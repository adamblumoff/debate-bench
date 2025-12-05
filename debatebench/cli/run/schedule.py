"""Scheduling helpers for `debatebench run`."""
from __future__ import annotations

import hashlib
import itertools
import random
from typing import List

import typer


def derive_debate_seed(tag: str, topic_id: str, pro_id: str, con_id: str, rep: int) -> int:
    """
    Deterministically derive a per-debate seed so resumes reproduce the same
    side swaps and judge panels.
    """
    key = f"{tag}|{topic_id}|{pro_id}|{con_id}|{rep}".encode("utf-8")
    digest = hashlib.blake2s(key, digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFF


def build_pairs(models: List, balanced_sides: bool):
    """Return ordered model pairs based on balance flag."""
    if balanced_sides:
        return list(itertools.permutations(models, 2))
    return list(itertools.combinations(models, 2))


def select_judges(pool, expected: int, seed_val: int, usage_counts: dict[str, int], balanced_judges: bool):
    if len(pool) < expected:
        raise typer.BadParameter(f"Need at least {expected} judges after exclusions; found {len(pool)}.")
    rng = random.Random(seed_val)
    if balanced_judges:
        ordered = sorted(
            pool,
            key=lambda j: (usage_counts.get(j.id, 0), rng.random(), j.id),
        )
        return ordered[:expected]
    return rng.sample(pool, expected)


__all__ = ["derive_debate_seed", "build_pairs", "select_judges"]
