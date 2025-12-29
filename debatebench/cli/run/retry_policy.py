"""Retry and skip policy helpers for `debatebench run`."""
from __future__ import annotations

from typing import Iterable

from ...debate import EmptyResponseError


def should_skip_task(task, banned_models: Iterable[str]) -> bool:
    banned = set(banned_models)
    return task.pro_model.id in banned or task.con_model.id in banned


def record_empty_response_failure(
    *,
    error: EmptyResponseError,
    task,
    opts,
    banned_models: set,
    failed_debates: list,
    progress_writer,
    progress_payload: dict,
    live_console=None,
) -> None:
    if opts.skip_on_empty:
        banned_models.add(error.model_id)
        if live_console:
            live_console.print(
                f"[yellow]Skipping model {error.model_id} for remainder of run due to empty responses.[/yellow]"
            )
        progress_writer(**progress_payload, banned_models=banned_models)
    else:
        failed_debates.append(task)


def record_general_failure(task, failed_debates: list) -> None:
    failed_debates.append(task)


__all__ = ["should_skip_task", "record_empty_response_failure", "record_general_failure"]
