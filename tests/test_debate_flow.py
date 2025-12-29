from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from debatebench.debate import _strip_end_marker, _strip_thinking, run_debate
from debatebench.schema import DimensionConfig, MainConfig, RoundConfig, ScoringConfig, Topic


@dataclass
class DummyConfig:
    id: str


class DummyAdapter:
    def __init__(self, responses):
        self.config = DummyConfig(id="dummy")
        self._responses = iter(responses)
        self.calls = 0

    def generate(self, prompt, turns, max_tokens=None):
        self.calls += 1
        return next(self._responses)


def _make_config():
    return MainConfig(
        benchmark_version="v0",
        rubric_version="v0",
        rounds=[RoundConfig(speaker="pro", stage="opening", token_limit=32, language="en")],
        scoring=ScoringConfig(dimensions=[DimensionConfig(id="persuasion")]),
        num_judges=1,
        language="en",
    )


def test_strip_helpers():
    assert _strip_end_marker("hi<END_OF_TURN>") == "hi"
    assert _strip_end_marker("hi<END_OF_") == "hi"
    assert _strip_thinking("a<thinking>secret</thinking>b") == "ab"
    assert _strip_thinking("a```thinking\nsecret\n```b") == "ab"


def test_run_debate_retries_empty():
    topic = Topic(id="t1", motion="motion")
    adapter = DummyAdapter([("", {}), ("Hello<END_OF_TURN>", {})])
    transcript = run_debate(
        topic=topic,
        pro_adapter=adapter,
        con_adapter=adapter,
        config=_make_config(),
        seed=123,
    )
    assert adapter.calls == 2
    assert transcript.turns[0].content == "Hello"


def test_run_debate_reasoning_fallback():
    topic = Topic(id="t2", motion="motion")
    adapter = DummyAdapter([("", {"reasoning": "Reasoned answer"})])
    transcript = run_debate(
        topic=topic,
        pro_adapter=adapter,
        con_adapter=adapter,
        config=_make_config(),
        seed=123,
    )
    assert transcript.turns[0].content == "Reasoned answer"
