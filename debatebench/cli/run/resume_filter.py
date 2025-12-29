"""Resume helpers for completed debates."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Tuple


def count_completed(existing_records) -> tuple[Dict[Tuple[str, str, str], int], Dict[str, int]]:
    completed_counts = defaultdict(int)
    judge_usage = defaultdict(int)
    for rec in existing_records:
        key = (rec.transcript.topic.id, rec.transcript.pro_model_id, rec.transcript.con_model_id)
        completed_counts[key] += 1
        for jres in rec.judges:
            judge_usage[jres.judge_id] += 1
    return completed_counts, judge_usage


__all__ = ["count_completed"]
