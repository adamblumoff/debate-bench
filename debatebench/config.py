"""
Loading, validating, and generating DebateBench configuration files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

import yaml

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

# ---------- Default generators ----------


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


# ---------- Load helpers ----------


def _load_yaml(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_main_config(path: Path) -> MainConfig:
    data = _load_yaml(path) or {}
    return MainConfig(**data)


def load_topics(path: Path) -> List[Topic]:
    data = _load_yaml(path) or []
    if isinstance(data, dict) and "topics" in data:
        data = data["topics"]
    if not isinstance(data, list):
        raise ValueError("Topics file must be a list or contain a 'topics' list.")
    return [Topic(**t) for t in data]


def load_debater_models(path: Path) -> List[DebaterModelConfig]:
    data = _load_yaml(path) or []
    if isinstance(data, dict) and "models" in data:
        data = data["models"]
    if not isinstance(data, list):
        raise ValueError("Debater models file must be a list or contain a 'models' list.")
    return [DebaterModelConfig(**m) for m in data]


def load_judge_models(path: Path) -> List[JudgeModelConfig]:
    data = _load_yaml(path) or []
    if isinstance(data, dict) and "judges" in data:
        data = data["judges"]
    if not isinstance(data, list):
        raise ValueError("Judge models file must be a list or contain a 'judges' list.")
    return [JudgeModelConfig(**m) for m in data]


# ---------- Write helpers ----------


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_default_configs(
    root: Path,
    overwrite: bool = False,
) -> None:
    """
    Create default config templates if they do not already exist.
    """
    configs_dir = root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    main_cfg_path = configs_dir / "config.yaml"
    topics_path = configs_dir / "topics.json"
    models_path = configs_dir / "models.yaml"
    judges_path = configs_dir / "judges.yaml"

    if overwrite or not main_cfg_path.exists():
        write_yaml(main_cfg_path, default_main_config().dict())

    if overwrite or not topics_path.exists():
        write_json(topics_path, default_topics())

    if overwrite or not models_path.exists():
        write_yaml(models_path, default_debater_models())

    if overwrite or not judges_path.exists():
        write_yaml(judges_path, default_judge_models())


def load_all_configs(
    config_path: Path,
    topics_path: Path,
    models_path: Path,
    judges_path: Path,
):
    main = load_main_config(config_path)
    topics = load_topics(topics_path)
    debaters = load_debater_models(models_path)
    judges = load_judge_models(judges_path)
    return main, topics, debaters, judges
