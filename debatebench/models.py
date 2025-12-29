"""
OpenRouter-only model adapters.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .schema import DebaterModelConfig, JudgeModelConfig, Turn
from .settings import Settings
from .openrouter_client import OpenRouterClient
from .openrouter_rate import RateLimitState


class ModelAdapter:
    def __init__(self, config):
        self.config = config


class DebaterAdapter(ModelAdapter):
    def generate(
        self,
        prompt: str,
        turns: List[Turn],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
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
    def __init__(
        self,
        config,
        api_key: str,
        site_url: Optional[str],
        site_name: Optional[str],
        include_usage: bool = True,
        rate_state: RateLimitState | None = None,
    ):
        super().__init__(config)
        self._client = OpenRouterClient(
            config=config,
            api_key=api_key,
            site_url=site_url,
            site_name=site_name,
            include_usage=include_usage,
            rate_state=rate_state or DEFAULT_RATE_STATE,
        )


class OpenRouterDebaterAdapter(OpenRouterAdapter, DebaterAdapter):
    def generate(
        self,
        prompt: str,
        turns: List[Turn],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        params = self.config.parameters or {}
        if "temperature" in params:
            temperature = params.get("temperature")
        elif temperature is None:
            temperature = 0.7
        token_limit = max_tokens or self.config.token_limit or params.get("max_tokens") or 1024
        messages = [{"role": "user", "content": prompt}]
        return self._client.request(
            messages,
            temperature=temperature,
            max_tokens=token_limit,
            is_judge=False,
        )


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

        return self._client.request(
            messages,
            temperature=temperature,
            max_tokens=token_limit,
            use_structured=structured,
            response_format=response_format,
            is_judge=True,
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
        rate_state=DEFAULT_RATE_STATE,
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
        rate_state=DEFAULT_RATE_STATE,
    )


def configure_openrouter_rate_limit(max_rpm: int | None) -> None:
    DEFAULT_RATE_STATE.configure(max_rpm)


def get_openrouter_rate_limit_status() -> Dict[str, object]:
    return DEFAULT_RATE_STATE.status()


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    import random

    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)


DEFAULT_RATE_STATE = RateLimitState()
