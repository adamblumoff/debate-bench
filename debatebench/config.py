"""
Loading, validating, and generating DebateBench configuration files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import yaml

from .schema import DebaterModelConfig, JudgeModelConfig, MainConfig, Topic
from .config_defaults import (
    default_main_config,
    default_topics,
    default_debater_models,
    default_judge_models,
)
from .config_parse import (
    parse_main_config_data,
    parse_topics_data,
    parse_debater_models_data,
    parse_judge_models_data,
)


# ---------- Load helpers ----------


def _load_yaml(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_main_config(path: Path) -> MainConfig:
    data = _load_yaml(path) or {}
    return parse_main_config_data(data)


def load_topics(path: Path) -> List[Topic]:
    data = _load_yaml(path) or []
    return parse_topics_data(data)


def load_debater_models(path: Path) -> List[DebaterModelConfig]:
    data = _load_yaml(path) or []
    return parse_debater_models_data(data)


def load_judge_models(path: Path) -> List[JudgeModelConfig]:
    data = _load_yaml(path) or []
    return parse_judge_models_data(data)


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


__all__ = [
    "default_main_config",
    "default_topics",
    "default_debater_models",
    "default_judge_models",
    "load_main_config",
    "load_topics",
    "load_debater_models",
    "load_judge_models",
    "load_all_configs",
    "parse_main_config_data",
    "parse_topics_data",
    "parse_debater_models_data",
    "parse_judge_models_data",
]
