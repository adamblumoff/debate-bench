"""
OpenRouter-only model adapters.
"""
from __future__ import annotations

import time
import threading
from typing import Dict, List, Optional

import requests
from requests import exceptions as req_exc

from .schema import DebaterModelConfig, JudgeModelConfig, Turn
from .settings import Settings


class _RateLimiter:
    def __init__(self, max_rpm: int):
        self.max_rpm = max(1, max_rpm)
        self.tokens = float(self.max_rpm)
        self.refill_rate = self.max_rpm / 60.0
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.updated
                if elapsed > 0:
                    self.tokens = min(
                        float(self.max_rpm), self.tokens + elapsed * self.refill_rate
                    )
                    self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait_for = (1 - self.tokens) / self.refill_rate if self.refill_rate > 0 else 1.0
            time.sleep(min(wait_for, 1.0))


def _parse_retry_after(headers: Dict[str, str]) -> float | None:
    if not headers:
        return None
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if not retry_after:
        return None
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        return None


class ModelAdapter:
    def __init__(self, config):
        self.config = config


class DebaterAdapter(ModelAdapter):
    def generate(self, prompt: str, turns: List[Turn], max_tokens: int | None = None):
        """Return (content, usage_dict)."""
        return "", {}


class JudgeAdapter(ModelAdapter):
    def judge(
        self,
        prompt: str,
        structured: bool = True,
        dim_ids: Optional[List[str]] = None,
        format_hint: Optional[str] = None,
    ):
        """Return (content, usage_dict)."""
        return "", {}


class OpenRouterAdapter(ModelAdapter):
    """
    OpenRouter chat completions adapter with basic retries and 402 downshift.
    """

    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    _rate_limiter = None

    @classmethod
    def configure_rate_limiter(cls, max_rpm: int | None) -> None:
        if max_rpm is None:
            cls._rate_limiter = None
        else:
            cls._rate_limiter = _RateLimiter(max_rpm)

    def __init__(
        self,
        config,
        api_key: str,
        site_url: Optional[str],
        site_name: Optional[str],
        include_usage: bool = True,
    ):
        super().__init__(config)
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter provider.")
        if not getattr(config, "endpoint", None):
            config.endpoint = self.DEFAULT_ENDPOINT
        params = self.config.parameters or {}
        self.timeout = float(params.get("timeout", 300))  # default 5 minutes
        self.retries = int(params.get("retries", 3))
        self.backoff = float(params.get("backoff", 2.0))
        self.api_key = api_key
        self.site_url = site_url
        self.site_name = site_name
        self.include_usage = include_usage

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

    def _request(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = 0.7,
        max_tokens: int | None = None,
        use_structured: bool = True,
        response_format: Optional[Dict] = None,
    ):
        # normalize temperature
        try:
            temp_val = float(temperature) if temperature is not None else None
        except (TypeError, ValueError):
            temp_val = None
        # Clamp judge temperature to 0 for deterministic scoring
        if isinstance(self, OpenRouterJudgeAdapter):
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

        # Encourage JSON responses for judges using structured outputs
        if response_format is not None:
            payload["response_format"] = response_format
        elif isinstance(self, OpenRouterJudgeAdapter) and use_structured:
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
                if self._rate_limiter is not None:
                    self._rate_limiter.acquire()
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
                    m = re.search(r"afford\\s+(\\d+)", body or "")
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
                        retry_after = _parse_retry_after(e.response.headers if e.response else {})
                        if retry_after is not None:
                            time.sleep(retry_after)
                        else:
                            time.sleep(self.backoff * attempt)
                    else:
                        time.sleep(self.backoff * attempt)
                    continue
                detail = f"HTTP {status}"
                if body:
                    detail += f": {body}"
                raise RuntimeError(detail) from e
        raise last_err or RuntimeError("Request failed without exception")


class OpenRouterDebaterAdapter(OpenRouterAdapter, DebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn], max_tokens: int | None = None):
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.7)
        token_limit = max_tokens or self.config.token_limit or params.get("max_tokens") or 1024
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature, max_tokens=token_limit)


class OpenRouterJudgeAdapter(OpenRouterAdapter, JudgeAdapter):
    def judge(
        self,
        prompt: str,
        structured: bool = True,
        dim_ids: Optional[List[str]] = None,
        format_hint: Optional[str] = None,
    ):
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.0)
        token_limit = self.config.token_limit or params.get("max_tokens")
        messages = [
            {
                "role": "system",
                "content": "You are a strict JSON emitter. Reply with JSON only, no markdown or prose.",
            },
            {"role": "user", "content": prompt},
        ]

        response_format = None
        if structured:
            dims = dim_ids or []
            # Build a strict schema that enumerates required dimensions so OpenAI accepts it.
            dim_props = {d: {"type": "integer"} for d in dims}
            response_format = {
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
                                        "properties": dim_props,
                                        "required": dims,
                                        "additionalProperties": False,
                                    },
                                    "con": {
                                        "type": "object",
                                        "properties": dim_props,
                                        "required": dims,
                                        "additionalProperties": False,
                                    },
                                },
                                "required": ["pro", "con"],
                                "additionalProperties": False,
                            }
                        },
                        "required": ["scores"],
                        "additionalProperties": False,
                    },
                },
            }
        elif format_hint == "json_object":
            response_format = {"type": "json_object"}

        return self._request(
            messages,
            temperature=temperature,
            max_tokens=token_limit,
            use_structured=structured,
            response_format=response_format,
        )


def build_debater_adapter(config: DebaterModelConfig, settings: Settings) -> DebaterAdapter:
    if config.provider != "openrouter":
        raise ValueError(f"Unsupported provider '{config.provider}'. Only 'openrouter' is supported.")
    return OpenRouterDebaterAdapter(
        config,
        api_key=settings.openrouter_api_key,
        site_url=settings.openrouter_site_url,
        site_name=settings.openrouter_site_name,
        include_usage=settings.capture_usage_costs,
    )


def build_judge_adapter(config: JudgeModelConfig, settings: Settings) -> JudgeAdapter:
    if config.provider != "openrouter":
        raise ValueError(f"Unsupported provider '{config.provider}'. Only 'openrouter' is supported.")
    return OpenRouterJudgeAdapter(
        config,
        api_key=settings.openrouter_api_key,
        site_url=settings.openrouter_site_url,
        site_name=settings.openrouter_site_name,
        include_usage=settings.capture_usage_costs,
    )


def configure_openrouter_rate_limit(max_rpm: int | None) -> None:
    OpenRouterAdapter.configure_rate_limiter(max_rpm)


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    import random

    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)
