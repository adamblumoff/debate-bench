from __future__ import annotations

import random
from types import SimpleNamespace

from debatebench import config as cfg
from debatebench.cli.run.selection_standard import apply_standard_selection
from debatebench.cli.run.selection_state import SelectionState
from debatebench.schema import DebaterModelConfig
from debatebench.settings import Settings


def _make_state(seed: int = 123):
    rng = random.Random(seed)
    topics = [
        cfg.Topic(id="t1", motion="m1"),
        cfg.Topic(id="t2", motion="m2"),
    ]
    debaters = [
        DebaterModelConfig(id="a", provider="openrouter", model="a/model"),
        DebaterModelConfig(id="b", provider="openrouter", model="b/model"),
    ]
    return SelectionState(
        main_cfg=cfg.default_main_config(),
        topics=topics,
        debater_models=debaters,
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
        openrouter_select=False,
        openrouter_probe=False,
        openrouter_months=1,
        openrouter_temperature=0.7,
        openrouter_max_tokens=None,
        openrouter_judge_max_tokens=None,
        openrouter_judge_months=None,
        ui="none",
        sample_topics=sample_topics,
        judges_from_selection=True,
    )
    return SimpleNamespace(options=options, settings=Settings(openrouter_api_key=None))


def test_standard_selection_uses_existing_models():
    state = _make_state()
    setup = _make_setup()
    state.main_cfg.num_judges = 3
    selected = apply_standard_selection(state, setup)
    assert len(selected.topics_selected) == 2
    assert len(selected.judge_models) == 2
    assert selected.main_cfg.num_judges == 2


def test_standard_selection_sample_topics():
    state = _make_state()
    setup = _make_setup(sample_topics=1)
    selected = apply_standard_selection(state, setup)
    assert len(selected.topics_selected) == 1
