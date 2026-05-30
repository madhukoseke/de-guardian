"""
SuperPlane "Bash Script Funeral" demo — control surface for the pipeline.

Endpoints (all designed for a live stage demo):
  GET  /            -> status + quick links
  GET  /health      -> Render health check
  POST /run         -> run the pipeline once (emits an incident to SuperPlane on failure)
  POST /break       -> arm a failure mode, e.g. ?mode=schema_drift   (break it live)
  POST /heal        -> clear failure mode (this is what the Canvas calls after approval)
  GET  /status      -> current mode + last run
  GET  /runs        -> recent run history (the audit trail)
  GET  /modes       -> list available failure modes
"""

from __future__ import annotations

import os
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.pipeline import run_pipeline, FAILURE_MODES, JOB_NAME
from app.events import emit_incident
from app import db

app = FastAPI(title="Bash Script Funeral — Pipeline Demo", version="1.0.0")

# In-process state: which failure mode is currently armed ("healthy" = none).
STATE = {"mode": "healthy", "last_run": None}


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/")
def root():
    return {
        "service": JOB_NAME,
        "armed_mode": STATE["mode"],
        "endpoints": ["/run", "/break?mode=", "/heal", "/status", "/runs", "/modes", "/health"],
        "webhook_configured": bool(os.environ.get("SUPERPLANE_WEBHOOK_URL")),
        "webhook_signature_configured": bool(os.environ.get("SUPERPLANE_WEBHOOK_SECRET")),
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/modes")
def modes():
    return {"healthy": "Normal run, no failure.", **FAILURE_MODES}


@app.post("/break")
def break_pipeline(mode: str = Query(..., description="A failure mode key from /modes")):
    if mode != "healthy" and mode not in FAILURE_MODES:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown mode '{mode}'", "valid": list(FAILURE_MODES)},
        )
    STATE["mode"] = mode
    return {"armed_mode": mode, "note": "next /run will fail with this mode" if mode != "healthy" else "healthy"}


@app.post("/heal")
def heal():
    STATE["mode"] = "healthy"
    return {"armed_mode": "healthy", "note": "remediation applied — pipeline restored"}


@app.post("/run")
def run():
    result = run_pipeline(mode=STATE["mode"], last_success_at=db.last_success_at())
    run_dict = result.to_dict()
    db.save_run(run_dict)
    STATE["last_run"] = run_dict

    if result.status == "failed":
        emission = emit_incident(run_dict)
        return {"run": run_dict, "incident_emitted": emission.get("sent"), "incident": emission.get("incident")}
    return {"run": run_dict}


@app.get("/status")
def status():
    return {"armed_mode": STATE["mode"], "last_run": STATE["last_run"]}


@app.get("/runs")
def runs(limit: int = 20):
    return {"runs": db.recent_runs(limit)}
