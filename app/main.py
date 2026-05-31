"""
DE-Guardian — control surface for the simulated pipeline.

  GET  /            -> status + quick links
  GET  /health      -> Render health check
  POST /run         -> run the pipeline once (emits an incident on failure)
  POST /break       -> arm a failure mode, e.g. ?mode=schema_drift
  POST /heal        -> clear failure mode (the Canvas calls this after approval)
  GET  /status      -> current mode + last run
  GET  /runs        -> recent run history (the audit trail)
  GET  /memory      -> incident memory for a failure mode (what the agent recalls)
  GET  /modes       -> list available failure modes
"""

from __future__ import annotations

import os
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.pipeline import run_pipeline, FAILURE_MODES, JOB_NAME
from app.events import emit_incident
from app import db, memory

app = FastAPI(title="DE-Guardian — Pipeline Incident Investigator", version="1.0.0")

# In-process state: which failure mode is currently armed ("healthy" = none).
STATE = {"mode": "healthy", "last_run": None}


@app.get("/")
def root():
    return {
        "service": JOB_NAME,
        "armed_mode": STATE["mode"],
        "endpoints": ["/run", "/break?mode=", "/heal", "/status", "/runs", "/memory?mode=", "/modes", "/health"],
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
        return {
            "run": run_dict,
            "incident_emitted": emission.get("sent"),
            "incident_error": emission.get("reason"),
            "incident": emission.get("incident"),
        }
    return {"run": run_dict}


@app.get("/status")
def status():
    return {"armed_mode": STATE["mode"], "last_run": STATE["last_run"]}


@app.get("/runs")
def runs(limit: int = 20):
    return {"runs": db.recent_runs(limit)}


@app.get("/memory")
def recall_memory(mode: str = Query(..., description="A failure mode key from /modes")):
    """What the agent recalls about a failure mode: prior occurrences and how
    often the next run recovered. This block is embedded in every incident."""
    return memory.recall(mode, JOB_NAME, db.recent_runs(200))
