"""Execution loop for the `debatebench run` command."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import List
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from ...debate import EmptyResponseError, run_debate
from ...judge import run_judge_panel
from ...models import build_debater_adapter, build_judge_adapter, configure_openrouter_rate_limit
from ...schema import DebateRecord
from ...storage import append_debate_record
from ..common import console
from .types import RunPlan, RunSetup


def _run_debate_and_judge(
    setup: RunSetup,
    topic,
    pro_model,
    con_model,
    debate_seed: int,
    debater_adapters,
    judge_adapters,
    panel_configs,
    remaining_candidates,
    failed_judges_path,
    log,
):
    main_cfg = setup.main_cfg
    pro_adapter = debater_adapters[pro_model.id]
    con_adapter = debater_adapters[con_model.id]

    transcript = run_debate(
        topic=topic,
        pro_adapter=pro_adapter,
        con_adapter=con_adapter,
        config=main_cfg,
        seed=setup.options.seed,
        log=log,
    )

    panel_adapters = [judge_adapters[j.id] for j in panel_configs]
    remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

    if log:
        log(f"  Judging with panel: {', '.join(j.id for j in panel_configs)}")

    usage_ordering = {cfg.id: 0 for cfg in panel_configs}
    usage_ordering.update({cfg.id: 1 for cfg in remaining_candidates})

    def sink_failed(payload):
        if not failed_judges_path:
            return
        failed_judges_path.parent.mkdir(parents=True, exist_ok=True)
        with failed_judges_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        **payload,
                        "debate_id": transcript.debate_id,
                        "topic": topic.id,
                        "pro": pro_model.id,
                        "con": con_model.id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
            f.write("\n")

    judge_results, aggregate = run_judge_panel(
        candidate_adapters=panel_adapters + remaining_adapters,
        transcript=transcript,
        config=main_cfg,
        expected=main_cfg.num_judges,
        usage=usage_ordering,
        seed=debate_seed,
        log=log,
        failed_judges_sink=sink_failed if failed_judges_path else None,
    )

    panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)

    record = DebateRecord(
        transcript=transcript,
        judges=judge_results,
        aggregate=aggregate,
        created_at=datetime.now(timezone.utc),
        judges_expected=main_cfg.num_judges,
        judges_actual=len(judge_results),
        panel_complete=len(judge_results) == main_cfg.num_judges,
        panel_latency_ms=panel_latency,
        debate_seed=debate_seed,
        elo=main_cfg.elo,
    )
    return record, aggregate


def execute_plan(setup: RunSetup, plan: RunPlan) -> None:
    """Run debates, manage retries/progress, and append records."""
    opts = setup.options
    main_cfg = setup.main_cfg

    uses_free_models = any(
        (model.model or "").endswith(":free")
        for model in [*setup.debater_models, *setup.judge_models]
    )
    configure_openrouter_rate_limit(20 if uses_free_models else None)
    if uses_free_models:
        console.print("[cyan]OpenRouter free models detected; throttling to ~20 RPM.[/cyan]")

    debater_adapters = {m.id: build_debater_adapter(m, setup.settings) for m in setup.debater_models}
    judge_adapters = {j.id: build_judge_adapter(j, setup.settings) for j in setup.judge_models}

    total_runs = plan.total_runs
    existing_completed = plan.existing_completed

    progress_path = plan.progress_path or (setup.run_dir / "progress.json")
    failed_judges_path = setup.run_dir / "failed_judges.jsonl" if opts.log_failed_judges else None

    banned_models = set()
    failed_debates: List = []
    completed_new = 0
    run_index = 0

    def write_progress():
        payload = {
            "run_tag": setup.run_tag,
            "debates_file": str(setup.debates_path),
            "total_planned_remaining": total_runs,
            "completed_new": completed_new,
            "completed_prior": existing_completed,
            "completed_total": existing_completed + completed_new,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "banned_models": sorted(banned_models),
        }
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    write_progress()
    max_workers = min(32, (os.cpu_count() or 4) * 4)

    def run_task(task, attempt_seed: int):
        record, aggregate = _run_debate_and_judge(
            setup=setup,
            topic=task.topic,
            pro_model=task.pro_model,
            con_model=task.con_model,
            debate_seed=attempt_seed,
            debater_adapters=debater_adapters,
            judge_adapters=judge_adapters,
            panel_configs=task.panel_configs,
            remaining_candidates=task.remaining_candidates,
            failed_judges_path=failed_judges_path,
            log=console.print,
        )
        return record, aggregate

    def submit_tasks(task_list, retry_offset: int = 0):
        nonlocal completed_new, run_index, failed_debates
        index = 0
        inflight = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while index < len(task_list) or inflight:
                while index < len(task_list) and len(inflight) < max_workers:
                    task = task_list[index]
                    index += 1
                    if task.pro_model.id in banned_models or task.con_model.id in banned_models:
                        continue
                    run_index += 1
                    task_index = run_index
                    attempt_seed = task.seed + retry_offset
                    console.print(
                        f"[yellow]Debate {task_index}/{total_runs}[/yellow] "
                        f"Topic '{task.topic.id}' | PRO={task.pro_model.id} vs CON={task.con_model.id}"
                    )
                    start_time = time.perf_counter()
                    future = pool.submit(run_task, task, attempt_seed)
                    inflight[future] = (task, attempt_seed, task_index, start_time)

                done, _ = wait(inflight.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    task, attempt_seed, task_index, start_time = inflight.pop(future)
                    try:
                        record, aggregate = future.result()
                        append_debate_record(setup.debates_path, record)
                        completed_new += 1
                        write_progress()
                        elapsed = (time.perf_counter() - start_time) * 1000
                        console.print(
                            f"[cyan]{task_index}/{total_runs}[/cyan] "
                            f"Topic '{task.topic.id}' {task.pro_model.id} (Pro) vs {task.con_model.id} (Con) "
                            f"-> winner: {aggregate.winner} ({elapsed:.0f} ms)"
                        )
                    except EmptyResponseError as e:
                        console.print(
                            f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                        )
                        if opts.skip_on_empty:
                            banned_models.add(e.model_id)
                            console.print(
                                f"[yellow]Skipping model {e.model_id} for remainder of run due to empty responses.[/yellow]"
                            )
                            write_progress()
                        else:
                            failed_debates.append(task)
                    except Exception as e:
                        console.print(
                            f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                        )
                        failed_debates.append(task)

    submit_tasks(plan.tasks, retry_offset=0)

    if opts.retry_failed and failed_debates:
        console.print(f"[yellow]Retrying {len(failed_debates)} failed debates once...[/yellow]")
        retry_list = list(failed_debates)
        failed_debates = []
        retry_tasks = []
        for task in retry_list:
            if task.pro_model.id in banned_models or task.con_model.id in banned_models:
                continue
            retry_tasks.append(task)
        if retry_tasks:
            submit_tasks(retry_tasks, retry_offset=17)


__all__ = ["execute_plan"]
