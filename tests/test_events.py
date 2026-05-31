"""Tests for webhook signing and incident payload shape."""

import json

from app.events import build_incident, sign_webhook_payload


def test_sign_webhook_payload():
    payload = b'{"event":"pipeline.failed"}'
    sig = sign_webhook_payload(payload, "test-secret")
    assert len(sig) == 64


def test_build_incident_includes_investigation(monkeypatch):
    monkeypatch.setattr("app.events.db.recent_runs", lambda limit=200: [])
    monkeypatch.setattr("app.events.db.heal_events", lambda job, limit=100: [])
    run = {
        "run_id": "run_test",
        "job_name": "daily_revenue_aggregation",
        "failure_mode": "schema_drift",
        "error_type": "SchemaDrift",
        "error_message": "boom",
        "finished_at": "2026-01-01T00:00:00Z",
        "duration_ms": 1,
        "rows_in": 10,
        "offending_record": {},
        "recent_changes": [],
    }
    incident = build_incident(run)
    assert incident["event"] == "pipeline.failed"
    assert "memory" in incident
    assert "investigation" in incident
    assert "incidents_sync_url" in incident["context"]
    assert incident["investigation"]["skip_claude"] is False


def test_severity_p1_for_upstream_timeout(monkeypatch):
    monkeypatch.setattr("app.events.db.recent_runs", lambda limit=200: [])
    monkeypatch.setattr("app.events.db.heal_events", lambda job, limit=100: [])
    run = {
        "run_id": "run_p1",
        "job_name": "daily_revenue_aggregation",
        "failure_mode": "upstream_timeout",
        "error_type": "UpstreamTimeout",
        "error_message": "504",
        "finished_at": "2026-01-01T00:00:00Z",
        "duration_ms": 1,
        "rows_in": 10,
    }
    incident = build_incident(run)
    assert incident["severity"] == "P1"
