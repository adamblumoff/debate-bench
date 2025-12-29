from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from requests import exceptions as req_exc

from debatebench.openrouter import fetch_recent_openrouter_models, probe_model


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


def test_fetch_recent_openrouter_models_filters(monkeypatch):
    now = datetime.now(timezone.utc)
    recent_ts = int((now - timedelta(days=10)).timestamp())
    old_ts = int((now - timedelta(days=120)).timestamp())
    payload = {
        "data": [
            {
                "id": "recent-text",
                "created": recent_ts,
                "name": "Recent",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            },
            {
                "id": "recent-image",
                "created": recent_ts,
                "architecture": {"input_modalities": ["image"], "output_modalities": ["text"]},
            },
            {
                "id": "old-text",
                "created": old_ts,
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            },
        ]
    }

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(200, json_data=payload)

    monkeypatch.setattr("debatebench.openrouter.requests.get", fake_get)
    models = fetch_recent_openrouter_models(months=1, api_key="key")
    assert [m["id"] for m in models] == ["recent-text"]


def test_fetch_recent_openrouter_models_requires_key():
    with pytest.raises(ValueError):
        fetch_recent_openrouter_models(months=1, api_key="")


def test_probe_model_success(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(200)

    monkeypatch.setattr("debatebench.openrouter.requests.post", fake_post)
    assert probe_model("model", api_key="key") is None


def test_probe_model_failure(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(400, text="bad request")

    monkeypatch.setattr("debatebench.openrouter.requests.post", fake_post)
    assert probe_model("model", api_key="key") == "bad request"
