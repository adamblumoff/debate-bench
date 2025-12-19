#!/usr/bin/env python3
"""Backfill OpenRouter usage costs into a debate JSONL file safely."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import requests

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class BackfillStats:
    records: int = 0
    turns: int = 0
    turns_missing_cost: int = 0
    turns_updated: int = 0
    turns_updated_cost: int = 0
    turns_updated_tokens: int = 0
    turns_updated_currency: int = 0
    turns_updated_cost_details: int = 0
    turns_missing_usage: int = 0
    turns_missing_generation_id: int = 0
    generation_calls: int = 0
    generation_failures: int = 0


def _latest_debates_file(results_dir: Path) -> Path:
    candidates = sorted(results_dir.glob("debates_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No debates_*.jsonl files found in {results_dir}")
    return candidates[-1]


def _default_output_path(input_path: Path) -> Path:
    if input_path.suffix == ".jsonl":
        return input_path.with_name(input_path.stem + "_costs.jsonl")
    return input_path.with_suffix(input_path.suffix + "_costs.jsonl")


def _usage_from_raw(raw_response: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_response, dict):
        return None
    usage = raw_response.get("usage")
    if not isinstance(usage, dict):
        return None
    return usage


def _set_if_missing(obj: Dict[str, Any], key: str, value: Any, overwrite: bool) -> bool:
    if value is None:
        return False
    if overwrite or obj.get(key) is None:
        obj[key] = value
        return True
    return False


def _fill_turn_from_usage(turn: Dict[str, Any], usage: Dict[str, Any], overwrite: bool) -> Tuple[int, int, int, int]:
    changed = 0
    changed_cost = 0
    changed_tokens = 0
    changed_currency = 0
    changed_cost_details = 0

    if _set_if_missing(turn, "prompt_tokens", usage.get("prompt_tokens"), overwrite):
        changed += 1
        changed_tokens += 1
    if _set_if_missing(turn, "completion_tokens", usage.get("completion_tokens"), overwrite):
        changed += 1
        changed_tokens += 1
    if _set_if_missing(turn, "total_tokens", usage.get("total_tokens"), overwrite):
        changed += 1
        changed_tokens += 1

    if _set_if_missing(turn, "cost", usage.get("cost"), overwrite):
        changed += 1
        changed_cost += 1

    currency = usage.get("currency") or usage.get("cost_currency")
    if _set_if_missing(turn, "currency", currency, overwrite):
        changed += 1
        changed_currency += 1

    cost_details = usage.get("cost_details")
    if cost_details is not None and (overwrite or turn.get("cost_details") is None):
        turn["cost_details"] = cost_details
        changed += 1
        changed_cost_details += 1

    return changed, changed_cost, changed_tokens, changed_currency, changed_cost_details


def _fetch_generation(
    session: requests.Session,
    base_url: str,
    api_key: str,
    generation_id: str,
    timeout: float,
) -> Optional[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    resp = session.get(
        f"{base_url.rstrip('/')}/generation",
        params={"id": generation_id},
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    return data


def _fill_turn_from_generation(turn: Dict[str, Any], gen: Dict[str, Any], overwrite: bool) -> Tuple[int, int, int]:
    changed = 0
    changed_cost = 0
    changed_tokens = 0

    cost = gen.get("total_cost")
    if cost is None:
        usage = gen.get("usage")
        if isinstance(usage, dict):
            cost = usage.get("total_cost")
            if cost is None:
                cost = usage.get("cost")
            if cost is None:
                cost = usage.get("total_cost_usd")
        else:
            cost = None
    if _set_if_missing(turn, "cost", cost, overwrite):
        changed += 1
        changed_cost += 1

    prompt_tokens = gen.get("native_tokens_prompt")
    completion_tokens = gen.get("native_tokens_completion")
    total_tokens = gen.get("native_tokens_prompt")
    if total_tokens is not None and completion_tokens is not None:
        total_tokens = total_tokens + completion_tokens
    else:
        total_tokens = None

    if _set_if_missing(turn, "prompt_tokens", prompt_tokens, overwrite):
        changed += 1
        changed_tokens += 1
    if _set_if_missing(turn, "completion_tokens", completion_tokens, overwrite):
        changed += 1
        changed_tokens += 1
    if _set_if_missing(turn, "total_tokens", total_tokens, overwrite):
        changed += 1
        changed_tokens += 1

    cost_details = {
        "upstream_inference_cost": gen.get("upstream_inference_cost"),
        "cache_discount": gen.get("cache_discount"),
        "total_cost": gen.get("total_cost"),
    }
    if any(v is not None for v in cost_details.values()):
        if overwrite or turn.get("cost_details") is None:
            turn["cost_details"] = cost_details
            changed += 1

    return changed, changed_cost, changed_tokens


def _iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)


def _count_missing(path: Path) -> Tuple[int, int]:
    missing_cost = 0
    missing_generation_id = 0
    for rec in _iter_records(path):
        for turn in rec.get("transcript", {}).get("turns", []):
            if turn.get("cost") is not None:
                continue
            usage = _usage_from_raw((turn.get("metadata") or {}).get("raw_response"))
            if usage and usage.get("cost") is not None:
                continue
            missing_cost += 1
            raw = (turn.get("metadata") or {}).get("raw_response")
            gen_id = raw.get("id") if isinstance(raw, dict) else None
            if not gen_id:
                missing_generation_id += 1
    return missing_cost, missing_generation_id


def _configure_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def backfill_costs(
    input_path: Path,
    output_path: Path,
    overwrite: bool,
    use_generation_api: bool,
    max_generation_calls: int,
    base_url: str,
    timeout: float,
    sleep_seconds: float,
    dry_run: bool,
) -> BackfillStats:
    stats = BackfillStats()

    api_key = None
    session = None
    if use_generation_api:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when --use-generation-api is set")
        session = _configure_session()

    writer = None
    if not dry_run:
        writer = output_path.open("w", encoding="utf-8")

    try:
        for rec in _iter_records(input_path):
            stats.records += 1
            transcript = rec.get("transcript") or {}
            turns = transcript.get("turns") or []
            for turn in turns:
                stats.turns += 1
                usage = _usage_from_raw((turn.get("metadata") or {}).get("raw_response"))
                if usage is None:
                    stats.turns_missing_usage += 1
                changed = 0
                if usage is not None:
                    c, c_cost, c_tokens, c_currency, c_details = _fill_turn_from_usage(
                        turn, usage, overwrite
                    )
                    changed += c
                    stats.turns_updated += c
                    stats.turns_updated_cost += c_cost
                    stats.turns_updated_tokens += c_tokens
                    stats.turns_updated_currency += c_currency
                    stats.turns_updated_cost_details += c_details

                if turn.get("cost") is None:
                    stats.turns_missing_cost += 1
                    if use_generation_api:
                        raw = (turn.get("metadata") or {}).get("raw_response")
                        gen_id = raw.get("id") if isinstance(raw, dict) else None
                        if not gen_id:
                            stats.turns_missing_generation_id += 1
                        else:
                            if stats.generation_calls >= max_generation_calls:
                                raise RuntimeError(
                                    f"Generation call cap exceeded ({max_generation_calls}). "
                                    "Rerun with a higher --max-generation-calls."
                                )
                            try:
                                gen = _fetch_generation(session, base_url, api_key, gen_id, timeout)
                                stats.generation_calls += 1
                                if gen:
                                    c, c_cost, c_tokens = _fill_turn_from_generation(turn, gen, overwrite)
                                    changed += c
                                    stats.turns_updated += c
                                    stats.turns_updated_cost += c_cost
                                    stats.turns_updated_tokens += c_tokens
                            except Exception:
                                stats.generation_calls += 1
                                stats.generation_failures += 1
                            if sleep_seconds > 0:
                                time.sleep(sleep_seconds)

            if writer is not None:
                writer.write(json.dumps(rec, ensure_ascii=True) + "\n")
    finally:
        if writer is not None:
            writer.close()
    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input debates JSONL (default: latest debates_*.jsonl under results/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL (default: <input>_costs.jsonl)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing cost/token fields when usage data is present",
    )
    parser.add_argument(
        "--use-generation-api",
        action="store_true",
        help="Use OpenRouter /generation endpoint to backfill missing costs",
    )
    parser.add_argument(
        "--max-generation-calls",
        type=int,
        default=200,
        help="Safety cap for generation API calls (default: 200)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenRouter API base URL (default: https://openrouter.ai/api/v1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout seconds for generation calls",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.1,
        help="Sleep seconds between generation calls (default: 0.1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write output; just report stats",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report path",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    input_path = args.input
    if input_path is None:
        input_path = _latest_debates_file(Path("results"))

    output_path = args.output or _default_output_path(input_path)

    if not input_path.exists():
        parser.error(f"Input not found: {input_path}")

    if not args.dry_run and output_path.exists():
        parser.error(f"Output already exists: {output_path} (use a new path)")

    if args.use_generation_api:
        missing_cost, missing_gen_id = _count_missing(input_path)
        if missing_cost == 0:
            print("No missing costs after local usage scan; skipping generation API.")
            args.use_generation_api = False
        elif missing_cost > args.max_generation_calls:
            parser.error(
                f"Missing costs require {missing_cost} generation calls, "
                f"exceeds cap ({args.max_generation_calls}). "
                "Re-run with a higher --max-generation-calls."
            )
        elif missing_gen_id > 0:
            print(
                f"Warning: {missing_gen_id} turns missing generation IDs; those cannot be backfilled."
            )

    stats = backfill_costs(
        input_path=input_path,
        output_path=output_path,
        overwrite=args.overwrite,
        use_generation_api=args.use_generation_api,
        max_generation_calls=args.max_generation_calls,
        base_url=args.base_url,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
        dry_run=args.dry_run,
    )

    summary = {
        "input": str(input_path),
        "output": None if args.dry_run else str(output_path),
        "records": stats.records,
        "turns": stats.turns,
        "turns_missing_cost": stats.turns_missing_cost,
        "turns_updated": stats.turns_updated,
        "turns_updated_cost": stats.turns_updated_cost,
        "turns_updated_tokens": stats.turns_updated_tokens,
        "turns_updated_currency": stats.turns_updated_currency,
        "turns_updated_cost_details": stats.turns_updated_cost_details,
        "turns_missing_usage": stats.turns_missing_usage,
        "turns_missing_generation_id": stats.turns_missing_generation_id,
        "generation_calls": stats.generation_calls,
        "generation_failures": stats.generation_failures,
    }

    print(json.dumps(summary, indent=2))

    if args.report:
        args.report.write_text(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
