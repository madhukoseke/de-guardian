"""API auth and validation tests."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    """
    Provide a TestClient for the FastAPI app configured for tests.
    
    Sets ENV to "development" and removes API_KEY and DATABASE_URL from the environment, then yields a TestClient instance for the application.
    
    Returns:
        TestClient: A TestClient instance for the FastAPI app.
    """
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
    """
    Validates that requesting /runs with a `limit` of 0 is rejected by the API.
    
    Asserts that the endpoint responds with HTTP 422 (request validation failure) when the `limit` query parameter is 0.
    """
    r = client.get("/runs", params={"limit": 0})
    assert r.status_code == 422


def test_memory_unknown_mode(client):
    """
    Verifies that requesting /memory with an invalid mode returns HTTP 400.
    
    Sends a GET request to /memory with mode="not_a_mode" and asserts the response status code is 400.
    """
    r = client.get("/memory", params={"mode": "not_a_mode"})
    assert r.status_code == 400


def test_auth_required_when_api_key_set(client, monkeypatch):
    """
    Verify that POST /heal requires a valid API key when one is configured.
    
    Sets the application's API_KEY to "secret-key", asserts an unauthenticated POST to /heal returns 401, then asserts a POST with header 'Authorization: Bearer secret-key' returns 200. Resets the configured API_KEY to None.
    """
    monkeypatch.setenv("API_KEY", "secret-key")
    import app.config as config
    config.API_KEY = "secret-key"

    r = client.post("/heal")
    assert r.status_code == 401

    r2 = client.post("/heal", headers={"Authorization": "Bearer secret-key"})
    assert r2.status_code == 200
    config.API_KEY = None
