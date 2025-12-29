from __future__ import annotations

import json
from pathlib import Path

from debatebench.cli.run.estimate import (
    estimate_wall_time,
    format_duration,
    load_timing_snapshots,
)


class DummyModel:
    def __init__(self, model_id: str):
        self.id = model_id


class DummyTask:
    def __init__(self, pro_id: str, con_id: str, judge_ids: list[str]):
        self.pro_model = DummyModel(pro_id)
        self.con_model = DummyModel(con_id)
        self.panel_configs = [DummyModel(j) for j in judge_ids]


class DummyRound:
    def __init__(self, speaker: str, stage: str):
        self.speaker = speaker
        self.stage = stage


def test_format_duration():
    assert format_duration(0.5).endswith("ms")
    assert "1m" in format_duration(61)


def test_load_timing_snapshots_filters(tmp_path):
    snap = {
        "debate_totals": {"p50": 10, "n": 200},
        "model_stage_latencies": {},
        "judge_latencies": {},
    }
    path = tmp_path / "run_x" / "timing_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap), encoding="utf-8")

    out = load_timing_snapshots(tmp_path, min_debates=120)
    assert len(out) == 1


def test_estimate_wall_time_fallback():
    tasks = [DummyTask("a", "b", ["j1"])]
    rounds = [DummyRound("pro", "opening"), DummyRound("con", "opening")]
    estimates, meta = estimate_wall_time(
        tasks,
        rounds,
        max_workers=4,
        per_model_cap=4,
        snapshots=[],
        fallback_per_debate=12.0,
    )
    assert meta["source"] == "fallback"
    assert estimates["p50"] == 12.0
