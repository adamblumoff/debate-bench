"""
Default config generators for DebateBench.
"""
from __future__ import annotations

from typing import List

from .schema import (
    DebaterModelConfig,
    DimensionConfig,
    EloConfig,
    JudgeModelConfig,
    MainConfig,
    RoundConfig,
    ScoringConfig,
    Topic,
)


def default_main_config() -> MainConfig:
    """Generate a default main benchmark configuration."""
    rounds = [
        RoundConfig(speaker="pro", stage="opening", token_limit=4096, language="en"),
        RoundConfig(speaker="con", stage="opening", token_limit=4096, language="en"),
    ]
    scoring = ScoringConfig(
        dimensions=[
            DimensionConfig(id="persuasion", name="Persuasion"),
            DimensionConfig(id="reasoning", name="Reasoning"),
            DimensionConfig(id="factuality", name="Factuality"),
            DimensionConfig(id="clarity", name="Clarity"),
            DimensionConfig(id="safety", name="Safety"),
        ],
        scale_min=1,
        scale_max=10,
    )
    return MainConfig(
        benchmark_version="v0",
        rubric_version="v0",
        rounds=rounds,
        scoring=scoring,
        num_judges=3,
        elo=EloConfig(initial_rating=400.0, k_factor=32.0),
        language="en",
        system_prompt_pro=None,
        system_prompt_con=None,
        judge_system_prompt=None,
    )


def default_topics() -> List[Topic]:
    """Provide an empty topics list as a template."""
    return []


def default_debater_models() -> List[DebaterModelConfig]:
    """Provide an empty debater model list as a template."""
    return []


def default_judge_models() -> List[JudgeModelConfig]:
    """Provide an empty judge model list as a template."""
    return []


__all__ = [
    "default_main_config",
    "default_topics",
    "default_debater_models",
    "default_judge_models",
]
