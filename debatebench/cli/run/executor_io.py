"""I/O helpers for the `debatebench run` executor."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def write_progress(
    *,
    progress_path: Path,
    run_tag: str,
    debates_path: Path,
    total_planned_remaining: int,
    completed_new: int,
    completed_prior: int,
    banned_models: Iterable[str],
    round_order: str | None = None,
) -> None:
    payload = {
        "run_tag": run_tag,
        "debates_file": str(debates_path),
        "total_planned_remaining": total_planned_remaining,
        "completed_new": completed_new,
        "completed_prior": completed_prior,
        "completed_total": completed_prior + completed_new,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "banned_models": sorted(banned_models),
        "round_order": round_order,
    }
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


__all__ = ["write_progress"]
