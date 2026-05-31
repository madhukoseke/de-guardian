"""Post pipeline incidents to Slack via Incoming Webhook."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import SLACK_WEBHOOK_URL

log = logging.getLogger(__name__)


def _severity_emoji(severity: str) -> str:
    """
    Map an incident severity label to the corresponding Slack emoji.
    
    Parameters:
        severity (str): Severity label (e.g., "P1").
    
    Returns:
        str: ":rotating_light:" when `severity` is "P1", ":warning:" otherwise.
    """
    return ":rotating_light:" if severity == "P1" else ":warning:"


def format_incident_message(incident: dict[str, Any]) -> str:
    """
    Constructs a Slack mrkdwn message describing a pipeline failure incident.
    
    Builds a multi-line message that includes severity (with emoji), a DE-Guardian pipeline failure label, job name, run ID, failure mode, error message, memory metrics (prior occurrences and auto-remediation success rate), and a route label that reflects whether the investigation skips Claude. If present, the message also includes the run URL and an italicized memory note.
    
    Parameters:
        incident (dict[str, Any]): Incident payload containing optional keys such as
            "severity", "job_name", "run_id", "error" (with "failure_mode" and "message"),
            "memory" (with "prior_occurrences", "auto_remediation_success_rate", "note"),
            "context" (with "run_url"), and "investigation" (with "skip_claude").
    
    Returns:
        str: The formatted Slack mrkdwn message.
    """
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
    """
    Send a formatted incident alert to Slack using the configured incoming webhook.
    
    If the Slack webhook URL is not configured, the function does nothing and returns a result indicating it did not send a notification. The function always returns a small status dictionary describing whether the notification was sent and, on failure, the reason.
    
    Parameters:
        incident (dict[str, Any]): Incident payload used to build the Slack message (expected fields include keys such as "run_id", "job_name", "error", "memory", "context", and "investigation").
    
    Returns:
        dict[str, Any]: Result object with the following shapes:
            - On success: {"sent": True, "status": <http status code>}
            - When webhook is unset: {"sent": False, "reason": "SLACK_WEBHOOK_URL not set"}
            - On failure: {"sent": False, "reason": "<error message>"}
    """
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
