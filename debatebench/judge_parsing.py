"""
Parsing utilities for judge outputs.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import yaml


def extract_json_block(text: str) -> Optional[dict]:
    """
    Find the first JSON object in free-form text and parse it. If none found, try YAML.
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        payload = yaml.safe_load(text)
        if isinstance(payload, dict):
            return payload
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


def extract_scores_from_text(
    text: str, dim_ids: List[str], scale_min: int, scale_max: int
) -> Optional[Tuple[Dict[str, int], Dict[str, int]]]:
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


def parse_json_scores(
    payload: dict, dim_ids: List[str], scale_min: int, scale_max: int
) -> Tuple[Dict[str, int], Dict[str, int]]:
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

    pro = normalize_side(pro_scores)
    con = normalize_side(con_scores)
    return pro, con


__all__ = ["extract_json_block", "extract_scores_from_text", "parse_json_scores"]
