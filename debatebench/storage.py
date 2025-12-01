"""
Persistence helpers for DebateBench results.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from pydantic import ValidationError

from .schema import DebateRecord, RatingsFile


def append_debate_record(path: Path, record: DebateRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use Pydantic v2 API to avoid deprecated .json/dumps_kwargs issues.
    line = record.model_dump_json()
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")


def load_debate_records(path: Path) -> List[DebateRecord]:
    if not path.exists():
        return []
    records: List[DebateRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            try:
                records.append(DebateRecord(**payload))
            except ValidationError as e:
                raise ValueError(f"Invalid debate record in {path}: {e}") from e
    return records


def write_ratings(path: Path, ratings: RatingsFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        # Pydantic v2: model_dump_json supports stdlib json kwargs like indent.
        f.write(ratings.model_dump_json(indent=2))


def read_ratings(path: Path) -> RatingsFile:
    if not path.exists():
        raise FileNotFoundError(f"Ratings file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return RatingsFile(**payload)
