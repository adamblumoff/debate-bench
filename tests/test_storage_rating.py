from __future__ import annotations

from datetime import datetime, timezone

import pytest

from debatebench import config as cfg
from debatebench.rating import recompute_ratings
from debatebench.schema import (
    AggregatedResult,
    DebateRecord,
    JudgeResult,
    JudgeScores,
    Topic,
    Transcript,
    Turn,
)
from debatebench.storage import append_debate_record, load_debate_records, read_ratings, write_ratings


def _make_record(
    *,
    topic_id: str,
    pro_id: str,
    con_id: str,
    winner: str,
    pro_score: float,
    con_score: float,
) -> DebateRecord:
    now = datetime.now(timezone.utc)
    topic = Topic(id=topic_id, motion=f"motion {topic_id}")
    turn = Turn(
        index=0,
        speaker="pro",
        stage="opening",
        content="hello",
        created_at=now,
    )
    transcript = Transcript(
        debate_id=f"{topic_id}-{pro_id}-{con_id}",
        benchmark_version="v0",
        rubric_version="v0",
        topic=topic,
        pro_model_id=pro_id,
        con_model_id=con_id,
        turns=[turn],
        seed=123,
    )
    judge = JudgeResult(
        judge_id="judge-1",
        pro=JudgeScores(scores={"persuasion": int(pro_score)}),
        con=JudgeScores(scores={"persuasion": int(con_score)}),
        winner=winner,
        raw_response="{}",
    )
    aggregate = AggregatedResult(
        winner=winner,
        mean_pro={"persuasion": pro_score},
        mean_con={"persuasion": con_score},
    )
    return DebateRecord(
        transcript=transcript,
        judges=[judge],
        aggregate=aggregate,
        created_at=now,
        judges_expected=1,
        judges_actual=1,
        panel_complete=True,
        panel_latency_ms=0.0,
        debate_seed=123,
        elo=None,
    )


def test_append_and_load_roundtrip(tmp_path):
    path = tmp_path / "debates.jsonl"
    record = _make_record(
        topic_id="t1",
        pro_id="pro",
        con_id="con",
        winner="pro",
        pro_score=7.0,
        con_score=4.0,
    )
    append_debate_record(path, record)
    loaded = load_debate_records(path)
    assert len(loaded) == 1
    assert loaded[0].transcript.debate_id == record.transcript.debate_id


def test_load_invalid_record_raises(tmp_path):
    path = tmp_path / "debates.jsonl"
    path.write_text('{"bad": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_debate_records(path)


def test_recompute_ratings_and_write_read(tmp_path):
    records = [
        _make_record(
            topic_id="t1",
            pro_id="a",
            con_id="b",
            winner="pro",
            pro_score=8.0,
            con_score=4.0,
        ),
        _make_record(
            topic_id="t2",
            pro_id="b",
            con_id="a",
            winner="pro",
            pro_score=7.0,
            con_score=5.0,
        ),
    ]
    main_cfg = cfg.default_main_config()
    ratings = recompute_ratings(records, main_cfg)
    assert set(ratings.models.keys()) == {"a", "b"}
    assert ratings.models["a"].games_played == 2
    assert ratings.models["b"].games_played == 2

    ratings_path = tmp_path / "ratings.json"
    write_ratings(ratings_path, ratings)
    loaded = read_ratings(ratings_path)
    assert loaded.models["a"].dimension_avgs["persuasion"] > 0
