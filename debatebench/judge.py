"""
Judge panel logic and aggregation.
"""
from __future__ import annotations

import json
import random
import re
import time
from typing import Dict, List, Tuple, Optional

from .models import JudgeAdapter
from .schema import AggregatedResult, JudgeResult, JudgeScores, MainConfig, Transcript


def _build_judge_prompt(transcript: Transcript, config: MainConfig) -> str:
    turns_text = "\n".join(
        f"{t.speaker.upper()} ({t.stage}): {t.content}" for t in transcript.turns
    )
    dims = ", ".join(d.id for d in config.scoring.dimensions)
    return (
        f"Debate transcript for motion: {transcript.topic.motion}\n"
        f"Scores needed on dimensions ({dims}) with scale "
        f"{config.scoring.scale_min}-{config.scoring.scale_max}.\n"
        f"Provide winner as pro/con/tie.\n\n"
        f"{turns_text}"
    )


def _synthetic_scores(dim_ids: List[str], scale_min: int, scale_max: int, rng: random.Random) -> Dict[str, int]:
    return {dim: rng.randint(scale_min, scale_max) for dim in dim_ids}


def _extract_json_block(text: str) -> Optional[dict]:
    """
    Find the first JSON object in free-form text and parse it.
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        snippet = match.group(0)
        try:
            return json.loads(snippet)
        except Exception:
            return None
    return None


def _parse_or_synthesize(
    response: str,
    dim_ids: List[str],
    scale_min: int,
    scale_max: int,
    rng: random.Random,
) -> Tuple[str, Dict[str, int], Dict[str, int]]:
    """
    Try to parse a judge JSON response; fallback to extracting winner from text; then synthesize remaining fields.
    """
    winner = "tie"
    pro_scores: Dict[str, int] = {}
    con_scores: Dict[str, int] = {}

    payload = _extract_json_block(response)
    if payload:
        winner = payload.get("winner", winner)
        pro_scores = payload.get("pro", {}) or payload.get("scores", {}).get("pro", {})
        con_scores = payload.get("con", {}) or payload.get("scores", {}).get("con", {})
    else:
        m = re.search(r"winner\s*[:\-]\s*(pro|con|tie)", response, re.I)
        if m:
            winner = m.group(1).lower()

    # Fill missing dimensions
    for dim in dim_ids:
        if dim not in pro_scores:
            pro_scores[dim] = rng.randint(scale_min, scale_max)
        if dim not in con_scores:
            con_scores[dim] = rng.randint(scale_min, scale_max)

    if winner not in {"pro", "con", "tie"}:
        winner = "tie"

    return winner, pro_scores, con_scores


def run_single_judge(
    adapter: JudgeAdapter,
    transcript: Transcript,
    config: MainConfig,
    rng: random.Random,
) -> JudgeResult:
    prompt = _build_judge_prompt(transcript, config)
    t0 = time.perf_counter()
    raw, usage = adapter.judge(prompt)
    latency_ms = (time.perf_counter() - t0) * 1000
    dim_ids = [d.id for d in config.scoring.dimensions]
    winner, pro_scores, con_scores = _parse_or_synthesize(
        raw, dim_ids, config.scoring.scale_min, config.scoring.scale_max, rng
    )
    return JudgeResult(
        judge_id=adapter.config.id,
        pro=JudgeScores(scores=pro_scores),
        con=JudgeScores(scores=con_scores),
        winner=winner,
        raw_response=raw,
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens") if usage else None,
        completion_tokens=usage.get("completion_tokens") if usage else None,
        total_tokens=usage.get("total_tokens") if usage else None,
    )


def aggregate_panel(results: List[JudgeResult]) -> AggregatedResult:
    vote_counts = {"pro": 0, "con": 0, "tie": 0}
    for r in results:
        vote_counts[r.winner] = vote_counts.get(r.winner, 0) + 1

    if vote_counts["pro"] > vote_counts["con"]:
        winner = "pro"
    elif vote_counts["con"] > vote_counts["pro"]:
        winner = "con"
    else:
        winner = "tie"

    # mean scores per dimension
    dim_keys = set()
    for r in results:
        dim_keys.update(r.pro.scores.keys())
        dim_keys.update(r.con.scores.keys())

    mean_pro: Dict[str, float] = {}
    mean_con: Dict[str, float] = {}
    for dim in dim_keys:
        mean_pro[dim] = sum(r.pro.scores.get(dim, 0) for r in results) / len(results)
        mean_con[dim] = sum(r.con.scores.get(dim, 0) for r in results) / len(results)

    return AggregatedResult(winner=winner, mean_pro=mean_pro, mean_con=mean_con)


def run_judge_panel(
    judge_adapters: List[JudgeAdapter],
    transcript: Transcript,
    config: MainConfig,
    seed: int | None = None,
) -> Tuple[List[JudgeResult], AggregatedResult]:
    rng = random.Random(seed)
    results = [
        run_single_judge(adapter, transcript, config, rng) for adapter in judge_adapters
    ]
    aggregate = aggregate_panel(results)
    return results, aggregate
