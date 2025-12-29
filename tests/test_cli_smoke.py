from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from typer.testing import CliRunner

from debatebench import config as cfg
from debatebench.cli.app import app
from debatebench.schema import (
    AggregatedResult,
    DebateRecord,
    JudgeResult,
    JudgeScores,
    Topic,
    Transcript,
    Turn,
)
from debatebench.storage import append_debate_record


def _write_config(path: Path) -> None:
    payload = cfg.default_main_config().model_dump()
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_debates(path: Path) -> None:
    now = datetime.now(timezone.utc)
    topic = Topic(id="t1", motion="motion")
    turn = Turn(index=0, speaker="pro", stage="opening", content="hi", created_at=now)
    transcript = Transcript(
        debate_id="d1",
        benchmark_version="v0",
        rubric_version="v0",
        topic=topic,
        pro_model_id="a",
        con_model_id="b",
        turns=[turn],
        seed=123,
    )
    judge = JudgeResult(
        judge_id="judge-1",
        pro=JudgeScores(scores={"persuasion": 6}),
        con=JudgeScores(scores={"persuasion": 4}),
        winner="pro",
        raw_response="{}",
    )
    aggregate = AggregatedResult(
        winner="pro",
        mean_pro={"persuasion": 6.0},
        mean_con={"persuasion": 4.0},
    )
    record = DebateRecord(
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
    append_debate_record(path, record)


def test_cli_rate_and_leaderboard(tmp_path):
    config_path = tmp_path / "config.yaml"
    debates_path = tmp_path / "debates.jsonl"
    ratings_path = tmp_path / "ratings.json"

    _write_config(config_path)
    _write_debates(debates_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "rate",
            "--debates-path",
            str(debates_path),
            "--config-path",
            str(config_path),
            "--ratings-path",
            str(ratings_path),
        ],
    )
    assert result.exit_code == 0
    assert "Wrote ratings" in result.output

    result = runner.invoke(
        app,
        [
            "show-leaderboard",
            "--ratings-path",
            str(ratings_path),
            "--top",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "DebateBench Leaderboard" in result.output
