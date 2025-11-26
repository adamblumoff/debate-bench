"""
Model adapter interfaces and simple stubs.
"""
from __future__ import annotations

import random
from typing import List

from .schema import DebaterModelConfig, JudgeModelConfig, Turn


class ModelAdapter:
    def __init__(self, config):
        self.config = config


class DebaterAdapter(ModelAdapter):
    def generate(self, prompt: str, turns: List[Turn]) -> str:
        """
        Produce a reply for a debate turn.
        This stub returns deterministic filler text.
        """
        history_snippet = " ".join(t.speaker for t in turns[-4:]) if turns else ""
        return f"[stub:{self.config.id}] Responding as {history_snippet or 'start'}: {prompt}"


class JudgeAdapter(ModelAdapter):
    def judge(self, prompt: str) -> str:
        """
        Produce a judge JSON string. This stub returns a simple placeholder.
        """
        return f'{{"winner": "tie", "pro": {{}}, "con": {{}}, "notes": "stub from {self.config.id}"}}'


def build_debater_adapter(config: DebaterModelConfig) -> DebaterAdapter:
    # Future: dispatch on config.provider
    return DebaterAdapter(config)


def build_judge_adapter(config: JudgeModelConfig) -> JudgeAdapter:
    # Future: dispatch on config.provider
    return JudgeAdapter(config)


def sample_judges(pool: List[JudgeModelConfig], n: int, seed: int | None = None) -> List[JudgeModelConfig]:
    rng = random.Random(seed)
    if n > len(pool):
        raise ValueError(f"Requested {n} judges but pool has {len(pool)}")
    return rng.sample(pool, n)
