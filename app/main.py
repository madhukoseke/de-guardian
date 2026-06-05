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
    """
    Perform startup validation, initialize the database, and prepare runtime state before the application serves requests.
    
    If configuration validation returns errors, log each error and raise RuntimeError when running in production. Initialize the database (strict mode enabled when in production and DATABASE_URL is set) and log the current armed mode for JOB_NAME. Yields control to run the application; returning from the yield continues shutdown.
    
    Raises:
        RuntimeError: If startup validation produced errors and IS_PRODUCTION is true.
    
    """
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
    """
    Provide a service descriptor summarizing the application state and exposed endpoints.
    
    Returns:
        dict: A mapping containing:
            - "service": the service/job name.
            - "armed_mode": current armed failure mode for the job.
            - "auth_required": whether API key auth is required.
            - "production": whether the app is running in production.
            - "endpoints": list of exposed endpoint paths and query signatures.
    """
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
    """
    Report service health by probing the database and returning the probe details.
    
    When the database probe is not OK, responds with an HTTP 503 JSONResponse containing the probe content; otherwise returns a mapping that includes "ok": True plus the probe fields.
    
    Returns:
        dict | JSONResponse: If healthy, a mapping with `"ok": True` merged with the probe details; if unhealthy, a JSONResponse with status code 503 and the probe content.
    """
    probe = db.check_health()
    if not probe.get("ok"):
        return JSONResponse(status_code=503, content=probe)
    return {"ok": True, **probe}


@app.get("/modes")
def modes():
    """
    Provide the available failure modes including the 'healthy' mode.
    
    Returns:
        dict: Mapping of mode name to a short human-readable description; includes 'healthy' and the configured failure modes.
    """
    return {"healthy": "Normal run, no failure.", **FAILURE_MODES}


@app.post("/break", dependencies=[Depends(verify_api_key)])
def break_pipeline(mode: str = Query(..., description="A failure mode key from /modes")):
    """
    Set the pipeline's armed failure mode.
    
    Parameters:
        mode (str): A failure mode key from /modes — either "healthy" or one of the keys in FAILURE_MODES.
    
    Returns:
        On success, a dict with `armed_mode` (the mode now armed) and `note` (a short message). On invalid mode, a JSONResponse with HTTP 400 containing `error` and `valid` (the list of valid mode keys).
    """
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
    """
    Restore the pipeline to healthy mode and record the remediation event.
    
    Returns:
        dict: A dictionary with keys:
            - "armed_mode": the new armed mode, set to "healthy".
            - "note": a human-readable message describing the remediation.
    """
    db.set_armed_mode(JOB_NAME, "healthy")
    db.record_heal(JOB_NAME)
    log.info("heal applied", extra={"event": "heal", "armed_mode": "healthy"})
    return {"armed_mode": "healthy", "note": "remediation applied — pipeline restored"}


@app.post("/run", dependencies=[Depends(verify_api_key)])
def run():
    """
    Trigger a web-initiated pipeline run, persist its result, and emit an incident if the run failed.
    
    Returns:
        dict | JSONResponse: On a non-failed run, returns {"run": <run_dict>}.
        On a failed run, returns a dict containing:
            - "run": the persisted run record
            - "incident_emitted": `true` if an incident webhook was sent, `false` otherwise
            - "incident_error": an error message when emission failed (if any)
            - "webhook_attempts": number of emission attempts
            - "incident": the incident payload or details produced by the emitter
        If the run failed and incident emission was not sent while running in production, returns a JSONResponse with HTTP 503 whose content matches the failed-run dict and includes the "incident" field.
    """
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
    """
    Provide the service's current armed mode and the most recent run record.
    
    Returns:
        dict: Mapping with keys:
            - armed_mode (str): the currently armed failure mode for JOB_NAME.
            - last_run (Any | None): the most recent saved run record, or None if no run has been recorded.
    """
    return {"armed_mode": db.get_armed_mode(JOB_NAME), "last_run": STATE["last_run"]}


@app.get("/runs")
def runs(limit: int = Query(default=RUNS_LIMIT_DEFAULT, ge=1, le=RUNS_LIMIT_MAX)):
    """
    Return recent pipeline run records limited by `limit`.
    
    Parameters:
        limit (int): Maximum number of runs to return; must be between 1 and RUNS_LIMIT_MAX (defaults to RUNS_LIMIT_DEFAULT).
    
    Returns:
        dict: A mapping with key `"runs"` containing a list of recent run records.
    """
    return {"runs": db.recent_runs(limit)}


@app.get("/memory")
def recall_memory(mode: str = Query(..., description="A failure mode key from /modes")):
    """
    Return contextual memory and an automated investigation for a given failure mode.
    
    Validates that `mode` is one of the known failure modes, then loads recent runs and heal events and returns the memory recall combined with a resolved `investigation` for a synthetic run using the given mode.
    
    Parameters:
        mode (str): A failure-mode key (see /modes).
    
    Returns:
        dict | JSONResponse: On success, a dictionary containing the memory recall fields plus an `investigation` entry with the resolved investigation details. If `mode` is not a valid failure mode, returns a JSONResponse with HTTP 400 and an error payload describing valid modes.
    """
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
    """
    List recent incident statuses stored in Postgres.
    
    Parameters:
        limit (int): Maximum number of incidents to return (must be between 1 and 200).
    
    Returns:
        dict: A mapping with key `"incidents"` containing a list of incident records retrieved from the database.
    """
    return {"incidents": db.list_incidents(limit)}


@app.post("/incidents/status", dependencies=[Depends(verify_api_key)])
def sync_incident_status(body: IncidentStatusBody):
    """
    Accept and upsert a final incident status and RCA sent from an external system.
    
    Upserts the provided run's status and optional RCA into the incident store and logs the sync.
    
    Parameters:
        body (IncidentStatusBody): Request body containing `run_id`, `status`, and optional `rca`.
    
    Returns:
        dict: {"ok": True, "run_id": <str>, "status": <str>} indicating the upserted run ID and status.
    """
    db.upsert_incident_status(body.run_id, body.status, body.rca)
    log.info("incident status synced", extra={"run_id": body.run_id, "event": "incident_sync"})
    return {"ok": True, "run_id": body.run_id, "status": body.status}
