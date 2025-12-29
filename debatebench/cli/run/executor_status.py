"""Status tracking helpers for the `debatebench run` executor."""
from __future__ import annotations

import queue
import threading
import time


class StatusTracker:
    def __init__(self, *, main_cfg, total_steps: int) -> None:
        self.main_cfg = main_cfg
        self.total_steps = total_steps
        self.task_status: dict[str, dict] = {}
        self.status_lock = threading.Lock()
        self.status_queue: queue.Queue[tuple] = queue.Queue()

    def _default_entry(self) -> dict:
        return {
            "round": 0,
            "stage": "-",
            "phase": "queued",
            "error": "",
            "last_update": time.monotonic(),
            "judges_done": 0,
            "judges_expected": self.main_cfg.num_judges,
            "retrying": False,
        }

    def update(self, task_id: str, **updates) -> None:
        with self.status_lock:
            entry = self.task_status.setdefault(task_id, self._default_entry())
            entry.update(updates)
            entry["last_update"] = time.monotonic()

    def make_progress_hook(self, task_id: str):
        def _hook(round_idx: int, speaker: str, stage: str):
            self.status_queue.put(
                ("turn", task_id, {"round": round_idx, "stage": stage, "speaker": speaker})
            )

        return _hook

    def make_status_hook(self, task_id: str):
        def _hook(**updates):
            if updates.get("phase") == "judging":
                updates.setdefault("round", self.total_steps)
                updates.setdefault("stage", "judging")
            self.status_queue.put(("phase", task_id, updates))

        return _hook

    def make_judge_hook(self, task_id: str):
        def _hook(done: int, expected: int, judge_id: str):
            self.status_queue.put(
                ("judge", task_id, {"done": done, "expected": expected, "judge_id": judge_id})
            )

        return _hook

    def drain(self) -> bool:
        updated = False
        while True:
            try:
                event = self.status_queue.get_nowait()
            except queue.Empty:
                break
            updated = True
            kind, task_id, payload = event
            if kind == "turn":
                self.update(task_id, round=payload["round"], stage=payload["stage"], phase="debating")
            elif kind == "phase":
                self.update(
                    task_id,
                    phase=payload.get("phase", "queued"),
                    round=payload.get("round", 0),
                    stage=payload.get("stage", "-"),
                )
            elif kind == "error":
                self.update(task_id, phase="error", error=payload["message"])
            elif kind == "judge":
                self.update(
                    task_id,
                    phase="judging",
                    round=self.total_steps,
                    stage="judging",
                    judges_done=payload["done"],
                    judges_expected=payload["expected"],
                )
        return updated


__all__ = ["StatusTracker"]
