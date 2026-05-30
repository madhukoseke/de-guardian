"""
On a failed run, emit a rich incident event to the SuperPlane Canvas webhook
trigger (set SUPERPLANE_WEBHOOK_URL). The payload carries everything the Claude
component needs to produce a real root-cause analysis — logs, the offending
record, recent changes, and the last successful run.
"""

from __future__ import annotations

import os
import json
import urllib.request
from typing import Any

SUPERPLANE_WEBHOOK_URL = os.environ.get("SUPERPLANE_WEBHOOK_URL")
SERVICE_BASE_URL = os.environ.get("SERVICE_BASE_URL", "http://localhost:8000").rstrip("/")


def build_incident(run: dict[str, Any]) -> dict[str, Any]:
    """Shape a failed run into the incident event the Canvas consumes."""
    return {
        "event": "pipeline.failed",
        "severity": "P2",
        "job_name": run.get("job_name"),
        "run_id": run.get("run_id"),
        "failed_at": run.get("finished_at"),
        "duration_ms": run.get("duration_ms"),
        "rows_in": run.get("rows_in"),
        "error": {
            "type": run.get("error_type"),
            "message": run.get("error_message"),
            "failure_mode": run.get("failure_mode"),
            "offending_record": run.get("offending_record"),
            "traceback": run.get("traceback"),
        },
        "context": {
            "last_success_at": run.get("last_success_at"),
            "recent_changes": run.get("recent_changes"),
            "service": os.environ.get("RENDER_SERVICE_NAME", "local"),
            "heal_endpoint": "/heal",
            "heal_url": f"{SERVICE_BASE_URL}/heal",
            "run_url": f"{SERVICE_BASE_URL}/run",
            "status_url": f"{SERVICE_BASE_URL}/status",
        },
    }


def emit_incident(run: dict[str, Any]) -> dict[str, Any]:
    incident = build_incident(run)
    if not SUPERPLANE_WEBHOOK_URL:
        # No webhook configured (e.g. local dev) — return the payload so the
        # caller can still surface/log it.
        return {"sent": False, "reason": "SUPERPLANE_WEBHOOK_URL not set", "incident": incident}

    data = json.dumps(incident).encode("utf-8")
    req = urllib.request.Request(
        SUPERPLANE_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"sent": True, "status": resp.status, "incident": incident}
    except Exception as e:  # pragma: no cover
        return {"sent": False, "reason": str(e), "incident": incident}
