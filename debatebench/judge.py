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
from .debate import _extract_cost_fields


def _build_judge_prompt(
    transcript: Transcript,
    config: MainConfig,
    reinforce_json: bool = False,
    template_hint: Optional[str] = None,
) -> str:
    turns_text = "\n".join(
        f"{t.speaker.upper()} ({t.stage}): {t.content}" for t in transcript.turns
    )
    dim_ids = [d.id for d in config.scoring.dimensions]
    dims = ", ".join(dim_ids)
    system = config.judge_system_prompt or (
        "You are an expert debate adjudicator. Read the transcript and output ONLY a JSON object with per-dimension integer scores; winner will be derived from the scores."
    )
    instructions = (
        f"Return EXACTLY one JSON object and nothing else. Keys: scores.pro and scores.con. "
        f"Include dimensions: {dims}, each an integer {config.scoring.scale_min}-{config.scoring.scale_max}. "
        f"No rationale, no markdown, no code fences, and do NOT declare a winner. If you include any text outside the JSON object, the answer will be discarded."
    )
    if reinforce_json:
        example_obj = {
            "scores": {
                "pro": {d: config.scoring.scale_min for d in dim_ids},
                "con": {d: config.scoring.scale_min for d in dim_ids},
            }
        }
        import json as _json

        example_json = _json.dumps(example_obj, separators=(",", ":"))
        instructions += (
            " JSON only. No prose. No thinking. Use exactly these keys. Example: "
            f"{example_json}"
        )
    if template_hint:
        instructions += f" Fill this JSON skeleton with your integer scores and return ONLY the completed JSON: {template_hint}"
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
      accepts only explicit side/dimension/number patterns; avoids loose planning text.
      Handles:
        - 'pro persuasiveness: 7'
        - 'persuasiveness pro: 7'
        - 'persuasiveness scores for PRO and CON are 8 and 7'
        - 'persuasiveness pro 8 con 7'
    """
    body = text
    pro: Dict[str, int] = {}
    con: Dict[str, int] = {}

    def clamp(val):
        try:
            v = float(val)
        except Exception:
            return None
        v = int(round(v))
        return max(scale_min, min(scale_max, v))

    for dim in dim_ids:
        if dim in pro and dim in con:
            continue
        patterns = [
            rf"\b{dim}\b[^0-9]{{0,40}}?\bpro\b[^0-9]{{0,10}}?(\d+)[^0-9]{{0,20}}?\bcon\b[^0-9]{{0,10}}?(\d+)",
            rf"\b{dim}\b[^0-9]{{0,40}}?\bcon\b[^0-9]{{0,10}}?(\d+)[^0-9]{{0,20}}?\bpro\b[^0-9]{{0,10}}?(\d+)",
            rf"\b{dim}\b[^0-9]{{0,20}}?\bscores?\b[^0-9]{{0,20}}?for\b[^0-9]{{0,10}}?\bpro\b[^0-9]{{0,10}}?(\d+)[^0-9]{{0,20}}?\bcon\b[^0-9]{{0,10}}?(\d+)",
            rf"\bpro\b[^0-9]{{0,10}}?\b{dim}\b[^0-9]{{0,10}}?[:=]\s*(\d+)",
            rf"\bcon\b[^0-9]{{0,10}}?\b{dim}\b[^0-9]{{0,10}}?[:=]\s*(\d+)",
        ]
        for pat in patterns:
            m = re.search(pat, body, re.IGNORECASE)
            if not m:
                continue
            if len(m.groups()) == 2:
                p_val = clamp(m.group(1))
                c_val = clamp(m.group(2))
                if p_val is not None and c_val is not None:
                    pro[dim] = p_val
                    con[dim] = c_val
                break
            if len(m.groups()) == 1:
                v = clamp(m.group(1))
                if v is not None:
                    if "pro" in pat:
                        pro[dim] = v
                    else:
                        con[dim] = v
                break

    # Structured "PRO: dim X, dim Y" blocks
    block_pro = re.search(r"\bPRO\b[:\-]\s*(.*?)(?:\n\n|\Z)", body, re.IGNORECASE | re.S)
    block_con = re.search(r"\bCON\b[:\-]\s*(.*?)(?:\n\n|\Z)", body, re.IGNORECASE | re.S)
    if block_pro and block_con:
        for dim in dim_ids:
            mpro = re.search(rf"{dim}[^0-9]{{0,10}}(\d+)", block_pro.group(1), re.IGNORECASE)
            mcon = re.search(rf"{dim}[^0-9]{{0,10}}(\d+)", block_con.group(1), re.IGNORECASE)
            if mpro:
                v = clamp(mpro.group(1))
                if v is not None:
                    pro[dim] = v
            if mcon:
                v = clamp(mcon.group(1))
                if v is not None:
                    con[dim] = v

    # Only accept if every dimension was captured for both sides.
    if all(dim in pro for dim in dim_ids) and all(dim in con for dim in dim_ids):
        return pro, con
    return None


def _parse_json_scores(payload: dict, dim_ids: List[str], scale_min: int, scale_max: int) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Lenient parser: accepts ints/floats/strings, case-insensitive dim keys, clamps to range,
    and rejects responses that omit any required dimension.
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
                raise ValueError(f"Missing score for dimension '{dim}'.")
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
    raw = ""
    usage = {}
    latency_ms = None
    pro_scores: Dict[str, int] = {}
    con_scores: Dict[str, int] = {}

    template_hint = None
    if dim_ids:
        template_obj = {
            "scores": {
                "pro": {d: config.scoring.scale_min for d in dim_ids},
                "con": {d: config.scoring.scale_min for d in dim_ids},
            }
        }
        import json as _json

        template_hint = _json.dumps(template_obj, separators=(",", ":"))

    attempts = [
        {"structured": True, "reinforce_json": True, "format_hint": None, "template": template_hint},
        {"structured": True, "reinforce_json": True, "format_hint": "json_object", "template": template_hint},
    ]

    last_error: Optional[Exception] = None
    for attempt in attempts:
        prompt = _build_judge_prompt(
            transcript,
            config,
            reinforce_json=attempt["reinforce_json"],
            template_hint=attempt["template"],
        )
        t0 = time.perf_counter()
        try:
            raw, usage = adapter.judge(
                prompt,
                structured=attempt["structured"],
                dim_ids=dim_ids,
                format_hint=attempt["format_hint"],  # type: ignore[arg-type]
            )
        except Exception as e:
            last_error = e
            continue
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
        if pro_scores and con_scores:
            # Drop degenerate all-minimum outputs (often from thinking-only replies).
            all_min = all(v == config.scoring.scale_min for v in pro_scores.values()) and all(
                v == config.scoring.scale_min for v in con_scores.values()
            )
            if all_min:
                pro_scores, con_scores = {}, {}
                last_error = RuntimeError("Judge returned all-min scores (likely no usable JSON).")
                continue
            break

    if not pro_scores or not con_scores:
        if last_error:
            raise RuntimeError(f"Judge response did not contain usable JSON scores. Raw: {raw}") from last_error
        raise RuntimeError(f"Judge response did not contain usable JSON scores. Raw: {raw}")

    # Derive winner from mean dimension scores
    pro_avg = sum(pro_scores.values()) / len(pro_scores)
    con_avg = sum(con_scores.values()) / len(con_scores)
    if pro_avg > con_avg:
        winner = "pro"
    elif con_avg > pro_avg:
        winner = "con"
    else:
        winner = "tie"

    cost, currency, cost_details = _extract_cost_fields(usage if usage else None)
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
        cost=cost,
        currency=currency,
        cost_details=cost_details,
        metadata={
            "raw_response": usage.get("raw_response"),
            "reasoning": usage.get("reasoning"),
        }
        if usage
        else None,
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
    candidate_adapters: List[JudgeAdapter],
    transcript: Transcript,
    config: MainConfig,
    expected: int,
    usage: Optional[Dict[str, int]] = None,
    seed: int | None = None,
    log=None,
    failed_judges_sink=None,
) -> Tuple[List[JudgeResult], AggregatedResult]:
    """
    Try candidates in order until `expected` valid judge results are collected.
    Falls back through the remaining candidates; raises if we cannot reach the
    target count.
    """
    rng = None
    if seed is not None:
        import random

        rng = random.Random(seed)

    def sort_key(adapter: JudgeAdapter):
        count = usage.get(adapter.config.id, 0) if usage is not None else 0
        tie = rng.random() if rng else 0.0
        return (count, tie, adapter.config.id)

    queue = sorted(candidate_adapters, key=sort_key)
    results: List[JudgeResult] = []
    tried: set[str] = set()

    for adapter in queue:
        if adapter.config.id in tried:
            continue
        tried.add(adapter.config.id)
        try:
            res = run_single_judge(adapter, transcript, config)
            results.append(res)
            if usage is not None:
                usage[adapter.config.id] = usage.get(adapter.config.id, 0) + 1
        except Exception as e:
            if log:
                log(f"[yellow]Judge {adapter.config.id} dropped: {e}[/yellow]")
            if failed_judges_sink:
                failed_judges_sink(
                    {
                        "judge_id": adapter.config.id,
                        "error": str(e),
                    }
                )
            continue
        if len(results) >= expected:
            break

    if len(results) < expected:
        raise RuntimeError(f"Collected {len(results)} of {expected} judges.")

    aggregate = aggregate_panel(results)
    return results, aggregate
