"""Tests for Slack incident notifications."""

from app.notifications.slack import format_incident_message, notify_incident


def test_format_incident_message_includes_key_fields():
    incident = {
        "severity": "P2",
        "job_name": "daily_revenue_aggregation",
        "run_id": "run_abc",
        "error": {"failure_mode": "schema_drift", "message": "KeyError: amount"},
        "memory": {
            "prior_occurrences": 2,
            "auto_remediation_success_rate": 1.0,
            "note": "strong track record",
        },
        "investigation": {"skip_claude": True},
        "context": {"run_url": "https://example.com/run"},
    }
    text = format_incident_message(incident)
    assert "run_abc" in text
    assert "schema_drift" in text
    assert "memory fast path" in text
    assert "https://example.com/run" in text


def test_notify_incident_noop_without_webhook(monkeypatch):
    monkeypatch.setattr("app.notifications.slack.SLACK_WEBHOOK_URL", None)
    result = notify_incident({"run_id": "run_x"})
    assert result["sent"] is False


def test_notify_incident_posts_when_configured(monkeypatch):
    monkeypatch.setattr("app.notifications.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json):
            calls.append({"url": url, "json": json})
            return FakeResponse()

    monkeypatch.setattr("app.notifications.slack.httpx.Client", FakeClient)
    result = notify_incident({"run_id": "run_y", "severity": "P1", "error": {}, "memory": {}, "investigation": {}, "context": {}})
    assert result["sent"] is True
    assert calls[0]["url"] == "https://hooks.slack.com/test"
    assert "run_y" in calls[0]["json"]["text"]
