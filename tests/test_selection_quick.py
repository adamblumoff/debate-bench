from __future__ import annotations

import random
from types import SimpleNamespace

import yaml

from debatebench import config as cfg
from debatebench.cli.run.selection_modes import apply_quick_test_selection
from debatebench.cli.run.selection_state import SelectionState


def _make_state(seed: int):
    rng = random.Random(seed)
    main_cfg = cfg.default_main_config()
    topics = [
        cfg.Topic(id="t1", motion="m1"),
        cfg.Topic(id="t2", motion="m2"),
        cfg.Topic(id="t3", motion="m3"),
    ]
    return SelectionState(
        main_cfg=main_cfg,
        topics=topics,
        debater_models=[],
        judge_models=[],
        topics_selected=[],
        debates_per_pair=None,
        base_cli_args={},
        existing_records=[],
        judge_output_max_tokens=None,
        rng=rng,
    )


def _make_setup(sample_topics=None):
    options = SimpleNamespace(
        postupload=True,
        postupload_include_artifacts=True,
        sample_topics=sample_topics,
        openrouter_temperature=0.7,
        openrouter_max_tokens=None,
    )
    return SimpleNamespace(options=options)


def test_quick_test_selection_deterministic_topic(tmp_path, monkeypatch):
    config_path = tmp_path / "quick-test-models.yaml"
    config_payload = {
        "debaters": [{"id": "d1", "provider": "openrouter", "model": "x"}],
        "judges": [{"id": "j1", "provider": "openrouter", "model": "y"}],
        "num_judges": 1,
    }
    config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        "debatebench.cli.run.selection_modes.QUICK_TEST_CONFIG_PATH",
        config_path,
    )

    state_a = _make_state(seed=123)
    setup_a = _make_setup()
    state_b = _make_state(seed=123)
    setup_b = _make_setup()

    apply_quick_test_selection(state_a, setup_a)
    apply_quick_test_selection(state_b, setup_b)

    assert state_a.topics_selected[0].id == state_b.topics_selected[0].id
