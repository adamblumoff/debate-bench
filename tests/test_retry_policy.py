from __future__ import annotations

from types import SimpleNamespace

from debatebench.cli.run.retry_policy import (
    record_empty_response_failure,
    should_skip_task,
)
from debatebench.debate import EmptyResponseError


class DummyModel:
    def __init__(self, model_id: str):
        self.id = model_id


class DummyTask:
    def __init__(self, pro_id: str, con_id: str):
        self.pro_model = DummyModel(pro_id)
        self.con_model = DummyModel(con_id)


def test_should_skip_task():
    task = DummyTask("a", "b")
    assert should_skip_task(task, {"b"})
    assert not should_skip_task(task, {"c"})


def test_record_empty_response_bans_when_skip_enabled():
    task = DummyTask("a", "b")
    banned = set()
    failed = []
    calls = []

    def writer(**kwargs):
        calls.append(kwargs)

    opts = SimpleNamespace(skip_on_empty=True)
    err = EmptyResponseError("b", "opening", "con")
    record_empty_response_failure(
        error=err,
        task=task,
        opts=opts,
        banned_models=banned,
        failed_debates=failed,
        progress_writer=writer,
        progress_payload={"progress_path": "x", "run_tag": "r", "debates_path": "y", "total_planned_remaining": 1, "completed_new": 0, "completed_prior": 0},
        live_console=None,
    )
    assert "b" in banned
    assert failed == []
    assert calls


def test_record_empty_response_queues_retry_when_skip_disabled():
    task = DummyTask("a", "b")
    banned = set()
    failed = []

    def writer(**kwargs):  # pragma: no cover - should not be called
        raise AssertionError("writer should not be called")

    opts = SimpleNamespace(skip_on_empty=False)
    err = EmptyResponseError("b", "opening", "con")
    record_empty_response_failure(
        error=err,
        task=task,
        opts=opts,
        banned_models=banned,
        failed_debates=failed,
        progress_writer=writer,
        progress_payload={"progress_path": "x", "run_tag": "r", "debates_path": "y", "total_planned_remaining": 1, "completed_new": 0, "completed_prior": 0},
        live_console=None,
    )
    assert "b" not in banned
    assert failed == [task]
