"""
Helpers for interacting with the OpenRouter model catalog.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import requests
from requests import exceptions as req_exc


def fetch_recent_openrouter_models(
    months: int,
    api_key: str,
    site_url: Optional[str] = None,
    site_name: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch the OpenRouter model catalog and return entries created within the last `months`.
    Returns a list of dicts with at least `id` and `created` keys, sorted by newest first.
    """
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required to fetch OpenRouter models.")

    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-Title"] = site_name

    try:
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
    except req_exc.RequestException as e:
        raise RuntimeError(f"Failed to fetch OpenRouter models: {e}") from e

    payload = resp.json()
    data = payload.get("data") or []
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    filtered: List[Dict] = []
    for entry in data:
        created_ts = entry.get("created")
        if created_ts is None:
            continue
        created_dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)
        if created_dt < cutoff:
            continue

        arch = entry.get("architecture") or {}
        input_modalities = arch.get("input_modalities") or []
        output_modalities = arch.get("output_modalities") or []

        # Only keep models that accept text input AND produce text output.
        if "text" not in input_modalities or "text" not in output_modalities:
            continue

        filtered.append(
            {
                "id": entry.get("id"),
                "created": created_dt,
                "name": entry.get("name") or entry.get("id"),
            }
        )

    filtered.sort(key=lambda e: e["id"] or "")
    return filtered


def probe_model(
    model_id: str,
    api_key: str,
    site_url: Optional[str] = None,
    site_name: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Send a minimal 1-token request to verify the model is usable.
    Returns None on success (HTTP 200); otherwise returns the response text for logging.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-Title"] = site_name

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except req_exc.RequestException as e:
        return str(e)

    if resp.status_code == 200:
        return None
    return resp.text or f"HTTP {resp.status_code}"
