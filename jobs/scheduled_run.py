"""
Cron entrypoint — this is the scheduled "daily" run of the pipeline, deployed
as a Render Cron Job (your 3rd Render Service). It calls the same pipeline
logic and emits an incident to SuperPlane if the run fails, so a failure that
happens at 6am unattended still kicks off the agent investigation.

Run: python -m jobs.scheduled_run
"""

from __future__ import annotations

import os
import sys

from app.pipeline import run_pipeline
from app.events import emit_incident
from app import db


def main() -> int:
    db.init_db()
    # A cron run uses whatever mode the operator armed via an env var, defaulting
    # to healthy. (For the demo you can also just break it from the web service.)
    mode = os.environ.get("PIPELINE_MODE", "healthy")
    result = run_pipeline(mode=mode, last_success_at=db.last_success_at())
    run_dict = result.to_dict()
    db.save_run(run_dict)

    print(f"[{result.run_id}] {result.job_name} -> {result.status} "
          f"(in={result.rows_in}, out={result.rows_out}, {result.duration_ms}ms)")

    if result.status == "failed":
        emission = emit_incident(run_dict)
        print(f"  error: {result.error_type}: {result.error_message}")
        print(f"  incident emitted to SuperPlane: {emission.get('sent')}")
        return 1  # non-zero exit so Render marks the cron run as failed too
    return 0


if __name__ == "__main__":
    sys.exit(main())
