from __future__ import annotations

from dataclasses import dataclass

from requests import exceptions as req_exc

from debatebench.models import OpenRouterDebaterAdapter
from debatebench.schema import DebaterModelConfig
from debatebench.settings import Settings


class FakeResponse:
    def __init__(self, status_code, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = req_exc.HTTPError()
            err.response = self
            raise err

    def json(self):
        return self._json


def _make_adapter():
    cfg = DebaterModelConfig(
        id="debater",
        provider="openrouter",
        model="test/model",
        token_limit=100,
        parameters={"retries": 2, "backoff": 0},
    )
    settings = Settings(openrouter_api_key="key")
    return OpenRouterDebaterAdapter(cfg, api_key=settings.openrouter_api_key, site_url=None, site_name=None)


def test_openrouter_402_downshift(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(dict(json))
        if len(calls) == 1:
            return FakeResponse(402, text="afford 50")
        return FakeResponse(
            200,
            json_data={"choices": [{"message": {"content": "hi"}}], "usage": {}},
        )

    monkeypatch.setattr("debatebench.models.requests.post", fake_post)
    monkeypatch.setattr("debatebench.models.time.sleep", lambda *_: None)

    adapter = _make_adapter()
    content, _meta = adapter.generate("prompt", [], max_tokens=100)
    assert content == "hi"
    assert calls[0]["max_tokens"] == 100
    assert calls[1]["max_tokens"] == 50


def test_openrouter_429_retry_after(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(dict(json))
        if len(calls) == 1:
            return FakeResponse(429, text="rate", headers={"Retry-After": "0"})
        return FakeResponse(
            200,
            json_data={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    monkeypatch.setattr("debatebench.models.requests.post", fake_post)
    monkeypatch.setattr("debatebench.models.time.sleep", lambda *_: None)

    adapter = _make_adapter()
    content, _meta = adapter.generate("prompt", [], max_tokens=100)
    assert content == "ok"
    assert len(calls) == 2
