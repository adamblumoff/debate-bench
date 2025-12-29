"""
Rate limiting + backoff helpers for OpenRouter requests.
"""
from __future__ import annotations

import threading
import time
from typing import Dict


class _RateLimiter:
    def __init__(self, max_rpm: int):
        self.max_rpm = max(1, max_rpm)
        self.tokens = float(self.max_rpm)
        self.refill_rate = self.max_rpm / 60.0
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.updated
                if elapsed > 0:
                    self.tokens = min(
                        float(self.max_rpm), self.tokens + elapsed * self.refill_rate
                    )
                    self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait_for = (1 - self.tokens) / self.refill_rate if self.refill_rate > 0 else 1.0
            time.sleep(min(wait_for, 1.0))


class RateLimitState:
    def __init__(self) -> None:
        self._rate_limiter: _RateLimiter | None = None
        self._rate_limit_max_rpm: int | None = None
        self._backoff_lock = threading.Lock()
        self._backoff_until = 0.0
        self._backoff_reason = ""

    def configure(self, max_rpm: int | None) -> None:
        if max_rpm is None:
            self._rate_limiter = None
            self._rate_limit_max_rpm = None
        else:
            self._rate_limiter = _RateLimiter(max_rpm)
            self._rate_limit_max_rpm = max_rpm

    def acquire(self) -> None:
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()

    def note_backoff(self, seconds: float, reason: str) -> None:
        if seconds <= 0:
            return
        with self._backoff_lock:
            self._backoff_until = max(self._backoff_until, time.monotonic() + seconds)
            self._backoff_reason = reason

    def status(self) -> Dict[str, object]:
        with self._backoff_lock:
            remaining = max(0.0, self._backoff_until - time.monotonic())
            reason = self._backoff_reason if remaining > 0 else ""
        return {
            "max_rpm": self._rate_limit_max_rpm,
            "backoff_remaining": remaining,
            "backoff_reason": reason,
        }


def parse_retry_after(headers: Dict[str, str]) -> float | None:
    if not headers:
        return None
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if not retry_after:
        return None
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        return None


__all__ = ["RateLimitState", "parse_retry_after"]
