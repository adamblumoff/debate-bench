"""UI helpers for the `debatebench run` executor."""
from __future__ import annotations

import time
from typing import Callable

from rich.console import Group
from rich.table import Table


def update_progress(progress, progress_task, active_count: int, failed_total: int, skipped_total: int) -> None:
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


def render_active(
    *,
    inflight: dict,
    task_status: dict,
    status_lock,
    main_cfg,
    max_workers: int,
    total_runs: int,
    completed_new: int,
    failed_total: int,
    skipped_total: int,
    total_steps: int,
    progress,
    get_rate_status: Callable[[], dict],
) -> Group:
    status = get_rate_status()
    limiter = status.get("max_rpm")
    backoff = status.get("backoff_remaining") or 0.0
    backoff_reason = status.get("backoff_reason") or ""

    header = Table(show_header=False, box=None, expand=True)
    header.add_column(justify="left")
    header.add_row(
        f"Inflight {len(inflight)}/{max_workers} | "
        f"Completed {completed_new}/{total_runs} | "
        f"Failed {failed_total} | Skipped {skipped_total}"
    )
    if limiter:
        limiter_label = f"Rate limit: {limiter} RPM"
        if backoff > 0:
            limiter_label += f" | Backoff {backoff:.1f}s ({backoff_reason})"
        header.add_row(limiter_label)

    table = Table(title="Active debates", expand=True, show_edge=False)
    table.add_column("Slot", justify="right", width=4)
    table.add_column("Topic", overflow="fold")
    table.add_column("Pro", overflow="fold")
    table.add_column("Con", overflow="fold")
    table.add_column("Round", justify="right", width=9)
    table.add_column("Stage", overflow="fold")
    table.add_column("Phase", overflow="fold")
    table.add_column("Retry", justify="right", width=5)
    table.add_column("Judges", justify="right", width=7)
    table.add_column("Age", justify="right", width=6)
    table.add_column("Error", overflow="fold")
    table.add_column("Progress", overflow="fold")
    if not inflight:
        table.add_row("-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")
    else:
        for idx, (_, meta) in enumerate(inflight.items(), start=1):
            task, _attempt_seed, _task_index, _start_time = meta
            with status_lock:
                status = task_status.get(
                    task.task_id,
                    {
                        "round": 0,
                        "stage": "-",
                        "phase": "queued",
                        "error": "",
                        "last_update": time.monotonic(),
                        "judges_done": 0,
                        "judges_expected": main_cfg.num_judges,
                        "retrying": False,
                    },
                )
            round_idx = status.get("round", 0)
            stage = status.get("stage", "-")
            phase = status.get("phase", "queued")
            error = status.get("error", "")
            retrying = status.get("retrying", False)
            judges_done = status.get("judges_done", 0)
            judges_expected = status.get("judges_expected", main_cfg.num_judges)
            age = time.monotonic() - status.get("last_update", time.monotonic())
            judges_label = "-" if phase != "judging" else f"{judges_done}/{judges_expected}"
            progress_bar = _progress_bar(round_idx, total_steps)
            table.add_row(
                str(idx),
                task.topic.id,
                task.pro_model.id,
                task.con_model.id,
                f"{round_idx}/{total_steps}",
                stage,
                phase,
                "yes" if retrying else "-",
                judges_label,
                f"{age:.0f}s",
                error,
                progress_bar,
            )
    return Group(header, progress, table)


__all__ = ["render_active", "update_progress"]
