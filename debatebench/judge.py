"""
Judge panel logic and aggregation.
"""
from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Tuple, Optional

from .models import JudgeAdapter
from .schema import AggregatedResult, JudgeResult, JudgeScores, MainConfig, Transcript


def _build_judge_prompt(transcript: Transcript, config: MainConfig, reinforce_json: bool = False) -> str:
    turns_text = "\n".join(
        f"{t.speaker.upper()} ({t.stage}): {t.content}" for t in transcript.turns
    )
    dims = ", ".join(d.id for d in config.scoring.dimensions)
    system = config.judge_system_prompt or (
        "You are an expert debate adjudicator. Read the transcript and output ONLY a JSON object with per-dimension integer scores; winner will be derived from the scores."
    )
    instructions = (
        f"Return a single JSON object with keys scores.pro, scores.con. "
        f"Scores must include dimensions: {dims}, each an integer {config.scoring.scale_min}-{config.scoring.scale_max}. "
        f"Do not include overall reasoning or commentary. Do not include a winner field; it will be computed separately."
    )
    if reinforce_json:
        instructions += " Do not include any text before or after the JSON. Respond with JSON only."
    return (
        f"{system}\n\n"
        f"Motion: {transcript.topic.motion}\n"
        f"Dimensions: {dims} (scale {config.scoring.scale_min}-{config.scoring.scale_max})\n"
        f"{instructions}\n\n"
        f"Transcript:\n{turns_text}"
    )


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


def _parse_json_scores(payload: dict, dim_ids: List[str], scale_min: int, scale_max: int) -> Tuple[Dict[str, int], Dict[str, int]]:
    if not isinstance(payload, dict):
        raise ValueError("Judge response is not a JSON object.")
    scores = payload.get("scores") or {}
    pro_scores = scores.get("pro") or payload.get("pro")
    con_scores = scores.get("con") or payload.get("con")
    if not isinstance(pro_scores, dict) or not isinstance(con_scores, dict):
        raise ValueError("Missing scores for pro/con.")
    def validate_side(side_scores: Dict[str, int]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for dim in dim_ids:
            if dim not in side_scores:
                raise ValueError(f"Missing dimension {dim}")
            val = side_scores[dim]
            if isinstance(val, str) and val.isdigit():
                val = int(val)
            if not isinstance(val, int):
                raise ValueError(f"Dimension {dim} is not int")
            if val < scale_min or val > scale_max:
                raise ValueError(f"Dimension {dim} out of range")
            out[dim] = val
        return out
    return validate_side(pro_scores), validate_side(con_scores)


def run_single_judge(
    adapter: JudgeAdapter,
    transcript: Transcript,
    config: MainConfig,
) -> JudgeResult:
    dim_ids = [d.id for d in config.scoring.dimensions]
    attempts = 0
    raw = ""
    usage = {}
    latency_ms = None
    pro_scores: Dict[str, int] = {}
    con_scores: Dict[str, int] = {}

    while attempts < 5 and (not pro_scores or not con_scores):
        reinforce = attempts >= 1
        prompt = _build_judge_prompt(transcript, config, reinforce_json=reinforce)
        if attempts >= 3:
            # Final attempts: add explicit JSON skeleton to maximize compliance.
            example = {
                "scores": {
                    "pro": {dim: config.scoring.scale_min for dim in dim_ids},
                    "con": {dim: config.scoring.scale_min for dim in dim_ids},
                }
            }
            prompt += (
                "\n\nReturn JSON only. Do NOT include Markdown or code fences. "
                f"Example structure (fill with your integer scores {config.scoring.scale_min}-{config.scoring.scale_max}):\n"
                f"{example}"
            )
        t0 = time.perf_counter()
        raw, usage = adapter.judge(prompt)
        latency_ms = (time.perf_counter() - t0) * 1000
        payload = _extract_json_block(raw)
        if payload:
            try:
                pro_scores, con_scores = _parse_json_scores(
                    payload, dim_ids, config.scoring.scale_min, config.scoring.scale_max
                )
            except ValueError:
                pro_scores = {}
                con_scores = {}
        attempts += 1

    if not pro_scores or not con_scores:
        raise RuntimeError("Judge response was not valid JSON after three attempts.")

    # Derive winner from mean dimension scores
    pro_avg = sum(pro_scores.values()) / len(pro_scores)
    con_avg = sum(con_scores.values()) / len(con_scores)
    if pro_avg > con_avg:
        winner = "pro"
    elif con_avg > pro_avg:
        winner = "con"
    else:
        winner = "tie"

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
    log=None,
) -> Tuple[List[JudgeResult], AggregatedResult]:
    results: List[JudgeResult] = []
    for adapter in judge_adapters:
        try:
            results.append(run_single_judge(adapter, transcript, config))
        except Exception as e:
            if log:
                log(f"[yellow]Judge {adapter.config.id} dropped: {e}[/yellow]")
            continue
    if not results:
        raise RuntimeError("All judges failed to return valid JSON.")
    aggregate = aggregate_panel(results)
    return results, aggregate
