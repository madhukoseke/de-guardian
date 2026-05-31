"""
DE-Guardian — control surface for the simulated pipeline.

Production endpoints require API_KEY (Authorization: Bearer … or X-API-Key).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import db, memory
from app.adapters.registry import execute_run
from app.auth import verify_api_key
from app.config import (
    IS_PRODUCTION,
    RUNS_LIMIT_DEFAULT,
    RUNS_LIMIT_MAX,
    auth_required,
    validate_startup,
)
from app.events import emit_incident
from app.logging_config import configure_logging
from app.pipeline import FAILURE_MODES, JOB_NAME

configure_logging()
log = logging.getLogger(__name__)

STATE: dict[str, Any] = {"last_run": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = validate_startup()
    if errors:
        for msg in errors:
            log.error(msg, extra={"event": "startup_config_error"})
        if IS_PRODUCTION:
            raise RuntimeError("; ".join(errors))
    db.init_db(strict=IS_PRODUCTION and bool(__import__("os").environ.get("DATABASE_URL")))
    armed = db.get_armed_mode(JOB_NAME)
    log.info("startup complete", extra={"event": "startup", "armed_mode": armed})
    yield


app = FastAPI(
    title="DE-Guardian — Pipeline Incident Investigator",
    version="2.0.0",
    lifespan=lifespan,
)


class IncidentStatusBody(BaseModel):
    run_id: str
    status: str
    rca: str | None = None


@app.get("/")
def root():
    return {
        "service": JOB_NAME,
        "armed_mode": db.get_armed_mode(JOB_NAME),
        "auth_required": auth_required(),
        "production": IS_PRODUCTION,
        "endpoints": [
            "/run",
            "/break?mode=",
            "/heal",
            "/status",
            "/runs",
            "/memory?mode=",
            "/incidents",
            "/modes",
            "/health",
        ],
    }


@app.get("/health")
def health():
    probe = db.check_health()
    if not probe.get("ok"):
        return JSONResponse(status_code=503, content=probe)
    return {"ok": True, **probe}


@app.get("/modes")
def modes():
    return {"healthy": "Normal run, no failure.", **FAILURE_MODES}


@app.post("/break", dependencies=[Depends(verify_api_key)])
def break_pipeline(mode: str = Query(..., description="A failure mode key from /modes")):
    if mode != "healthy" and mode not in FAILURE_MODES:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown mode '{mode}'", "valid": list(FAILURE_MODES)},
        )
    db.set_armed_mode(JOB_NAME, mode)
    log.info("armed failure mode", extra={"event": "break", "armed_mode": mode})
    return {"armed_mode": mode, "note": "next /run will fail with this mode" if mode != "healthy" else "healthy"}


@app.post("/heal", dependencies=[Depends(verify_api_key)])
def heal():
    db.set_armed_mode(JOB_NAME, "healthy")
    db.record_heal(JOB_NAME)
    log.info("heal applied", extra={"event": "heal", "armed_mode": "healthy"})
    return {"armed_mode": "healthy", "note": "remediation applied — pipeline restored"}


@app.post("/run", dependencies=[Depends(verify_api_key)])
def run():
    mode = db.get_armed_mode(JOB_NAME)
    after_heal = db.consume_pending_heal(JOB_NAME)
    result = execute_run(
        mode=mode,
        last_success_at=db.last_success_at(),
        source="web",
        after_heal=after_heal,
    )
    run_dict = result.to_dict()
    db.save_run(run_dict)
    STATE["last_run"] = run_dict

    if result.status == "failed":
        emission = emit_incident(run_dict)
        body = {
            "run": run_dict,
            "incident_emitted": emission.get("sent"),
            "incident_error": emission.get("reason"),
            "webhook_attempts": emission.get("attempts"),
        }
        if not emission.get("sent") and IS_PRODUCTION:
            return JSONResponse(status_code=503, content={**body, "incident": emission.get("incident")})
        return {**body, "incident": emission.get("incident")}
    return {"run": run_dict}


@app.get("/status")
def status():
    return {"armed_mode": db.get_armed_mode(JOB_NAME), "last_run": STATE["last_run"]}


@app.get("/runs")
def runs(limit: int = Query(default=RUNS_LIMIT_DEFAULT, ge=1, le=RUNS_LIMIT_MAX)):
    return {"runs": db.recent_runs(limit)}


@app.get("/memory")
def recall_memory(mode: str = Query(..., description="A failure mode key from /modes")):
    if mode not in FAILURE_MODES:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown mode '{mode}'", "valid": list(FAILURE_MODES)},
        )
    runs = db.recent_runs(200)
    heals = db.heal_events(JOB_NAME, 200)
    mem = memory.recall(mode, JOB_NAME, runs, heal_events=heals)
    synthetic_run = {"failure_mode": mode, "job_name": JOB_NAME}
    return {
        **mem,
        "investigation": memory.resolve(synthetic_run, runs, recall_result=mem, heal_events=heals),
    }


@app.get("/incidents")
def incidents(limit: int = Query(default=50, ge=1, le=200)):
    """Postgres-backed incident statuses synced from SuperPlane canvas."""
    return {"incidents": db.list_incidents(limit)}


@app.post("/incidents/status", dependencies=[Depends(verify_api_key)])
def sync_incident_status(body: IncidentStatusBody):
    """Dual-memory sync: canvas POSTs final status + RCA back to the service."""
    db.upsert_incident_status(body.run_id, body.status, body.rca)
    log.info("incident status synced", extra={"run_id": body.run_id, "event": "incident_sync"})
    return {"ok": True, "run_id": body.run_id, "status": body.status}
