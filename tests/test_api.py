"""API auth and validation tests."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_runs_limit_bounds(client):
    r = client.get("/runs", params={"limit": 0})
    assert r.status_code == 422


def test_memory_unknown_mode(client):
    r = client.get("/memory", params={"mode": "not_a_mode"})
    assert r.status_code == 400


def test_auth_required_when_api_key_set(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    import app.config as config
    config.API_KEY = "secret-key"

    r = client.post("/heal")
    assert r.status_code == 401

    r2 = client.post("/heal", headers={"Authorization": "Bearer secret-key"})
    assert r2.status_code == 200
    config.API_KEY = None
