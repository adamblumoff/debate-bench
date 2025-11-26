"""
Elo rating utilities for DebateBench.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Tuple

from .schema import DebateRecord, EloConfig, MainConfig, RatingEntry, RatingsFile


def expected_score(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (r_b - r_a) / 400.0))


def update_elo(r_a: float, r_b: float, score_a: float, k: float) -> Tuple[float, float]:
    exp_a = expected_score(r_a, r_b)
    delta_a = k * (score_a - exp_a)
    return r_a + delta_a, r_b - delta_a


def recompute_ratings(debates: List[DebateRecord], config: MainConfig) -> RatingsFile:
    elo_cfg: EloConfig = config.elo
    ratings: Dict[str, float] = defaultdict(lambda: elo_cfg.initial_rating)
    games_played: Dict[str, int] = defaultdict(int)
    dim_sums: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dim_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Sort debates deterministically by creation time then id
    debates_sorted = sorted(debates, key=lambda d: (d.created_at, d.transcript.debate_id))

    for record in debates_sorted:
        pro = record.transcript.pro_model_id
        con = record.transcript.con_model_id
        winner = record.aggregate.winner

        if winner == "pro":
            score_pro = 1.0
        elif winner == "con":
            score_pro = 0.0
        else:
            score_pro = 0.5

        r_pro, r_con = ratings[pro], ratings[con]
        new_pro, new_con = update_elo(r_pro, r_con, score_pro, elo_cfg.k_factor)
        ratings[pro], ratings[con] = new_pro, new_con
        games_played[pro] += 1
        games_played[con] += 1

        # accumulate dimension means for each side
        for dim, score in record.aggregate.mean_pro.items():
            dim_sums[pro][dim] += score
            dim_counts[pro][dim] += 1
        for dim, score in record.aggregate.mean_con.items():
            dim_sums[con][dim] += score
            dim_counts[con][dim] += 1

    model_entries: Dict[str, RatingEntry] = {}
    for model_id, rating in ratings.items():
        dim_avgs = {
            dim: dim_sums[model_id][dim] / dim_counts[model_id][dim]
            for dim in dim_sums[model_id]
            if dim_counts[model_id][dim] > 0
        }
        model_entries[model_id] = RatingEntry(
            rating=rating,
            games_played=games_played[model_id],
            dimension_avgs=dim_avgs,
        )

    return RatingsFile(
        benchmark_version=config.benchmark_version,
        rubric_version=config.rubric_version,
        elo=elo_cfg,
        models=model_entries,
    )
