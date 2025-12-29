"""
Strict config parsing helpers for DebateBench.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

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
from .config_defaults import default_main_config


def _reject_unknown_keys(data: Dict, allowed: Iterable[str], context: str) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping.")
    allowed_set = set(allowed)
    unknown = [k for k in data.keys() if k not in allowed_set]
    if unknown:
        raise ValueError(f"Unknown keys in {context}: {', '.join(sorted(unknown))}")


def _parse_rounds(rounds_raw: Sequence, language: str, context: str) -> List[RoundConfig]:
    rounds: List[RoundConfig] = []
    for idx, entry in enumerate(rounds_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"{context}[{idx}] must be a mapping.")
        _reject_unknown_keys(
            entry,
            {"role", "speaker", "stage", "max_tokens", "token_limit", "language"},
            f"{context}[{idx}]",
        )
        rounds.append(
            RoundConfig(
                speaker=entry.get("role") or entry.get("speaker"),
                stage=entry.get("stage", "turn"),
                token_limit=entry.get("max_tokens") or entry.get("token_limit") or 5000,
                language=entry.get("language", language),
            )
        )
    return rounds


def _parse_dimensions(dimensions_raw) -> List[DimensionConfig]:
    dimensions: List[DimensionConfig] = []
    if isinstance(dimensions_raw, dict):
        for dim_id, dim_cfg in dimensions_raw.items():
            if dim_cfg is None:
                dim_cfg = {}
            if not isinstance(dim_cfg, dict):
                raise ValueError(f"Dimension '{dim_id}' must be a mapping.")
            _reject_unknown_keys(
                dim_cfg,
                {"min", "max", "description", "name"},
                f"scoring.dimensions.{dim_id}",
            )
            name = dim_cfg.get("name")
            dimensions.append(DimensionConfig(id=dim_id, name=name))
    elif isinstance(dimensions_raw, list):
        for idx, dim_cfg in enumerate(dimensions_raw):
            if not isinstance(dim_cfg, dict):
                raise ValueError(f"scoring.dimensions[{idx}] must be a mapping.")
            _reject_unknown_keys(
                dim_cfg,
                {"id", "name", "description"},
                f"scoring.dimensions[{idx}]",
            )
            dimensions.append(
                DimensionConfig(id=dim_cfg.get("id"), name=dim_cfg.get("name"))
            )
    else:
        raise ValueError("scoring.dimensions must be a dict or list.")
    return dimensions


def parse_main_config_data(data: dict) -> MainConfig:
    """
    Accept both legacy flat schema and the nested schema, rejecting unknown keys.
    """
    if not data:
        return default_main_config()

    scoring_block = data.get("scoring")
    nested_dims = (
        isinstance(scoring_block, dict)
        and isinstance(scoring_block.get("dimensions"), dict)
    )
    if "benchmark" in data or "debate" in data or nested_dims:
        _reject_unknown_keys(data, {"benchmark", "debate", "scoring", "elo"}, "config")
        benchmark = data.get("benchmark", {})
        debate = data.get("debate", {})
        scoring = data.get("scoring", {})
        elo = data.get("elo", {})

        _reject_unknown_keys(benchmark, {"version", "rubric_version", "name"}, "benchmark")
        _reject_unknown_keys(
            debate,
            {"language", "system_prompt_pro", "system_prompt_con", "rounds", "temperature"},
            "debate",
        )
        _reject_unknown_keys(
            scoring, {"dimensions", "judges_per_debate", "num_judges", "judge_system_prompt"}, "scoring"
        )
        _reject_unknown_keys(elo, {"initial_rating", "k_factor", "min_games_for_display"}, "elo")

        benchmark_version = benchmark.get("version", "v0")
        rubric_version = benchmark.get("rubric_version", benchmark_version)
        language = debate.get("language", "en")
        system_prompt_pro = debate.get("system_prompt_pro")
        system_prompt_con = debate.get("system_prompt_con")

        rounds_raw = debate.get("rounds", [])
        rounds = _parse_rounds(rounds_raw, language, "debate.rounds")

        dimensions_raw = scoring.get("dimensions", {})
        dimensions = _parse_dimensions(dimensions_raw)

        scale_min = None
        scale_max = None
        if isinstance(dimensions_raw, dict):
            for dim_cfg in dimensions_raw.values():
                if not isinstance(dim_cfg, dict):
                    continue
                dmin = dim_cfg.get("min")
                dmax = dim_cfg.get("max")
                if dmin is not None:
                    scale_min = dmin if scale_min is None else min(scale_min, dmin)
                if dmax is not None:
                    scale_max = dmax if scale_max is None else max(scale_max, dmax)

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

    _reject_unknown_keys(
        data,
        {
            "benchmark_version",
            "rubric_version",
            "rounds",
            "scoring",
            "num_judges",
            "elo",
            "language",
            "system_prompt_pro",
            "system_prompt_con",
            "judge_system_prompt",
        },
        "config",
    )

    rounds_raw = data.get("rounds", [])
    rounds = _parse_rounds(rounds_raw, data.get("language", "en"), "rounds")

    scoring = data.get("scoring", {})
    _reject_unknown_keys(scoring, {"dimensions", "scale_min", "scale_max"}, "scoring")
    dimensions = _parse_dimensions(scoring.get("dimensions", []))
    scoring_cfg = ScoringConfig(
        dimensions=dimensions,
        scale_min=scoring.get("scale_min", 1),
        scale_max=scoring.get("scale_max", 10),
    )
    data = dict(data)
    data["rounds"] = rounds
    data["scoring"] = scoring_cfg
    return MainConfig(**data)


def parse_topics_data(data) -> List[Topic]:
    if isinstance(data, dict) and "topics" in data:
        _reject_unknown_keys(data, {"topics"}, "topics file")
        data = data["topics"]
    if not isinstance(data, list):
        raise ValueError("Topics file must be a list or contain a 'topics' list.")
    topics: List[Topic] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"topics[{idx}] must be a mapping.")
        _reject_unknown_keys(entry, {"id", "motion", "category"}, f"topics[{idx}]")
        topics.append(Topic(**entry))
    return topics


def _parse_model_list(data, context: str) -> List[Dict]:
    if isinstance(data, dict):
        key = "models" if context == "models" else "judges"
        _reject_unknown_keys(data, {key}, context)
        data = data.get(key)
    if not isinstance(data, list):
        raise ValueError(f"{context} file must be a list or contain a '{context}' list.")
    return data


def parse_debater_models_data(data) -> List[DebaterModelConfig]:
    entries = _parse_model_list(data, "models")
    models: List[DebaterModelConfig] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"models[{idx}] must be a mapping.")
        _reject_unknown_keys(
            entry,
            {"id", "provider", "model", "token_limit", "endpoint", "parameters", "role"},
            f"models[{idx}]",
        )
        if "parameters" in entry and entry["parameters"] is not None and not isinstance(
            entry["parameters"], dict
        ):
            raise ValueError(f"models[{idx}].parameters must be a mapping.")
        models.append(DebaterModelConfig(**entry))
    return models


def parse_judge_models_data(data) -> List[JudgeModelConfig]:
    entries = _parse_model_list(data, "judges")
    models: List[JudgeModelConfig] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"judges[{idx}] must be a mapping.")
        _reject_unknown_keys(
            entry,
            {
                "id",
                "provider",
                "model",
                "endpoint",
                "prompt_style",
                "token_limit",
                "parameters",
                "role",
            },
            f"judges[{idx}]",
        )
        if "parameters" in entry and entry["parameters"] is not None and not isinstance(
            entry["parameters"], dict
        ):
            raise ValueError(f"judges[{idx}].parameters must be a mapping.")
        models.append(JudgeModelConfig(**entry))
    return models


__all__ = [
    "parse_main_config_data",
    "parse_topics_data",
    "parse_debater_models_data",
    "parse_judge_models_data",
]
