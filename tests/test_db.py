"""Tests for in-memory db consistency."""

from app import db


def test_record_heal_includes_healed_at(monkeypatch):
    monkeypatch.setattr("app.db._pg_available", lambda: False)
    monkeypatch.setattr("app.db.IS_PRODUCTION", False)
    db._mem_heals.clear()
    db.record_heal("daily_revenue_aggregation")
    heals = db.heal_events("daily_revenue_aggregation")
    assert len(heals) == 1
    assert heals[0]["healed_at"]


def test_list_incidents_includes_run_id(monkeypatch):
    monkeypatch.setattr("app.db._pg_available", lambda: False)
    db._mem_incidents.clear()
    db.upsert_incident_status("run_123", "verified_remediated", rca='{"ok":true}')
    rows = db.list_incidents()
    assert rows[0]["run_id"] == "run_123"
    assert rows[0]["status"] == "verified_remediated"
