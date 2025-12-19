from __future__ import annotations

import yaml

from debatebench import config as cfg


def test_load_main_config_nested_schema(tmp_path):
    payload = {
        "benchmark": {"version": "v1", "rubric_version": "v1r"},
        "debate": {
            "language": "en",
            "system_prompt_pro": "pro prompt",
            "system_prompt_con": "con prompt",
            "rounds": [
                {"role": "pro", "stage": "opening", "max_tokens": 123},
                {"role": "con", "stage": "opening", "max_tokens": 321},
            ],
        },
        "scoring": {
            "dimensions": {
                "persuasion": {"min": 1, "max": 10},
                "reasoning": {"min": 2, "max": 9},
            },
            "judges_per_debate": 4,
            "judge_system_prompt": "json only",
        },
        "elo": {"initial_rating": 500, "k_factor": 24},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    main_cfg = cfg.load_main_config(path)
    assert main_cfg.benchmark_version == "v1"
    assert main_cfg.rubric_version == "v1r"
    assert main_cfg.system_prompt_pro == "pro prompt"
    assert main_cfg.system_prompt_con == "con prompt"
    assert main_cfg.num_judges == 4
    assert main_cfg.elo.initial_rating == 500
    assert main_cfg.elo.k_factor == 24
    assert len(main_cfg.rounds) == 2
    assert main_cfg.rounds[0].token_limit == 123
    assert main_cfg.rounds[1].token_limit == 321
    dim_ids = {d.id for d in main_cfg.scoring.dimensions}
    assert dim_ids == {"persuasion", "reasoning"}
    assert main_cfg.scoring.scale_min == 1
    assert main_cfg.scoring.scale_max == 10


def test_load_main_config_legacy_schema(tmp_path):
    payload = {
        "benchmark_version": "legacy",
        "rubric_version": "legacy",
        "rounds": [{"speaker": "pro", "stage": "opening", "token_limit": 999}],
        "scoring": {
            "dimensions": [{"id": "clarity"}],
            "scale_min": 1,
            "scale_max": 7,
        },
        "num_judges": 2,
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    main_cfg = cfg.load_main_config(path)
    assert main_cfg.benchmark_version == "legacy"
    assert main_cfg.rubric_version == "legacy"
    assert main_cfg.num_judges == 2
    assert main_cfg.rounds[0].token_limit == 999
    assert main_cfg.scoring.scale_min == 1
    assert main_cfg.scoring.scale_max == 7
    assert main_cfg.scoring.dimensions[0].id == "clarity"
