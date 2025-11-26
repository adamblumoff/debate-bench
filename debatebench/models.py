"""
Model adapter interfaces and implementations.
"""
from __future__ import annotations

import json
import random
from typing import Dict, List, Optional

import requests

from .schema import DebaterModelConfig, JudgeModelConfig, Turn
from .settings import Settings


class ModelAdapter:
    def __init__(self, config):
        self.config = config


class DebaterAdapter(ModelAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:  # pragma: no cover - placeholder
        history_snippet = " ".join(t.speaker for t in turns[-4:]) if turns else ""
        return f"[stub:{self.config.id}] Responding as {history_snippet or 'start'}: {prompt}"


class JudgeAdapter(ModelAdapter):
    def judge(self, prompt: str) -> str:  # pragma: no cover - placeholder
        return f'{{"winner": "tie", "pro": {{}}, "con": {{}}, "notes": "stub from {self.config.id}"}}'


class OpenAIChatAdapter(ModelAdapter):
    def __init__(self, config, api_key: str):
        super().__init__(config)
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, messages: List[Dict[str, str]], temperature: float | None = 0.7) -> str:
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

        resp = requests.post(self.config.endpoint, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class OpenAIDebaterAdapter(OpenAIChatAdapter, DebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.7)
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature)


class OpenAIJudgeAdapter(OpenAIChatAdapter, JudgeAdapter):
    def judge(self, prompt: str) -> str:
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

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _request(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = requests.post(self.config.endpoint, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class HTTPDebaterAdapter(HTTPJSONAdapter, DebaterAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.7)
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature)


class HTTPJudgeAdapter(HTTPJSONAdapter, JudgeAdapter):
    def judge(self, prompt: str) -> str:
        params = self.config.parameters or {}
        temperature = params.get("temperature", 0.0)
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, temperature=temperature)


def build_debater_adapter(config: DebaterModelConfig, settings: Settings) -> DebaterAdapter:
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIDebaterAdapter(config, api_key=settings.openai_api_key)
    if provider == "http":
        return HTTPDebaterAdapter(config, bearer_token=settings.http_bearer_token)
    return DebaterAdapter(config)


def build_judge_adapter(config: JudgeModelConfig, settings: Settings) -> JudgeAdapter:
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIJudgeAdapter(config, api_key=settings.openai_api_key)
    if provider == "http":
        return HTTPJudgeAdapter(config, bearer_token=settings.http_bearer_token)
    return JudgeAdapter(config)


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)
