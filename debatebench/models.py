"""
OpenRouter-only model adapters.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import requests
from requests import exceptions as req_exc

from .schema import DebaterModelConfig, JudgeModelConfig, Turn
from .settings import Settings


class ModelAdapter:
    def __init__(self, config):
        self.config = config


class DebaterAdapter(ModelAdapter):
    def generate(self, prompt: str, turns: List[Turn], max_tokens: int | None = None):
        """Return (content, usage_dict)."""
        return "", {}


class JudgeAdapter(ModelAdapter):
    def judge(self, prompt: str):
        """Return (content, usage_dict)."""
        return "", {}


class OpenRouterAdapter(ModelAdapter):
    """
    OpenRouter chat completions adapter with basic retries and 402 downshift.
    """

    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config, api_key: str, site_url: Optional[str], site_name: Optional[str]):
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

    def _request(self, messages: List[Dict[str, str]], temperature: float | None = 0.7, max_tokens: int | None = None):
        # normalize temperature
        try:
            temp_val = float(temperature) if temperature is not None else None
        except (TypeError, ValueError):
            temp_val = None
        # Clamp judge temperature to 0 for deterministic, short answers
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

        # Encourage JSON responses for judges when supported
        if isinstance(self, OpenRouterJudgeAdapter):
            payload.setdefault("response_format", {"type": "json_object"})

        last_err = None
        retried_402 = False
        for attempt in range(1, self.retries + 1):
            try:
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
    def judge(self, prompt: str):
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.0)
        token_limit = self.config.token_limit or params.get("max_tokens") or 256
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature, max_tokens=token_limit)


def build_debater_adapter(config: DebaterModelConfig, settings: Settings) -> DebaterAdapter:
    if config.provider != "openrouter":
        raise ValueError(f"Unsupported provider '{config.provider}'. Only 'openrouter' is supported.")
    return OpenRouterDebaterAdapter(
        config,
        api_key=settings.openrouter_api_key,
        site_url=settings.openrouter_site_url,
        site_name=settings.openrouter_site_name,
    )


def build_judge_adapter(config: JudgeModelConfig, settings: Settings) -> JudgeAdapter:
    if config.provider != "openrouter":
        raise ValueError(f"Unsupported provider '{config.provider}'. Only 'openrouter' is supported.")
    return OpenRouterJudgeAdapter(
        config,
        api_key=settings.openrouter_api_key,
        site_url=settings.openrouter_site_url,
        site_name=settings.openrouter_site_name,
    )


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    import random

    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)
