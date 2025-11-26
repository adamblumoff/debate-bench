"""
Model adapter interfaces and implementations.
"""
from __future__ import annotations

import json
import random
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
    def generate(self, prompt: str, turns: List[Turn]):
        """Return (content, usage_dict)."""
        history_snippet = " ".join(t.speaker for t in turns[-4:]) if turns else ""
        return f"[stub:{self.config.id}] Responding as {history_snippet or 'start'}: {prompt}", {}


class JudgeAdapter(ModelAdapter):
    def judge(self, prompt: str):
        """Return (content, usage_dict)."""
        return f'{{"winner": "tie", "pro": {{}}, "con": {{}}, "notes": "stub from {self.config.id}"}}', {}


class OpenAIChatAdapter(ModelAdapter):
    def __init__(self, config, api_key: str):
        super().__init__(config)
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        self.api_key = api_key
        params = self.config.parameters or {}
        self.timeout = float(params.get("timeout", 300))  # default 5 minutes
        self.retries = int(params.get("retries", 3))
        self.backoff = float(params.get("backoff", 2.0))

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, messages: List[Dict[str, str]], temperature: float | None = 0.7):
        payload = {
            "model": self.config.model,
            "messages": messages,
        }

        # For some models (e.g., gpt-5 family), OpenAI only supports default temperature.
        if temperature is not None:
            try:
                tval = float(temperature)
            except (TypeError, ValueError):
                tval = None

            if self.config.model.startswith("gpt-5"):
                # Only default (1) is supported; omit otherwise to avoid API 400.
                if tval == 1 or tval is None:
                    pass
                else:
                    # clamp to default by omitting the param
                    tval = None
            if tval is not None:
                payload["temperature"] = tval

        last_err = None
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
                return data["choices"][0]["message"]["content"], {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            except (req_exc.Timeout, req_exc.ConnectionError) as e:
                last_err = e
                if attempt == self.retries:
                    raise
                time.sleep(self.backoff * attempt)
            except req_exc.HTTPError as e:
                # Do not retry on HTTP errors except 429/500s
                status = e.response.status_code if e.response else None
                if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                    last_err = e
                    time.sleep(self.backoff * attempt)
                    continue
                raise
        raise last_err or RuntimeError("Request failed without exception")


class OpenAIDebaterAdapter(OpenAIChatAdapter, DebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.7)
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature)


class OpenAIJudgeAdapter(OpenAIChatAdapter, JudgeAdapter):
    def judge(self, prompt: str):
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.0)
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature)


class HTTPJSONAdapter(ModelAdapter):
    """
    Generic HTTP JSON chat completion adapter:
    expects OpenAI-compatible payload/response.
    """

    def __init__(self, config, bearer_token: Optional[str] = None):
        super().__init__(config)
        self.bearer_token = bearer_token
        params = self.config.parameters or {}
        self.timeout = float(params.get("timeout", 300))  # default 5 minutes
        self.retries = int(params.get("retries", 3))
        self.backoff = float(params.get("backoff", 2.0))

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _request(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int | None = None):
        # normalize temperature
        try:
            temp_val = float(temperature) if temperature is not None else None
        except (TypeError, ValueError):
            temp_val = None

        payload = {
            "model": self.config.model,
            "messages": messages,
        }
        if temp_val is not None:
            payload["temperature"] = temp_val
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        last_err = None
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
                return data["choices"][0]["message"]["content"], {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
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
                if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                    last_err = e
                    time.sleep(self.backoff * attempt)
                    continue
                detail = f"HTTP {status}"
                if body:
                    detail += f": {body}"
                raise RuntimeError(detail) from e
        raise last_err or RuntimeError("Request failed without exception")


class HTTPDebaterAdapter(HTTPJSONAdapter, DebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.7)
        token_limit = self.config.token_limit or params.get("max_tokens") or 1024
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature, max_tokens=token_limit)


class HTTPJudgeAdapter(HTTPJSONAdapter, JudgeAdapter):
    def judge(self, prompt: str) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.0)
        token_limit = self.config.token_limit or params.get("max_tokens") or 256
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature, max_tokens=token_limit)


class OpenRouterAdapter(HTTPJSONAdapter):
    """
    OpenRouter chat completions adapter.
    Adds required Authorization plus optional referral headers.
    """

    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config, api_key: str, site_url: Optional[str], site_name: Optional[str]):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter provider.")
        # ensure endpoint is set (allow override via config.endpoint)
        if not getattr(config, "endpoint", None):
            config.endpoint = self.DEFAULT_ENDPOINT
        super().__init__(config, bearer_token=api_key)
        self.site_url = site_url
        self.site_name = site_name

    def _headers(self) -> Dict[str, str]:
        headers = super()._headers()
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        headers.setdefault("Accept", "application/json")
        return headers


class OpenRouterDebaterAdapter(OpenRouterAdapter, HTTPDebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn]):
        return HTTPDebaterAdapter.generate(self, prompt, turns)


class OpenRouterJudgeAdapter(OpenRouterAdapter, HTTPJudgeAdapter):
    def judge(self, prompt: str):
        return HTTPJudgeAdapter.judge(self, prompt)


def build_debater_adapter(config: DebaterModelConfig, settings: Settings) -> DebaterAdapter:
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIDebaterAdapter(config, api_key=settings.openai_api_key)
    if provider == "http":
        return HTTPDebaterAdapter(config, bearer_token=settings.http_bearer_token)
    if provider == "openrouter":
        return OpenRouterDebaterAdapter(
            config,
            api_key=settings.openrouter_api_key,
            site_url=settings.openrouter_site_url,
            site_name=settings.openrouter_site_name,
        )
    return DebaterAdapter(config)


def build_judge_adapter(config: JudgeModelConfig, settings: Settings) -> JudgeAdapter:
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIJudgeAdapter(config, api_key=settings.openai_api_key)
    if provider == "http":
        return HTTPJudgeAdapter(config, bearer_token=settings.http_bearer_token)
    if provider == "openrouter":
        return OpenRouterJudgeAdapter(
            config,
            api_key=settings.openrouter_api_key,
            site_url=settings.openrouter_site_url,
            site_name=settings.openrouter_site_name,
        )
    return JudgeAdapter(config)


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)
