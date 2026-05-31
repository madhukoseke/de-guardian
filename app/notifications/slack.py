"""Post pipeline incidents to Slack via Incoming Webhook."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import SLACK_WEBHOOK_URL

log = logging.getLogger(__name__)


def _severity_emoji(severity: str) -> str:
    return ":rotating_light:" if severity == "P1" else ":warning:"


def format_incident_message(incident: dict[str, Any]) -> str:
    """Build a Slack mrkdwn message from a pipeline.failed incident."""
    severity = incident.get("severity", "P2")
    memory = incident.get("memory") or {}
    error = incident.get("error") or {}
    context = incident.get("context") or {}
    investigation = incident.get("investigation") or {}

    lines = [
        f"{_severity_emoji(severity)} *DE-Guardian pipeline failure* ({severity})",
        f"*Job:* `{incident.get('job_name', 'unknown')}`",
        f"*Run:* `{incident.get('run_id', 'unknown')}`",
        f"*Mode:* `{error.get('failure_mode', 'unknown')}`",
        f"*Error:* {error.get('message', 'n/a')}",
        f"*Memory:* {memory.get('prior_occurrences', 0)} prior · "
        f"auto-heal rate {memory.get('auto_remediation_success_rate', 'n/a')}",
        f"*Route:* {'memory fast path' if investigation.get('skip_claude') else 'Claude investigation'}",
    ]
    if context.get("run_url"):
        lines.append(f"*Run URL:* {context['run_url']}")
    if memory.get("note"):
        lines.append(f"_{memory['note']}_")
    return "\n".join(lines)


def notify_incident(incident: dict[str, Any]) -> dict[str, Any]:
    """POST incident alert to Slack. No-op when SLACK_WEBHOOK_URL is unset."""
    if not SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not set"}

    text = format_incident_message(incident)
    payload = {"text": text}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(SLACK_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
        log.info(
            "slack notification sent",
            extra={"run_id": incident.get("run_id"), "event": "slack_sent"},
        )
        return {"sent": True, "status": resp.status_code}
    except Exception as exc:
        log.warning(
            "slack notification failed",
            extra={"run_id": incident.get("run_id"), "event": "slack_failed", "error": str(exc)},
        )
        return {"sent": False, "reason": str(exc)}
