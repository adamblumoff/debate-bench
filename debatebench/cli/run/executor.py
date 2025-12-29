"""Execution loop for the `debatebench run` command."""
from __future__ import annotations

import os
import signal
import threading
import time
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
from rich.live import Live

from ...debate import EmptyResponseError
from ...models import (
    build_debater_adapter,
    build_judge_adapter,
    configure_openrouter_rate_limit,
    get_openrouter_rate_limit_status,
)
from ...storage import append_debate_record
from ..common import console
from .executor_io import write_progress
from .executor_task import run_debate_and_judge
from .executor_status import StatusTracker
from .progress import render_active, update_progress
from .retry_policy import record_empty_response_failure, record_general_failure, should_skip_task
from .types import RunPlan, RunSetup, ExecutionResult


def execute_plan(setup: RunSetup, plan: RunPlan) -> ExecutionResult:
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
    stop_requested = threading.Event()
    status_tracker = StatusTracker(main_cfg=main_cfg, total_steps=total_steps)
    refresh_interval = 0.25
    last_refresh = time.monotonic()

    write_progress(
        progress_path=progress_path,
        run_tag=setup.run_tag,
        debates_path=setup.debates_path,
        total_planned_remaining=total_runs,
        completed_new=completed_new,
        completed_prior=existing_completed,
        banned_models=banned_models,
    )
    max_workers = min(64, (os.cpu_count() or 4) * 8)
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

    def maybe_update(live: Live | None, inflight: dict, force: bool = False) -> None:
        nonlocal last_refresh
        if not live:
            return
        now = time.monotonic()
        if force or (now - last_refresh) >= refresh_interval:
            live.update(
                render_active(
                    inflight=inflight,
                    task_status=status_tracker.task_status,
                    status_lock=status_tracker.status_lock,
                    main_cfg=main_cfg,
                    max_workers=max_workers,
                    total_runs=total_runs,
                    completed_new=completed_new,
                    failed_total=failed_total,
                    skipped_total=skipped_total,
                    total_steps=total_steps,
                    progress=progress,
                    get_rate_status=get_openrouter_rate_limit_status,
                )
            )
            last_refresh = now

    def drain_status(live: Live | None, inflight: dict) -> None:
        if status_tracker.drain():
            maybe_update(live, inflight)

    def run_task(task, attempt_seed: int, log_fn, status_hook, progress_hook, judge_hook):
        record, aggregate = run_debate_and_judge(
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
            judge_hook=judge_hook,
        )
        return record, aggregate

    def submit_tasks(task_list, retry_offset: int = 0, live: Live | None = None):
        nonlocal completed_new, run_index, failed_debates, failed_total, skipped_total
        queue_tasks = list(task_list)
        inflight = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            try:
                while queue_tasks or inflight:
                    if stop_requested.is_set():
                        raise KeyboardInterrupt
                    drain_status(live, inflight)
                    attempts = 0
                    while queue_tasks and len(inflight) < max_workers:
                        if stop_requested.is_set():
                            raise KeyboardInterrupt
                        task = queue_tasks.pop(0)
                        attempts += 1
                        if should_skip_task(task, banned_models):
                            skipped_total += 1
                            progress.advance(progress_task, 1)
                            update_progress(progress, progress_task, len(inflight), failed_total, skipped_total)
                            maybe_update(live, inflight)
                            continue
                        run_index += 1
                        task_index = run_index
                        attempt_seed = task.seed + retry_offset
                        update_progress(progress, progress_task, len(inflight) + 1, failed_total, skipped_total)
                        start_time = time.perf_counter()
                        status_tracker.update(
                            task.task_id,
                            phase="retrying" if retry_offset > 0 else "debating",
                            round=0,
                            stage="-",
                            error="",
                            judges_done=0,
                            judges_expected=main_cfg.num_judges,
                            retrying=retry_offset > 0,
                        )

                        task_id = task.task_id
                        progress_hook = status_tracker.make_progress_hook(task_id)
                        status_hook = status_tracker.make_status_hook(task_id)
                        judge_hook = status_tracker.make_judge_hook(task_id)

                        future = pool.submit(
                            run_task, task, attempt_seed, None, status_hook, progress_hook, judge_hook
                        )
                        inflight[future] = (task, attempt_seed, task_index, start_time)
                        maybe_update(live, inflight)

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
                            write_progress(
                                progress_path=progress_path,
                                run_tag=setup.run_tag,
                                debates_path=setup.debates_path,
                                total_planned_remaining=total_runs,
                                completed_new=completed_new,
                                completed_prior=existing_completed,
                                banned_models=banned_models,
                            )
                            update_progress(progress, progress_task, len(inflight), failed_total, skipped_total)
                            status_tracker.update(task.task_id, phase="done")
                            maybe_update(live, inflight)
                        except EmptyResponseError as e:
                            failed_total += 1
                            update_progress(progress, progress_task, len(inflight), failed_total, skipped_total)
                            status_tracker.status_queue.put(("error", task.task_id, {"message": str(e)}))
                            if live:
                                live.console.print(
                                    f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                                )
                            record_empty_response_failure(
                                error=e,
                                task=task,
                                opts=opts,
                                banned_models=banned_models,
                                failed_debates=failed_debates,
                                progress_writer=write_progress,
                                progress_payload={
                                    "progress_path": progress_path,
                                    "run_tag": setup.run_tag,
                                    "debates_path": setup.debates_path,
                                    "total_planned_remaining": total_runs,
                                    "completed_new": completed_new,
                                    "completed_prior": existing_completed,
                                },
                                live_console=live.console if live else None,
                            )
                            maybe_update(live, inflight)
                        except Exception as e:
                            failed_total += 1
                            status_tracker.status_queue.put(("error", task.task_id, {"message": str(e)}))
                            update_progress(progress, progress_task, len(inflight), failed_total, skipped_total)
                            if live:
                                live.console.print(
                                    f"[red]Debate failed ({task.pro_model.id} vs {task.con_model.id} on {task.topic.id}): {e}"
                                )
                            record_general_failure(task, failed_debates)
                            maybe_update(live, inflight)
            except KeyboardInterrupt:
                if live:
                    live.console.print("[yellow]Interrupted. Cancelling in-flight debates...[/yellow]")
                for future in list(inflight.keys()):
                    future.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise

    def _sigint_handler(_signum, _frame):
        stop_requested.set()
        console.print("[yellow]Run interrupted by user. Cancelling in-flight debates...[/yellow]")
        raise KeyboardInterrupt

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint_handler)
    try:
        with Live(
            render_active(
                inflight={},
                task_status=status_tracker.task_status,
                status_lock=status_tracker.status_lock,
                main_cfg=main_cfg,
                max_workers=max_workers,
                total_runs=total_runs,
                completed_new=completed_new,
                failed_total=failed_total,
                skipped_total=skipped_total,
                total_steps=total_steps,
                progress=progress,
                get_rate_status=get_openrouter_rate_limit_status,
            ),
            console=console,
            refresh_per_second=4,
        ) as live:
            update_progress(progress, progress_task, 0, failed_total, skipped_total)
            maybe_update(live, {}, force=True)
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
    finally:
        write_progress(
            progress_path=progress_path,
            run_tag=setup.run_tag,
            debates_path=setup.debates_path,
            total_planned_remaining=total_runs,
            completed_new=completed_new,
            completed_prior=existing_completed,
            banned_models=banned_models,
        )
        signal.signal(signal.SIGINT, previous_handler)

    return ExecutionResult(
        completed_new=completed_new,
        failed_total=failed_total,
        skipped_total=skipped_total,
        banned_models=sorted(banned_models),
    )


__all__ = ["execute_plan"]
