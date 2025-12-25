"""Planning helpers for the `debatebench run` command."""
from __future__ import annotations

import json
import random
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import typer

from ...storage import load_debate_records
from ..common import console
from .estimate import (
    estimate_cost,
    estimate_wall_time,
    fetch_pricing,
    format_duration,
    historical_debate_durations,
    load_activity_pricing,
    load_timing_snapshots,
    load_token_stats,
)
from .schedule import build_pairs, derive_debate_seed, make_pair_key, select_judges
from .types import DebateTask, RunPlan, RunSetup


def _write_progress(progress_path: Path, run_tag: str, debates_path: Path, total_runs: int, existing_completed: int, completed_new: int, banned_models):
    payload = {
        "run_tag": run_tag,
        "debates_file": str(debates_path),
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


def build_plan(setup: RunSetup, debates_per_pair: int) -> tuple[RunPlan | None, bool]:
    """Construct schedule, resume state, and (optionally) perform dry-run preview."""
    opts = setup.options
    main_cfg = setup.main_cfg

    if setup.incremental_mode:
        new_model_cfg = next((m for m in setup.debater_models if m.id == opts.new_model_id), None)
        if new_model_cfg is None:
            raise typer.BadParameter(f"New model '{opts.new_model_id}' disappeared after selection.")
        incumbents = [m for m in setup.debater_models if m.id != opts.new_model_id]
        combined_order = incumbents + [new_model_cfg]
        all_pairs = build_pairs(combined_order, opts.balanced_sides)
        pairs = [p for p in all_pairs if opts.new_model_id in {p[0].id, p[1].id}]
    else:
        pairs = build_pairs(setup.debater_models, opts.balanced_sides)

    completed_counts = defaultdict(int)
    judge_usage = defaultdict(int)
    existing = setup.existing_records
    loaded_from_disk = False
    if (not existing) and opts.resume and setup.debates_path.exists():
        existing = load_debate_records(setup.debates_path)
        loaded_from_disk = True
    if existing:
        for rec in existing:
            key = (rec.transcript.topic.id, rec.transcript.pro_model_id, rec.transcript.con_model_id)
            completed_counts[key] += 1
            for jres in rec.judges:
                judge_usage[jres.judge_id] += 1
        if setup.incremental_mode:
            console.print(
                f"[cyan]Loaded {len(existing)} completed debates from {setup.debates_path}; skipping already-finished pairings for incremental append.[/cyan]"
            )
        elif opts.resume and loaded_from_disk:
            console.print(
                f"[cyan]Resume mode: found {len(existing)} completed debates in {setup.debates_path}; will skip already-finished matchups.[/cyan]"
            )
    existing_completed = sum(completed_counts.values())

    def remaining_for(topic, a, b):
        done = completed_counts.get((topic.id, a.id, b.id), 0)
        return max(0, debates_per_pair - done)

    total_runs = sum(
        remaining_for(topic, a, b) for topic in setup.topics_selected for (a, b) in pairs
    )
    console.print(f"Scheduled {total_runs} debates (remaining).")

    progress_path = setup.run_dir / "progress.json"
    _write_progress(progress_path, setup.run_tag, setup.debates_path, total_runs, existing_completed, 0, set())

    def build_schedule(include_completed: bool) -> tuple[list[Dict], list[DebateTask]]:
        usage_counts = judge_usage.copy()
        topic_usage: dict[Tuple[str, str], int] = {}
        pair_usage: dict[Tuple[str, str], int] = {}
        preview: list[Dict] = []
        tasks = []
        for topic in setup.topics_selected:
            for (model_a, model_b) in pairs:
                already_done = completed_counts.get((topic.id, model_a.id, model_b.id), 0)
                for rep in range(debates_per_pair):
                    if not include_completed and rep < already_done:
                        continue
                    debate_seed = derive_debate_seed(
                        setup.run_tag, topic.id, model_a.id, model_b.id, rep
                    )
                    debate_rng = random.Random(debate_seed)
                    pro_model = model_a
                    con_model = model_b
                    if (not opts.balanced_sides) and opts.swap_sides and debate_rng.random() < 0.5:
                        pro_model, con_model = con_model, pro_model
                    judge_source_pool = list(setup.judge_models)
                    if opts.judges_from_selection:
                        judge_source_pool = [
                            j for j in setup.judge_models if j.id not in {pro_model.id, con_model.id}
                        ]
                    pair_key = make_pair_key(pro_model.id, con_model.id)
                    judges_chosen: list[str] = []
                    panel_configs = []
                    remaining_candidates = []
                    if main_cfg.num_judges > 0:
                        if len(judge_source_pool) < main_cfg.num_judges:
                            if include_completed:
                                judges_chosen = ["<insufficient judges after exclusion>"]
                            else:
                                raise typer.BadParameter(
                                    "Need at least "
                                    f"{main_cfg.num_judges} judges after exclusions; found "
                                    f"{len(judge_source_pool)}."
                                )
                        else:
                            panel_configs = select_judges(
                                judge_source_pool,
                                main_cfg.num_judges,
                                debate_seed,
                                usage_counts,
                                opts.balanced_judges,
                                topic_id=topic.id,
                                pair_key=pair_key,
                                topic_usage=topic_usage,
                                pair_usage=pair_usage,
                            )
                            judges_chosen = [j.id for j in panel_configs]
                            for j in panel_configs:
                                usage_counts[j.id] = usage_counts.get(j.id, 0) + 1
                                topic_usage[(j.id, topic.id)] = topic_usage.get((j.id, topic.id), 0) + 1
                                pair_usage[(j.id, pair_key)] = pair_usage.get((j.id, pair_key), 0) + 1
                            remaining_candidates = [
                                j for j in judge_source_pool if j.id not in {cfg.id for cfg in panel_configs}
                            ]
                    preview.append(
                        {
                            "topic": topic.id,
                            "pro": pro_model.id,
                            "con": con_model.id,
                            "judges": judges_chosen,
                            "rep": rep,
                        }
                    )
                    task_id = f"{topic.id}|{pro_model.id}|{con_model.id}|{rep}"
                    tasks.append(
                        DebateTask(
                            topic=topic,
                            pro_model=pro_model,
                            con_model=con_model,
                            rep=rep,
                            seed=debate_seed,
                            panel_configs=panel_configs,
                            remaining_candidates=remaining_candidates,
                            pair_key=pair_key,
                            task_id=task_id,
                        )
                    )
        return preview, tasks

    schedule_preview_for_estimate = None
    schedule_tasks_for_estimate: list[DebateTask] = []
    if opts.estimate_time:
        schedule_preview_for_estimate, schedule_tasks_for_estimate = build_schedule(include_completed=False)
        snapshots = load_timing_snapshots(Path("results"))
        max_workers = min(64, (os.cpu_count() or 4) * 8)
        per_model_cap = max_workers
        if schedule_tasks_for_estimate and snapshots:
            estimates, meta = estimate_wall_time(
                schedule_tasks_for_estimate,
                main_cfg.rounds,
                max_workers=max_workers,
                per_model_cap=per_model_cap,
                snapshots=snapshots,
            )
            buffered = {k: v * 1.15 for k, v in estimates.items()}
            console.print(
                f"[cyan]Estimated wall time:[/cyan] "
                f"~{format_duration(buffered['p50'])} "
                f"(p75 {format_duration(buffered['p75'])}, p90 {format_duration(buffered['p90'])}) "
                f"| workers={max_workers}, per-model cap={per_model_cap} | {meta.get('source','')}"
            )
        else:
            median_sec, hist_n = historical_debate_durations(Path("results"))
            per_debate_sec = median_sec if median_sec is not None else 60.0
            est_total_sec = per_debate_sec * total_runs
            buffered_sec = est_total_sec * 1.15
            median_label = f"{format_duration(per_debate_sec)} per debate"
            if hist_n:
                median_label += f" (median of {hist_n} recent debates)"
            else:
                median_label += " (heuristic default)"
            console.print(
                f"[cyan]Estimated wall time:[/cyan] ~{format_duration(buffered_sec)} "
                f"(planned {total_runs} debates; {median_label})"
            )

    # Dry-run path: cost/time + schedule preview, then exit.
    if opts.dry_run:
        judge_calls = total_runs * main_cfg.num_judges
        activity_pricing, activity_path = load_activity_pricing()
        models_needed = {m.model for m in setup.debater_models} | {
            j.model for j in setup.judge_models
        }
        pricing_map = fetch_pricing(models_needed, setup.settings)
        pricing_source_label = "live (OpenRouter catalog)"
        if activity_pricing:
            pricing_map.update(activity_pricing)
            if activity_path:
                pricing_source_label = f"activity ({activity_path.name}) + live fallback"
            else:
                pricing_source_label = "activity + live fallback"

        deb_stats, judge_stats, stats_path = load_token_stats()
        stats_label = f"turn averages from {stats_path.name}" if stats_path else "no historical token stats"
        total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost = estimate_cost(
            setup.debater_models,
            setup.judge_models,
            main_cfg.rounds,
            len(setup.topics_selected),
            debates_per_pair,
            opts.balanced_sides,
            pairs,
            pricing_override=pricing_map,
            token_stats=(deb_stats, judge_stats),
        )
        console.print("[green]Dry run (no debates executed).[/green]")
        console.print(f"[cyan]Cost pricing source:[/cyan] {pricing_source_label} | {stats_label}")
        console.print(
            f"Topics={len(setup.topics_selected)}, Debaters={len(setup.debater_models)}, Judges={len(setup.judge_models)}, "
            f"Debates planned={total_runs}, Judge calls={judge_calls}"
        )
        console.print("Debater models:")
        for m in setup.debater_models:
            console.print(f"  - {m.id} ({m.model}) max_tokens={m.token_limit}")
        console.print("Judge models:")
        for j in setup.judge_models:
            console.print(f"  - {j.id} ({j.model}) max_tokens={j.token_limit}")
        approx_total = total_debater_cost + total_judge_cost
        console.print(
            f"Estimated cost (very rough, USD): debaters ~${total_debater_cost:.2f}, judges ~${total_judge_cost:.2f}, total ~${approx_total:.2f}"
        )
        missing_models = {
            m.model for m in setup.debater_models if m.id not in per_model_cost
        } | {
            j.model for j in setup.judge_models if j.id not in per_judge_cost
        }
        if missing_models:
            console.print(
                f"[yellow]Pricing unavailable for: {', '.join(sorted(missing_models))} (not in OpenRouter catalog response); omitted from estimate.[/yellow]"
            )
        console.print("Per-debater share (approx):")
        for mid, cost in sorted(per_model_cost.items(), key=lambda kv: kv[1], reverse=True):
            console.print(f"  {mid}: ~${cost:.2f}")
        console.print("Per-judge share (approx):")
        for jid, cost in sorted(per_judge_cost.items(), key=lambda kv: kv[1], reverse=True):
            console.print(f"  {jid}: ~${cost:.2f}")

        schedule_preview, _tasks = build_schedule(include_completed=True)
        sched_path = setup.run_dir / "dryrun_schedule.json"
        with sched_path.open("w", encoding="utf-8") as f:
            json.dump(schedule_preview, f, indent=2)
        console.print(f"Saved full debate/judge schedule preview to {sched_path}")
        console.print("First 10 debates:")
        for i, entry in enumerate(schedule_preview[:10], start=1):
            console.print(
                f"  {i}. Topic {entry['topic']}: PRO={entry['pro']} vs CON={entry['con']} | judges={', '.join(entry['judges']) if entry['judges'] else 'n/a'}"
            )
        console.print(
            f"Output would be written to: debates={setup.debates_path}, viz={setup.viz_dir}, plots={setup.plots_dir}"
        )
        return None, True

    if schedule_tasks_for_estimate:
        schedule_tasks = schedule_tasks_for_estimate
    else:
        _schedule_preview, schedule_tasks = build_schedule(include_completed=False)

    plan = RunPlan(
        topics_selected=setup.topics_selected,
        pairs=pairs,
        debates_per_pair=debates_per_pair,
        total_runs=total_runs,
        completed_counts=completed_counts,
        tasks=schedule_tasks,
        existing_completed=existing_completed,
        progress_path=progress_path,
    )
    return plan, False


__all__ = ["build_plan"]
