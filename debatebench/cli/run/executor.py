"""Execution loop for the `debatebench run` command."""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from typing import List, Tuple

import typer

from ...debate import EmptyResponseError, run_debate
from ...judge import run_judge_panel
from ...models import build_debater_adapter, build_judge_adapter
from ...schema import DebateRecord
from ...storage import append_debate_record
from ..common import console
from .schedule import derive_debate_seed, make_pair_key, select_judges
from .types import RunPlan, RunSetup


def execute_plan(setup: RunSetup, plan: RunPlan) -> None:
    """Run debates, manage retries/progress, and append records."""
    opts = setup.options
    main_cfg = setup.main_cfg

    debater_adapters = {m.id: build_debater_adapter(m, setup.settings) for m in setup.debater_models}
    judge_adapters = {j.id: build_judge_adapter(j, setup.settings) for j in setup.judge_models}

    total_runs = plan.total_runs
    completed_counts = plan.completed_counts
    judge_usage = plan.judge_usage
    topic_usage = plan.topic_usage
    pair_usage = plan.pair_usage
    existing_completed = plan.existing_completed

    progress_path = plan.progress_path or (setup.run_dir / "progress.json")
    failed_judges_path = setup.run_dir / "failed_judges.jsonl" if opts.log_failed_judges else None

    banned_models = set()
    failed_debates: List[Tuple] = []
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

    for topic in plan.topics_selected:
        for (model_a, model_b) in plan.pairs:
            if model_a.id in banned_models or model_b.id in banned_models:
                continue
            key = (topic.id, model_a.id, model_b.id)
            already_done = completed_counts.get(key, 0)
            if already_done >= plan.debates_per_pair:
                continue
            for rep in range(already_done, plan.debates_per_pair):
                run_index += 1
                debate_seed = derive_debate_seed(setup.run_tag, topic.id, model_a.id, model_b.id, rep)
                debate_rng = random.Random(debate_seed)
                pro_model = model_a
                con_model = model_b
                if (not opts.balanced_sides) and opts.swap_sides and debate_rng.random() < 0.5:
                    pro_model, con_model = con_model, pro_model

                pro_adapter = debater_adapters[pro_model.id]
                con_adapter = debater_adapters[con_model.id]

                console.print(
                    f"[yellow]Debate {run_index}/{total_runs}[/yellow] "
                    f"Topic '{topic.id}' | PRO={pro_model.id} vs CON={con_model.id}"
                )
                log = console.print

                try:
                    t0 = time.perf_counter()
                    transcript = run_debate(
                        topic=topic,
                        pro_adapter=pro_adapter,
                        con_adapter=con_adapter,
                        config=main_cfg,
                        seed=opts.seed,
                        log=log,
                    )

                    judge_source_pool = list(setup.judge_models)
                    if opts.judges_from_selection:
                        judge_source_pool = [j for j in setup.judge_models if j.id not in {pro_model.id, con_model.id}]
                    pair_key = make_pair_key(pro_model.id, con_model.id)
                    panel_configs = select_judges(
                        judge_source_pool,
                        main_cfg.num_judges,
                        debate_seed,
                        judge_usage,
                        opts.balanced_judges,
                        topic_id=topic.id,
                        pair_key=pair_key,
                        topic_usage=topic_usage,
                        pair_usage=pair_usage,
                    )
                    panel_adapters = [judge_adapters[j.id] for j in panel_configs]
                    remaining_candidates = [
                        j for j in judge_source_pool if j.id not in {cfg.id for cfg in panel_configs}
                    ]
                    remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

                    console.print(
                        f"  Judging with panel: {', '.join(j.id for j in panel_configs)}"
                    )

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
                        usage=judge_usage,
                        seed=debate_seed,
                        log=log,
                        failed_judges_sink=sink_failed if failed_judges_path else None,
                    )

                    panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)
                    for jr in judge_results:
                        jid = jr.judge_id
                        topic_usage[(jid, topic.id)] = topic_usage.get((jid, topic.id), 0) + 1
                        pair_usage[(jid, pair_key)] = pair_usage.get((jid, pair_key), 0) + 1
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
                    append_debate_record(setup.debates_path, record)
                    completed_counts[key] = completed_counts.get(key, 0) + 1
                    completed_new += 1
                    write_progress()
                    elapsed = (time.perf_counter() - t0) * 1000

                    console.print(
                        f"[cyan]{run_index}/{total_runs}[/cyan] "
                        f"Topic '{topic.id}' {pro_model.id} (Pro) vs {con_model.id} (Con) "
                        f"-> winner: {aggregate.winner} ({elapsed:.0f} ms)"
                    )
                except EmptyResponseError as e:
                    console.print(
                        f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}"
                    )
                    if opts.skip_on_empty:
                        banned_models.add(e.model_id)
                        console.print(
                            f"[yellow]Skipping model {e.model_id} for remainder of run due to empty responses.[/yellow]"
                        )
                        write_progress()
                    else:
                        failed_debates.append((topic, pro_model, con_model, rep))
                except Exception as e:
                    console.print(f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}")
                    failed_debates.append((topic, pro_model, con_model, rep))

    if opts.retry_failed and failed_debates:
        console.print(f"[yellow]Retrying {len(failed_debates)} failed debates once...[/yellow]")
        retry_list = list(failed_debates)
        failed_debates = []
        for topic, model_a, model_b, rep in retry_list:
            if model_a.id in banned_models or model_b.id in banned_models:
                continue
            key = (topic.id, model_a.id, model_b.id)
            if completed_counts.get(key, 0) >= plan.debates_per_pair:
                continue
            retry_seed = derive_debate_seed(setup.run_tag, topic.id, model_a.id, model_b.id, rep) + 17
            debate_rng = random.Random(retry_seed)
            pro_model = model_a
            con_model = model_b
            if (not opts.balanced_sides) and opts.swap_sides and debate_rng.random() < 0.5:
                pro_model, con_model = con_model, pro_model

            pro_adapter = debater_adapters[pro_model.id]
            con_adapter = debater_adapters[con_model.id]

            try:
                t0 = time.perf_counter()
                transcript = run_debate(
                    topic=topic,
                    pro_adapter=pro_adapter,
                    con_adapter=con_adapter,
                    config=main_cfg,
                    seed=opts.seed,
                    log=console.print,
                )

                judge_source_pool = list(setup.judge_models)
                if opts.judges_from_selection:
                    judge_source_pool = [j for j in setup.judge_models if j.id not in {pro_model.id, con_model.id}]
                pair_key = make_pair_key(pro_model.id, con_model.id)
                panel_configs = select_judges(
                    judge_source_pool,
                    main_cfg.num_judges,
                    retry_seed,
                    judge_usage,
                    opts.balanced_judges,
                    topic_id=topic.id,
                    pair_key=pair_key,
                    topic_usage=topic_usage,
                    pair_usage=pair_usage,
                )
                remaining_candidates = [
                    j for j in judge_source_pool if j.id not in {cfg.id for cfg in panel_configs}
                ]
                panel_adapters = [judge_adapters[j.id] for j in panel_configs]
                remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

                judge_results, aggregate = run_judge_panel(
                    candidate_adapters=panel_adapters + remaining_adapters,
                    transcript=transcript,
                    config=main_cfg,
                    expected=main_cfg.num_judges,
                    usage=judge_usage,
                    seed=retry_seed,
                    log=console.print,
                )

                panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)
                for jr in judge_results:
                    jid = jr.judge_id
                    topic_usage[(jid, topic.id)] = topic_usage.get((jid, topic.id), 0) + 1
                    pair_usage[(jid, pair_key)] = pair_usage.get((jid, pair_key), 0) + 1
                record = DebateRecord(
                    transcript=transcript,
                    judges=judge_results,
                    aggregate=aggregate,
                    created_at=datetime.now(timezone.utc),
                    judges_expected=main_cfg.num_judges,
                    judges_actual=len(judge_results),
                    panel_complete=len(judge_results) == main_cfg.num_judges,
                    panel_latency_ms=panel_latency,
                    debate_seed=retry_seed,
                    elo=main_cfg.elo,
                )
                append_debate_record(setup.debates_path, record)
                completed_counts[key] = completed_counts.get(key, 0) + 1
                completed_new += 1
                write_progress()
                elapsed = (time.perf_counter() - t0) * 1000
                console.print(
                    f"[green]Retry success[/green] Topic '{topic.id}' {pro_model.id} vs {con_model.id} -> {aggregate.winner} ({elapsed:.0f} ms)"
                )
            except Exception as e:
                console.print(f"[red]Retry failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}")


__all__ = ["execute_plan"]
