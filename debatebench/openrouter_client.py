"""
OpenRouter transport client used by adapter classes.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import requests
from requests import exceptions as req_exc

from .openrouter_rate import RateLimitState, parse_retry_after


class OpenRouterClient:
    """
    OpenRouter chat completions client with retries and basic backoff.
    """

    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        config,
        api_key: str,
        site_url: Optional[str],
        site_name: Optional[str],
        include_usage: bool = True,
        rate_state: RateLimitState | None = None,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter provider.")
        if not getattr(config, "endpoint", None):
            config.endpoint = self.DEFAULT_ENDPOINT
        params = config.parameters or {}
        self.config = config
        self.timeout = float(params.get("timeout", 300))  # default 5 minutes
        self.retries = int(params.get("retries", 3))
        self.backoff = float(params.get("backoff", 2.0))
        self.api_key = api_key
        self.site_url = site_url
        self.site_name = site_name
        self.include_usage = include_usage
        self._rate_state = rate_state or RateLimitState()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def request(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float | None = 0.7,
        max_tokens: int | None = None,
        use_structured: bool = True,
        response_format: Optional[Dict] = None,
        is_judge: bool = False,
    ):
        # normalize temperature
        try:
            temp_val = float(temperature) if temperature is not None else None
        except (TypeError, ValueError):
            temp_val = None
        # Clamp judge temperature to 0 for deterministic scoring
        if is_judge:
            temp_val = 0.0

        payload = {
            "model": self.config.model,
            "messages": messages,
        }
        if temp_val is not None:
            payload["temperature"] = temp_val
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Request usage (cost + token) data when enabled; server may omit silently.
        if self.include_usage:
            payload["usage"] = {"include": True}

        if response_format is not None:
            payload["response_format"] = response_format
        elif is_judge and use_structured:
            payload.setdefault(
                "response_format",
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "judge_scores",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "scores": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "pro": {
                                            "type": "object",
                                            "additionalProperties": {"type": "integer"},
                                            "required": [],
                                        },
                                        "con": {
                                            "type": "object",
                                            "additionalProperties": {"type": "integer"},
                                            "required": [],
                                        },
                                    },
                                    "required": ["pro", "con"],
                                },
                            },
                            "required": ["scores"],
                        },
                    },
                },
            )

        last_err = None
        retried_402 = False
        for attempt in range(1, self.retries + 1):
            try:
                self._rate_state.acquire()
                resp = requests.post(
                    self.config.endpoint,
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                message = data["choices"][0].get("message", {})
                content = message.get("content", "")
                reasoning = message.get("reasoning") or message.get("reasoning_content")
                # Some thinking routes place the answer in `reasoning` while leaving `content` empty.
                # Keep reasoning hidden from the main transcript; only fallback when content is empty.
                if (not content) and reasoning:
                    content = reasoning
                meta = {
                    "raw_response": data,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "cost": usage.get("cost"),
                    "currency": usage.get("currency") or usage.get("cost_currency"),
                    "cost_details": usage.get("cost_details"),
                    "reasoning": reasoning,
                }
                return content, meta
            except (req_exc.Timeout, req_exc.ConnectionError) as e:
                last_err = e
                if attempt == self.retries:
                    raise
                time.sleep(self.backoff * attempt)
            except req_exc.HTTPError as e:
                status = e.response.status_code if e.response else None
                body = ""
                try:
                    body = e.response.text if e.response is not None else ""
                except Exception:
                    body = ""
                # If insufficient credits for requested max_tokens, try once with allowed tokens if present.
                if status == 402 and (not retried_402):
                    import re

                    allowed = None
                    m = re.search(r"afford\s+(\d+)", body or "")
                    if m:
                        try:
                            allowed = int(m.group(1))
                        except Exception:
                            allowed = None
                    if allowed and allowed > 0:
                        payload["max_tokens"] = allowed
                        retried_402 = True
                        continue
                if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                    last_err = e
                    if status == 429:
                        retry_after = parse_retry_after(e.response.headers if e.response else {})
                        if retry_after is not None:
                            self._rate_state.note_backoff(retry_after, "429")
                            time.sleep(retry_after)
                        else:
                            backoff = self.backoff * attempt
                            self._rate_state.note_backoff(backoff, "429")
                            time.sleep(backoff)
                    else:
                        backoff = self.backoff * attempt
                        self._rate_state.note_backoff(backoff, "retry")
                        time.sleep(backoff)
                    continue
                detail = f"HTTP {status}"
                if body:
                    detail += f": {body}"
                raise RuntimeError(detail) from e
        raise last_err or RuntimeError("Request failed without exception")


__all__ = ["OpenRouterClient"]
