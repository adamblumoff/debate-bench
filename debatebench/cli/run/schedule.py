"""Scheduling helpers for `debatebench run`."""
from __future__ import annotations

import hashlib
import itertools
import random
from typing import List, Tuple

import typer

UsageKey = Tuple[str, str]


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


def make_pair_key(pro_id: str, con_id: str) -> str:
    return f"{pro_id}|||{con_id}"


def select_judges(
    pool,
    expected: int,
    seed_val: int,
    usage_counts: dict[str, int],
    balanced_judges: bool,
    topic_id: str | None = None,
    pair_key: str | None = None,
    topic_usage: dict[UsageKey, int] | None = None,
    pair_usage: dict[UsageKey, int] | None = None,
):
    if len(pool) < expected:
        raise typer.BadParameter(f"Need at least {expected} judges after exclusions; found {len(pool)}.")
    rng = random.Random(seed_val)
    if balanced_judges:

        def score(j):
            total = usage_counts.get(j.id, 0)
            t_score = (
                (topic_usage or {}).get((j.id, topic_id or ""), 0)
                if topic_id is not None
                else 0
            )
            p_score = (
                (pair_usage or {}).get((j.id, pair_key or ""), 0)
                if pair_key is not None
                else 0
            )
            # Prioritize least-used on topic, then pair, then overall.
            return (t_score, p_score, total, rng.random(), j.id)

        ordered = sorted(pool, key=score)
        return ordered[:expected]
    return rng.sample(pool, expected)


__all__ = ["derive_debate_seed", "build_pairs", "select_judges", "make_pair_key"]
