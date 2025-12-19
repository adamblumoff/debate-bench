"""
Shared helpers for extracting cost metadata from provider usage payloads.
"""
from __future__ import annotations


def extract_cost_fields(usage: dict | None) -> tuple[float | None, str | None, dict | None]:
    if not usage:
        return None, None, None
    cost = usage.get("cost")
    currency = usage.get("currency") or usage.get("cost_currency")
    cost_details = usage.get("cost_details")
    if cost is None or currency is None or cost_details is None:
        raw = usage.get("raw_response") or {}
        raw_usage = raw.get("usage") or {}
        if cost is None:
            cost = raw_usage.get("cost")
        if currency is None:
            currency = raw_usage.get("currency") or raw_usage.get("cost_currency")
        if cost_details is None:
            cost_details = raw_usage.get("cost_details")
    return cost, currency, cost_details
