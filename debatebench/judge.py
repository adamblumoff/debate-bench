"""
Judge panel logic and aggregation.
"""
from __future__ import annotations

import json
import yaml
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
        f"Do NOT include rationale, markdown, thinking, or extra text. Do NOT include a winner field. "
        f"Example JSON: {{\"scores\": {{\"pro\": {{dim: int}}, \"con\": {{dim: int}}}}}}. "
        f"If you fail to return JSON, the content may be ignored."
    )
    if reinforce_json:
        instructions += " Respond with JSON only. No prose. No code fences."
    return (
        f"{system}\n\n"
        f"Motion: {transcript.topic.motion}\n"
        f"Dimensions: {dims} (scale {config.scoring.scale_min}-{config.scoring.scale_max})\n"
        f"{instructions}\n\n"
        f"Transcript:\n{turns_text}"
    )


def _extract_json_block(text: str) -> Optional[dict]:
    """
    Find the first JSON object in free-form text and parse it. If none found, try YAML.
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        snippet = match.group(0)
        for loader in (json.loads, yaml.safe_load):
            try:
                return loader(snippet)
            except Exception:
                continue
    return None


def _extract_scores_from_text(text: str, dim_ids: List[str], scale_min: int, scale_max: int) -> Optional[Tuple[Dict[str, int], Dict[str, int]]]:
    """
    Best-effort parser for non-JSON replies:
      expects lines like 'pro <dim>: <num>' or '<dim> pro: <num>' etc.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    pro: Dict[str, int] = {}
    con: Dict[str, int] = {}

    def clamp(val):
        try:
            v = float(val)
        except Exception:
            return None
        v = int(round(v))
        return max(scale_min, min(scale_max, v))

    for ln in lines:
        lower = ln.lower()
        for side, bucket in (("pro", pro), ("con", con)):
            if side in lower:
                for dim in dim_ids:
                    if dim in lower:
                        # find last number in line
                        m = re.findall(r"[-+]?[0-9]*\\.?[0-9]+", ln)
                        if m:
                            val = clamp(m[-1])
                            if val is not None:
                                bucket[dim] = val
    if pro and con:
        # fill missing
        for dim in dim_ids:
            pro.setdefault(dim, scale_min)
            con.setdefault(dim, scale_min)
        return pro, con
    return None


def _parse_json_scores(payload: dict, dim_ids: List[str], scale_min: int, scale_max: int) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Lenient parser: accepts ints/floats/strings, case-insensitive dim keys, clamps to range,
    and fills missing dims with scale_min if absent.
    """
    if not isinstance(payload, dict):
        raise ValueError("Judge response is not a JSON object.")
    scores = payload.get("scores") or {}
    pro_scores = scores.get("pro") or payload.get("pro")
    con_scores = scores.get("con") or payload.get("con")
    if not isinstance(pro_scores, dict) or not isinstance(con_scores, dict):
        raise ValueError("Missing scores for pro/con.")

    def normalize_side(side_scores: Dict[str, int]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        # Build a case-insensitive map
        lower_map = {k.lower(): v for k, v in side_scores.items()}
        for dim in dim_ids:
            val = None
            if dim in side_scores:
                val = side_scores[dim]
            elif dim.lower() in lower_map:
                val = lower_map[dim.lower()]
            if val is None:
                # Fill missing with minimum to avoid drop
                val = scale_min
            # Coerce types
            if isinstance(val, str):
                try:
                    val = float(val)
                except Exception:
                    val = scale_min
            if isinstance(val, float):
                val = int(round(val))
            if not isinstance(val, int):
                val = scale_min
            # Clamp
            if val < scale_min:
                val = scale_min
            if val > scale_max:
                val = scale_max
            out[dim] = val
        return out

    return normalize_side(pro_scores), normalize_side(con_scores)


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

    # Single-attempt parse: send prompt once, parse whatever comes back.
    prompt = _build_judge_prompt(transcript, config, reinforce_json=True)
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
    if (not pro_scores or not con_scores) and raw:
        fallback = _extract_scores_from_text(raw, dim_ids, config.scoring.scale_min, config.scoring.scale_max)
        if fallback:
            pro_scores, con_scores = fallback
    if not pro_scores or not con_scores:
        raise RuntimeError("Judge response did not contain usable scores.")

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
