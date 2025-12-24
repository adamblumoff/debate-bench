"""Execution loop for the `debatebench run` command."""
from __future__ import annotations

import json
import os
import threading
import queue
import time
from datetime import datetime, timezone
from typing import List
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.console import Group
from rich.live import Live

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
    status_hook=None,
    progress_hook=None,
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
        progress_hook=progress_hook,
    )
    if status_hook:
        status_hook(phase="judging")

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
    failed_total = 0
    skipped_total = 0
    run_index = 0
    total_rounds = len(main_cfg.rounds)
    total_steps = total_rounds + 1
    status_lock = threading.Lock()
    task_status: dict[str, dict] = {}
    status_queue: queue.Queue[tuple] = queue.Queue()

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
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )
    progress_task = progress.add_task("Debates", total=total_runs)

    def update_progress(active_count: int = 0) -> None:
        progress.update(
            progress_task,
            description=(
                f"Debates (active={active_count}, failed={failed_total}, skipped={skipped_total})"
            ),
        )

    def _progress_bar(current: int, total: int, width: int = 10) -> str:
        if total <= 0:
            return "-" * width
        filled = int(round(width * (current / total)))
        filled = max(0, min(width, filled))
        return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"

    def _update_status(task_id: str, **updates) -> None:
        with status_lock:
            entry = task_status.setdefault(
                task_id,
                {"round": 0, "stage": "-", "phase": "queued", "error": ""},
            )
            entry.update(updates)

    def drain_status(live: Live | None, inflight: dict) -> None:
        updated = False
        while True:
            try:
                event = status_queue.get_nowait()
            except queue.Empty:
                break
            updated = True
            kind, task_id, payload = event
            if kind == "turn":
                _update_status(task_id, round=payload["round"], stage=payload["stage"], phase="debating")
            elif kind == "phase":
                _update_status(
                    task_id,
                    phase=payload.get("phase", "queued"),
                    round=payload.get("round", 0),
                    stage=payload.get("stage", "-"),
                )
            elif kind == "error":
                _update_status(task_id, phase="error", error=payload["message"])
        if updated and live:
            live.update(render_active(inflight))

    def render_active(inflight: dict) -> Group:
        table = Table(title="Active debates", expand=True, show_edge=False)
        table.add_column("Slot", justify="right", width=4)
        table.add_column("Topic", overflow="fold")
        table.add_column("Pro", overflow="fold")
        table.add_column("Con", overflow="fold")
        table.add_column("Round", justify="right", width=9)
        table.add_column("Stage", overflow="fold")
        table.add_column("Phase", overflow="fold")
        table.add_column("Error", overflow="fold")
        table.add_column("Progress", overflow="fold")
        if not inflight:
            table.add_row("-", "-", "-", "-", "-", "-", "-", "-", "-")
        else:
            for idx, (_, meta) in enumerate(inflight.items(), start=1):
                task, _attempt_seed, _task_index, _start_time = meta
                with status_lock:
                    status = task_status.get(
                        task.task_id, {"round": 0, "stage": "-", "phase": "queued", "error": ""}
                    )
                round_idx = status.get("round", 0)
                stage = status.get("stage", "-")
                phase = status.get("phase", "queued")
                error = status.get("error", "")
                progress_bar = _progress_bar(round_idx, total_steps)
                table.add_row(
                    str(idx),
                    task.topic.id,
                    task.pro_model.id,
                    task.con_model.id,
                    f"{round_idx}/{total_steps}",
                    stage,
                    phase,
                    error,
                    progress_bar,
                )
        return Group(progress, table)

    def run_task(task, attempt_seed: int, log_fn, status_hook, progress_hook):
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
            log=log_fn,
            status_hook=status_hook,
            progress_hook=progress_hook,
        )
        return record, aggregate

    def submit_tasks(task_list, retry_offset: int = 0, live: Live | None = None):
        nonlocal completed_new, run_index, failed_debates, failed_total, skipped_total
        index = 0
        inflight = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while index < len(task_list) or inflight:
                drain_status(live, inflight)
                while index < len(task_list) and len(inflight) < max_workers:
                    task = task_list[index]
                    index += 1
                    if task.pro_model.id in banned_models or task.con_model.id in banned_models:
                        skipped_total += 1
                        progress.advance(progress_task, 1)
                        update_progress(active_count=len(inflight))
                        if live:
                            live.update(render_active(inflight))
                        continue
                    run_index += 1
                    task_index = run_index
                    attempt_seed = task.seed + retry_offset
                    update_progress(active_count=len(inflight) + 1)
                    start_time = time.perf_counter()
                    _update_status(task.task_id, phase="debating", round=0, stage="-", error="")

                    def progress_hook(round_idx: int, speaker: str, stage: str, *, task_id: str = task.task_id):
                        status_queue.put(
                            (
                                "turn",
                                task_id,
                                {"round": round_idx, "stage": stage, "speaker": speaker},
                            )
                        )

                    def status_hook(**updates):
                        if updates.get("phase") == "judging":
                            updates.setdefault("round", total_steps)
                            updates.setdefault("stage", "judging")
                        status_queue.put(("phase", task.task_id, updates))

                    future = pool.submit(run_task, task, attempt_seed, None, status_hook, progress_hook)
                    inflight[future] = (task, attempt_seed, task_index, start_time)
                    if live:
                        live.update(render_active(inflight))

                done, _ = wait(inflight.keys(), return_when=FIRST_COMPLETED, timeout=0.2)
                if not done:
                    continue
                for future in done:
                    task, attempt_seed, task_index, start_time = inflight.pop(future)
                    try:
                        record, aggregate = future.result()
                        append_debate_record(setup.debates_path, record)
                        completed_new += 1
                        progress.advance(progress_task, 1)
                        write_progress()
                        update_progress(active_count=len(inflight))
                        _update_status(task.task_id, phase="done")
                        if live:
                            live.update(render_active(inflight))
                    except EmptyResponseError as e:
                        failed_total += 1
                        update_progress(active_count=len(inflight))
                        status_queue.put(("error", task.task_id, {"message": str(e)}))
                        if live:
                            live.console.print(
                                f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                            )
                        if opts.skip_on_empty:
                            banned_models.add(e.model_id)
                            if live:
                                live.console.print(
                                    f"[yellow]Skipping model {e.model_id} for remainder of run due to empty responses.[/yellow]"
                                )
                            write_progress()
                        else:
                            failed_debates.append(task)
                        if live:
                            live.update(render_active(inflight))
                    except Exception as e:
                        failed_total += 1
                        status_queue.put(("error", task.task_id, {"message": str(e)}))
                        update_progress(active_count=len(inflight))
                        if live:
                            live.console.print(
                                f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                            )
                        failed_debates.append(task)
                        if live:
                            live.update(render_active(inflight))

    with Live(render_active({}), console=console, refresh_per_second=4) as live:
        update_progress(active_count=0)
        live.update(render_active({}))
        submit_tasks(plan.tasks, retry_offset=0, live=live)

        if opts.retry_failed and failed_debates:
            live.console.print(
                f"[yellow]Retrying {len(failed_debates)} failed debates once...[/yellow]"
            )
            retry_list = list(failed_debates)
            failed_debates = []
            retry_tasks = []
            for task in retry_list:
                if task.pro_model.id in banned_models or task.con_model.id in banned_models:
                    continue
                retry_tasks.append(task)
            if retry_tasks:
                submit_tasks(retry_tasks, retry_offset=17, live=live)


__all__ = ["execute_plan"]
