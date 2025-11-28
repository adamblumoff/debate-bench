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


# ---------- Load helpers ----------


def _load_yaml(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def _parse_main_config(data: dict) -> MainConfig:
    """
    Accept both the legacy flat schema and the richer nested schema the user provided.
    """
    if not data:
        return default_main_config()

    # New nested style with benchmark/debate/scoring/elo keys
    if "benchmark" in data or "debate" in data or "scoring" in data:
        benchmark = data.get("benchmark", {})
        debate = data.get("debate", {})
        scoring = data.get("scoring", {})
        elo = data.get("elo", {})

        benchmark_version = benchmark.get("version", "v0")
        rubric_version = benchmark.get("rubric_version", benchmark_version)
        language = debate.get("language", "en")
        system_prompt_pro = debate.get("system_prompt_pro")
        system_prompt_con = debate.get("system_prompt_con")

        rounds_raw = debate.get("rounds", [])
        rounds: List[RoundConfig] = []
        for r in rounds_raw:
            rounds.append(
                RoundConfig(
                    speaker=r.get("role") or r.get("speaker"),
                    stage=r.get("stage", "turn"),
                    token_limit=r.get("max_tokens") or r.get("token_limit") or 4096,
                    language=r.get("language", language),
                )
            )

        dimensions_raw = scoring.get("dimensions", {})
        dimensions: List[DimensionConfig] = []
        scale_min = None
        scale_max = None
        if isinstance(dimensions_raw, dict):
            for dim_id, dim_cfg in dimensions_raw.items():
                dimensions.append(DimensionConfig(id=dim_id, name=dim_id))
                if isinstance(dim_cfg, dict):
                    dmin = dim_cfg.get("min")
                    dmax = dim_cfg.get("max")
                    if dmin is not None:
                        scale_min = dmin if scale_min is None else min(scale_min, dmin)
                    if dmax is not None:
                        scale_max = dmax if scale_max is None else max(scale_max, dmax)
        else:
            # fallback to list
            dimensions = [DimensionConfig(**d) for d in dimensions_raw]

        scoring_cfg = ScoringConfig(
            dimensions=dimensions,
            scale_min=scale_min if scale_min is not None else 1,
            scale_max=scale_max if scale_max is not None else 10,
        )

        num_judges = scoring.get("judges_per_debate") or scoring.get("num_judges") or 3
        judge_system_prompt = scoring.get("judge_system_prompt")

        elo_cfg = EloConfig(
            initial_rating=elo.get("initial_rating", 400.0),
            k_factor=elo.get("k_factor", 32.0),
        )

        return MainConfig(
            benchmark_version=benchmark_version,
            rubric_version=rubric_version,
            rounds=rounds if rounds else default_main_config().rounds,
            scoring=scoring_cfg,
            num_judges=num_judges,
            elo=elo_cfg,
            language=language,
            system_prompt_pro=system_prompt_pro,
            system_prompt_con=system_prompt_con,
            judge_system_prompt=judge_system_prompt,
        )

    # Legacy flat schema
    return MainConfig(**data)


def load_main_config(path: Path) -> MainConfig:
    data = _load_yaml(path) or {}
    return _parse_main_config(data)


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
