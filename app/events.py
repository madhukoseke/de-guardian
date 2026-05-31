"""
On a failed run, emit a rich incident event to the SuperPlane Canvas webhook
trigger (set SUPERPLANE_WEBHOOK_URL). Retries with backoff and persists
delivery status on the run record.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from app import db, memory
from app.config import (
    IS_PRODUCTION,
    RENDER_SERVICE_NAME,
    SERVICE_BASE_URL,
    SUPERPLANE_WEBHOOK_SECRET,
    SUPERPLANE_WEBHOOK_URL,
    WEBHOOK_MAX_ATTEMPTS,
    WEBHOOK_RETRY_BACKOFF_SEC,
)
from app.notifications.slack import notify_incident as notify_slack

log = logging.getLogger(__name__)

SUPERPLANE_WEBHOOK_SIGNATURE_HEADER = __import__("os").environ.get(
    "SUPERPLANE_WEBHOOK_SIGNATURE_HEADER", "X-Signature-256"
)


def sign_webhook_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 hex digest, matching SuperPlane's openssl example."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def severity_for_failure_mode(failure_mode: str | None) -> str:
    """SLA routing hint: upstream_timeout is P1; others default P2."""
    if failure_mode == "upstream_timeout":
        return "P1"
    return "P2"


def build_incident(run: dict[str, Any]) -> dict[str, Any]:
    """Shape a failed run into the incident event the Canvas consumes."""
    runs = db.recent_runs(200)
    job_name = run.get("job_name") or ""
    heals = db.heal_events(job_name, 200)
    mem = memory.recall(
        run.get("failure_mode"),
        job_name,
        runs,
        exclude_run_id=run.get("run_id"),
        heal_events=heals,
    )
    investigation = memory.resolve(run, runs, recall_result=mem, heal_events=heals)
    failure_mode = run.get("failure_mode")
    return {
        "event": "pipeline.failed",
        "severity": severity_for_failure_mode(failure_mode),
        "job_name": run.get("job_name"),
        "run_id": run.get("run_id"),
        "failed_at": run.get("finished_at"),
        "duration_ms": run.get("duration_ms"),
        "rows_in": run.get("rows_in"),
        "error": {
            "type": run.get("error_type"),
            "message": run.get("error_message"),
            "failure_mode": failure_mode,
            "offending_record": run.get("offending_record"),
            "traceback": run.get("traceback"),
        },
        "memory": mem,
        "investigation": investigation,
        "context": {
            "last_success_at": run.get("last_success_at"),
            "recent_changes": run.get("recent_changes"),
            "service": RENDER_SERVICE_NAME,
            "heal_endpoint": "/heal",
            "heal_url": f"{SERVICE_BASE_URL}/heal",
            "run_url": f"{SERVICE_BASE_URL}/run",
            "status_url": f"{SERVICE_BASE_URL}/status",
            "incidents_url": f"{SERVICE_BASE_URL}/incidents",
            "incidents_sync_url": f"{SERVICE_BASE_URL}/incidents/status",
        },
    }


def emit_incident(run: dict[str, Any]) -> dict[str, Any]:
    incident = build_incident(run)
    run_id = run.get("run_id", "")

    if not SUPERPLANE_WEBHOOK_URL:
        result = {"sent": False, "reason": "SUPERPLANE_WEBHOOK_URL not set", "incident": incident}
        db.save_webhook_delivery(run_id, False, result["reason"], 0, incident)
        return result

    if IS_PRODUCTION and not SUPERPLANE_WEBHOOK_SECRET:
        result = {
            "sent": False,
            "reason": "SUPERPLANE_WEBHOOK_SECRET required in production",
            "incident": incident,
        }
        db.save_webhook_delivery(run_id, False, result["reason"], 0, incident)
        return result

    data = json.dumps(incident, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Idempotency-Key": run_id,
    }
    if SUPERPLANE_WEBHOOK_SECRET:
        signature = sign_webhook_payload(data, SUPERPLANE_WEBHOOK_SECRET)
        headers[SUPERPLANE_WEBHOOK_SIGNATURE_HEADER] = f"sha256={signature}"

    last_reason = "unknown error"
    for attempt in range(1, WEBHOOK_MAX_ATTEMPTS + 1):
        req = urllib.request.Request(
            SUPERPLANE_WEBHOOK_URL,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = {"sent": True, "status": resp.status, "attempts": attempt, "incident": incident}
                db.save_webhook_delivery(run_id, True, None, attempt, incident)
                result["slack"] = notify_slack(incident)
                log.info(
                    "webhook delivered",
                    extra={"run_id": run_id, "event": "webhook_sent", "attempt": attempt},
                )
                return result
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            last_reason = f"HTTP {e.code}: {body or e.reason}"
            log.warning(
                "webhook HTTP error",
                extra={"run_id": run_id, "event": "webhook_retry", "attempt": attempt},
            )
        except Exception as e:
            last_reason = str(e)
            log.warning(
                "webhook error",
                extra={"run_id": run_id, "event": "webhook_retry", "attempt": attempt},
            )
        if attempt < WEBHOOK_MAX_ATTEMPTS:
            time.sleep(WEBHOOK_RETRY_BACKOFF_SEC * attempt)

    result = {"sent": False, "reason": last_reason, "attempts": WEBHOOK_MAX_ATTEMPTS, "incident": incident}
    db.save_webhook_delivery(run_id, False, last_reason, WEBHOOK_MAX_ATTEMPTS, incident)
    log.error("webhook failed", extra={"run_id": run_id, "event": "webhook_failed"})
    return result
