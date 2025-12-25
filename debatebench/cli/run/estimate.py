"""Time and cost estimation helpers for `debatebench run`."""
from __future__ import annotations

import json
import statistics
import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, Iterable, Any

import requests

from ...storage import load_debate_records


def format_duration(seconds: float) -> str:
    """Pretty-print seconds as human-friendly duration."""
    if seconds < 1:
        return f"{seconds*1000:.0f} ms"
    delta = timedelta(seconds=int(seconds))
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if delta.days:
        parts.append(f"{delta.days}d")
    if hours or delta.days:
        parts.append(f"{hours}h")
    if minutes or hours or delta.days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def historical_debate_durations(results_dir: Path, max_files: int = 5, max_records: int = 500) -> Tuple[float | None, int]:
    """
    Return (median_total_seconds, num_records) from recent debate files.
    Total seconds = sum(turn.duration_ms) + sum(judge.latency_ms) for each debate.
    """
    totals = []
    files = sorted(results_dir.glob("debates_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for idx, path in enumerate(files):
        try:
            records = load_debate_records(path)
        except Exception:
            continue
        for rec in records:
            turn_ms = sum(t.duration_ms or 0 for t in rec.transcript.turns)
            judge_ms = sum(j.latency_ms or 0 for j in rec.judges)
            total_ms = turn_ms + judge_ms
            if total_ms > 0:
                totals.append(total_ms / 1000.0)
            if len(totals) >= max_records:
                break
        if len(totals) >= max_records:
            break
        if idx + 1 >= max_files:
            break
    if not totals:
        return None, 0
    return statistics.median(totals), len(totals)


def _percentile(values: Iterable[float], pct: float) -> float:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    idx = min(len(vals) - 1, max(0, int(round(pct * (len(vals) - 1)))))
    return vals[idx]


def write_timing_snapshot(
    debates_path: Path,
    out_path: Path,
    run_tag: str,
    max_workers: int,
    per_model_cap: int,
) -> None:
    if not debates_path.exists():
        return
    try:
        records = load_debate_records(debates_path)
    except Exception:
        return

    debate_totals = []
    model_stage: Dict[str, Dict[str, list[float]]] = {}
    judge_lat: Dict[str, list[float]] = {}

    for rec in records:
        tr = rec.transcript
        turn_ms = 0.0
        for t in tr.turns:
            ms = t.duration_ms or 0.0
            turn_ms += ms
            model_id = tr.pro_model_id if t.speaker == "pro" else tr.con_model_id
            if not model_id:
                continue
            bucket = model_stage.setdefault(model_id, {})
            bucket.setdefault(t.stage, []).append(ms / 1000.0)
            bucket.setdefault("_all", []).append(ms / 1000.0)
        judge_ms = 0.0
        for j in rec.judges:
            if j.latency_ms is None:
                continue
            judge_ms += j.latency_ms
            judge_lat.setdefault(j.judge_id, []).append(j.latency_ms / 1000.0)
        total_ms = turn_ms + judge_ms
        if total_ms > 0:
            debate_totals.append(total_ms / 1000.0)

    def _summarize(vals: Iterable[float]) -> Dict[str, float]:
        vlist = list(vals)
        return {
            "p50": _percentile(vlist, 0.50),
            "p75": _percentile(vlist, 0.75),
            "p90": _percentile(vlist, 0.90),
            "n": float(len(vlist)),
        }

    model_summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for mid, stage_map in model_stage.items():
        model_summary[mid] = {stage: _summarize(vals) for stage, vals in stage_map.items()}

    judge_summary = {jid: _summarize(vals) for jid, vals in judge_lat.items()}

    payload: Dict[str, Any] = {
        "run_tag": run_tag,
        "debates_path": str(debates_path),
        "created_at": time.time(),
        "max_workers": max_workers,
        "per_model_cap": per_model_cap,
        "debate_totals": _summarize(debate_totals),
        "model_stage_latencies": model_summary,
        "judge_latencies": judge_summary,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_timing_snapshots(results_dir: Path, max_files: int = 10) -> list[Dict[str, Any]]:
    snapshots = sorted(results_dir.glob("run_*/timing_snapshot.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for path in snapshots[:max_files]:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def estimate_wall_time(
    tasks,
    rounds,
    max_workers: int,
    per_model_cap: int,
    snapshots: list[Dict[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, str]]:
    model_stage = {}
    judge_lat = {}
    snap_models = set()
    snap_judges = set()
    debate_totals = []
    for snap in snapshots:
        ms = snap.get("model_stage_latencies", {}) or {}
        jl = snap.get("judge_latencies", {}) or {}
        model_stage.update(ms)
        judge_lat.update(jl)
        snap_models.update(ms.keys())
        snap_judges.update(jl.keys())
        dt = snap.get("debate_totals") or {}
        if dt.get("p50"):
            debate_totals.append(float(dt["p50"]))

    def get_model_stage(mid: str, stage: str, pct: str) -> float:
        data = model_stage.get(mid, {})
        if stage in data and pct in data[stage]:
            return float(data[stage][pct])
        if "_all" in data and pct in data["_all"]:
            return float(data["_all"][pct])
        return 0.0

    def get_judge(jid: str, pct: str) -> float:
        data = judge_lat.get(jid, {})
        if pct in data:
            return float(data[pct])
        return 0.0

    def debate_time(task, pct: str) -> float:
        total = 0.0
        for round_cfg in rounds:
            model_id = task.pro_model.id if round_cfg.speaker == "pro" else task.con_model.id
            total += get_model_stage(model_id, round_cfg.stage, pct)
        for j in task.panel_configs:
            total += get_judge(j.id, pct)
        return total

    if not snapshots:
        # Fallback: median per debate from recent history.
        fallback = statistics.median(debate_totals) if debate_totals else 60.0
        return {
            "p50": fallback,
            "p75": fallback * 1.2,
            "p90": fallback * 1.4,
        }, {"source": "fallback"}

    required_models = {t.pro_model.id for t in tasks} | {t.con_model.id for t in tasks}
    required_judges = {j.id for t in tasks for j in t.panel_configs}
    model_coverage = len(required_models & snap_models) / max(1, len(required_models))
    judge_coverage = len(required_judges & snap_judges) / max(1, len(required_judges))
    if model_coverage < 0.7 or judge_coverage < 0.7:
        fallback = statistics.median(debate_totals) if debate_totals else 60.0
        return {
            "p50": fallback,
            "p75": fallback * 1.2,
            "p90": fallback * 1.4,
        }, {
            "source": "fallback",
            "coverage_models": f"{model_coverage:.2f}",
            "coverage_judges": f"{judge_coverage:.2f}",
        }

    totals = {pct: 0.0 for pct in ("p50", "p75", "p90")}
    per_model_work = {pct: {} for pct in ("p50", "p75", "p90")}
    for task in tasks:
        for pct in ("p50", "p75", "p90"):
            t = debate_time(task, pct)
            totals[pct] += t
            for round_cfg in rounds:
                model_id = task.pro_model.id if round_cfg.speaker == "pro" else task.con_model.id
                per_model_work[pct][model_id] = per_model_work[pct].get(model_id, 0.0) + get_model_stage(
                    model_id, round_cfg.stage, pct
                )
            for j in task.panel_configs:
                per_model_work[pct][j.id] = per_model_work[pct].get(j.id, 0.0) + get_judge(j.id, pct)

    estimates = {}
    for pct in ("p50", "p75", "p90"):
        total_work = totals[pct]
        global_time = total_work / max(1, max_workers)
        model_times = [
            work / max(1, per_model_cap) for work in per_model_work[pct].values()
        ]
        bottleneck = max(model_times) if model_times else 0.0
        estimates[pct] = max(global_time, bottleneck)

    meta = {
        "source": "snapshots",
        "max_workers": str(max_workers),
        "per_model_cap": str(per_model_cap),
        "coverage_models": f"{model_coverage:.2f}",
        "coverage_judges": f"{judge_coverage:.2f}",
    }
    return estimates, meta


def fetch_pricing(models_needed: set[str], settings) -> Dict[str, Tuple[float, float]]:
    """
    Returns map model_id -> (prompt_price_per_token, completion_price_per_token) by hitting OpenRouter.
    Falls back to an empty mapping if the API fails; caller should handle missing entries.
    """
    pricing: Dict[str, Tuple[float, float]] = {}
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Accept": "application/json"}
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_site_name:
        headers["X-Title"] = settings.openrouter_site_name
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json().get("data", [])
        for entry in payload:
            mid = entry.get("id")
            if mid in models_needed:
                pr = entry.get("pricing") or {}
                p = float(pr.get("prompt")) if pr.get("prompt") not in (None, "") else None
                c = float(pr.get("completion")) if pr.get("completion") not in (None, "") else None
                if p is not None and c is not None:
                    pricing[mid] = (p, c)
    except Exception:
        return {}
    return pricing


def load_activity_pricing(activity_path: Optional[Path] = None) -> Tuple[Dict[str, Tuple[float, float]], Optional[Path]]:
    """
    Build per-model prompt/completion token rates from an OpenRouter activity JSON.
    Uses a blended rate: usage / (prompt+completion+reasoning tokens).
    """
    if activity_path is None:
        candidates = sorted(Path("results").glob("openrouter_activity_*.json"))
        if not candidates:
            return {}, None
        activity_path = candidates[-1]
    if not activity_path.exists():
        return {}, None

    try:
        raw = json.loads(activity_path.read_text())
        records = raw.get("data") if isinstance(raw, dict) else raw
    except Exception:
        return {}, None
    if not isinstance(records, list):
        return {}, None

    agg: Dict[str, Dict[str, float]] = {}
    for rec in records:
        try:
            model = rec.get("model") or rec.get("model_permaslug")
            usage = float(rec.get("usage", 0) or 0.0)
            pt = int(rec.get("prompt_tokens", 0) or 0)
            ct = int(rec.get("completion_tokens", 0) or 0)
            rt = int(rec.get("reasoning_tokens", 0) or 0)
        except Exception:
            continue
        if not model or usage <= 0:
            continue
        bucket = agg.setdefault(model, {"usage": 0.0, "pt": 0, "ct": 0, "rt": 0})
        bucket["usage"] += usage
        bucket["pt"] += pt
        bucket["ct"] += ct
        bucket["rt"] += rt

    pricing: Dict[str, Tuple[float, float]] = {}
    for model, vals in agg.items():
        total_tokens = vals["pt"] + vals["ct"] + vals["rt"]
        if total_tokens <= 0:
            continue
        rate = vals["usage"] / total_tokens
        pricing[model] = (rate, rate)
    return pricing, activity_path


def load_token_stats(debates_path: Optional[Path] = None):
    """
    Load historical average prompt/completion tokens per debater and judge from the
    most recent debates_*.jsonl (or a specific path if provided).
    Returns (debater_stats, judge_stats, source_path)
    debater_stats: model_id -> {"prompt_avg": float, "completion_avg": float}
    judge_stats: judge_id -> {"prompt_avg": float, "completion_avg": float}
    """
    if debates_path is None:
        candidates = sorted(Path("results").glob("debates_*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return {}, {}, None
        debates_path = candidates[-1]

    debater_totals: Dict[str, Dict[str, float]] = {}
    debater_counts: Dict[str, int] = {}
    judge_totals: Dict[str, Dict[str, float]] = {}
    judge_counts: Dict[str, int] = {}
    judge_samples: Dict[str, Dict[str, list[float]]] = {}

    try:
        with debates_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                tr = rec.get("transcript") or {}
                for turn in tr.get("turns", []):
                    pt = turn.get("prompt_tokens")
                    ct = turn.get("completion_tokens")
                    if pt is None or ct is None:
                        continue
                    speaker = turn.get("speaker")
                    mid = tr.get("pro_model_id") if speaker == "pro" else tr.get("con_model_id")
                    if not mid:
                        continue
                    agg = debater_totals.setdefault(mid, {"pt": 0.0, "ct": 0.0})
                    agg["pt"] += pt
                    agg["ct"] += ct
                    debater_counts[mid] = debater_counts.get(mid, 0) + 1
                for jres in rec.get("judges", []):
                    pid = jres.get("judge_id")
                    pt = jres.get("prompt_tokens")
                    ct = jres.get("completion_tokens")
                    if pid is None or pt is None or ct is None:
                        continue
                    agg = judge_totals.setdefault(pid, {"pt": 0.0, "ct": 0.0})
                    agg["pt"] += pt
                    agg["ct"] += ct
                    judge_counts[pid] = judge_counts.get(pid, 0) + 1
                    samples = judge_samples.setdefault(pid, {"pt": [], "ct": []})
                    samples["pt"].append(pt)
                    samples["ct"].append(ct)
    except Exception:
        return {}, {}, None

    debater_stats = {}
    for mid, totals in debater_totals.items():
        n = debater_counts.get(mid, 0)
        if n:
            debater_stats[mid] = {
                "prompt_avg": totals["pt"] / n,
                "completion_avg": totals["ct"] / n,
            }
    judge_stats = {}
    for pid, totals in judge_totals.items():
        n = judge_counts.get(pid, 0)
        if n:
            def pct(vals: list[float], p: float) -> float:
                if not vals:
                    return 0.0
                s = sorted(vals)
                if len(s) == 1:
                    return s[0]
                idx = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
                return s[idx]

            def median(vals: list[float]) -> float:
                if not vals:
                    return 0.0
                s = sorted(vals)
                k = len(s)
                mid = k // 2
                if k % 2:
                    return s[mid]
                return 0.5 * (s[mid - 1] + s[mid])

            samples = judge_samples.get(pid, {"pt": [], "ct": []})
            prompt_raw = pct(samples.get("pt", []), 0.10) if samples.get("pt") else totals["pt"] / n
            completion_raw = pct(samples.get("ct", []), 0.10) if samples.get("ct") else totals["ct"] / n
            prompt_med = median(samples.get("pt", [])) if samples.get("pt") else prompt_raw
            completion_med = median(samples.get("ct", [])) if samples.get("ct") else completion_raw
            prompt_capped = min(prompt_raw, prompt_med, 1500.0)
            completion_capped = min(completion_raw, completion_med, 250.0)
            judge_stats[pid] = {
                "prompt_avg": prompt_capped,
                "completion_avg": completion_capped,
            }
    return debater_stats, judge_stats, debates_path


def estimate_cost(
    debaters,
    judges,
    rounds,
    num_topics,
    debates_per_pair,
    balanced,
    pairs,
    pricing_override: Optional[Dict[str, Tuple[float, float]]] = None,
    token_stats: Optional[Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]] = None,
):
    """
    Rough cost estimator using live OpenRouter pricing (USD per token) when available.
    Token model:
      - Debater: completion tokens = sum(token_limit for its stages); prompt tokens ~= sum(history before each turn)
        approximated as completion_total + (completion_total - first_turn_tokens)
      - Judge: prompt tokens = sum(token_limit for all turns); completion ~200 tokens JSON
    """
    models_needed = {m.model for m in debaters} | {j.model for j in judges}
    pricing = pricing_override or {}

    def side_token_budget():
        limits = [r.token_limit for r in rounds if r.speaker == "pro"]
        limits = [l for l in limits if isinstance(l, (int, float))]
        if not limits:
            return 0, 0
        comp = sum(limits)
        first_turn = limits[0]
        prompt = comp + max(0, comp - first_turn)
        return prompt, comp

    turns_per_side = len([r for r in rounds if r.speaker == "pro"])

    prompt_side, comp_side = side_token_budget()
    debater_stats = token_stats[0] if token_stats else {}
    judge_stats = token_stats[1] if token_stats else {}
    per_model_cost: Dict[str, float] = {}
    total_debater_cost = 0.0
    debates_per_pair_total = debates_per_pair * num_topics
    for a, b in pairs:
        for model, tokens in ((a, (prompt_side, comp_side)), (b, (prompt_side, comp_side))):
            if model.id in debater_stats:
                prompt_tokens = debater_stats[model.id]["prompt_avg"] * turns_per_side
                comp_tokens = debater_stats[model.id]["completion_avg"] * turns_per_side
            else:
                prompt_tokens, comp_tokens = tokens
            rates = pricing.get(model.model)
            if not rates:
                continue
            p_rate, c_rate = rates
            cost = prompt_tokens * p_rate + comp_tokens * c_rate
            per_model_cost[model.id] = per_model_cost.get(model.id, 0.0) + cost * debates_per_pair_total
            total_debater_cost += cost * debates_per_pair_total

    transcript_tokens = sum(r.token_limit for r in rounds if isinstance(r.token_limit, (int, float)))
    judge_output_tokens = 200
    per_judge_cost: Dict[str, float] = {}
    total_judge_cost = 0.0
    judge_calls = len(pairs) * debates_per_pair_total
    for j in judges:
        if j.id in judge_stats:
            prompt_tokens = judge_stats[j.id]["prompt_avg"]
            comp_tokens = judge_stats[j.id]["completion_avg"]
        else:
            prompt_tokens = transcript_tokens
            comp_tokens = judge_output_tokens
        rates = pricing.get(j.model)
        if not rates:
            continue
        p_rate, c_rate = rates
        cost = prompt_tokens * p_rate + comp_tokens * c_rate
        per_judge_cost[j.id] = cost * judge_calls
        total_judge_cost += cost * judge_calls

    return total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost


__all__ = [
    "format_duration",
    "historical_debate_durations",
    "write_timing_snapshot",
    "load_timing_snapshots",
    "estimate_wall_time",
    "fetch_pricing",
    "load_activity_pricing",
    "load_token_stats",
    "estimate_cost",
]
