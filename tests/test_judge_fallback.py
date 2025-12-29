from __future__ import annotations

from dataclasses import dataclass

import pytest

from debatebench.judge import run_single_judge
from debatebench.schema import (
    DimensionConfig,
    MainConfig,
    RoundConfig,
    ScoringConfig,
    Topic,
    Transcript,
    Turn,
)


@dataclass
class DummyConfig:
    id: str


class DummyJudgeAdapter:
    def __init__(self, responses):
        self.config = DummyConfig(id="judge-1")
        self._responses = iter(responses)
        self.calls = 0

    def judge(self, prompt, structured=True, dim_ids=None, format_hint=None):
        self.calls += 1
        return next(self._responses)


def _make_config():
    return MainConfig(
        benchmark_version="v0",
        rubric_version="v0",
        rounds=[RoundConfig(speaker="pro", stage="opening", token_limit=32, language="en")],
        scoring=ScoringConfig(
            dimensions=[DimensionConfig(id="persuasion")],
            scale_min=1,
            scale_max=10,
        ),
        num_judges=1,
        language="en",
    )


def _make_transcript():
    topic = Topic(id="t1", motion="motion")
    turn = Turn(
        index=0,
        speaker="pro",
        stage="opening",
        content="hi",
        created_at="2024-01-01T00:00:00Z",
    )
    return Transcript(
        debate_id="d1",
        benchmark_version="v0",
        rubric_version="v0",
        topic=topic,
        pro_model_id="pro",
        con_model_id="con",
        turns=[turn],
        seed=123,
    )


def test_run_single_judge_non_json_raises():
    adapter = DummyJudgeAdapter([("not json at all", {})])
    with pytest.raises(RuntimeError):
        run_single_judge(adapter, _make_transcript(), _make_config())


def test_run_single_judge_json_with_text_wrapper():
    adapter = DummyJudgeAdapter([("Result:\n{\"scores\":{\"pro\":{\"persuasion\":7},\"con\":{\"persuasion\":4}}}", {})])
    result = run_single_judge(adapter, _make_transcript(), _make_config())
    assert result.winner == "pro"
