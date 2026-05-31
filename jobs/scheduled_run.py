"""
Cron entrypoint — the scheduled "daily" run, deployed as a Render Cron Job.
Uses the same Postgres-backed armed mode as the web service.
"""

from __future__ import annotations

import logging
import os
import sys

from app.adapters.registry import execute_run
from app.events import emit_incident
from app import db
from app.logging_config import configure_logging
from app.pipeline import JOB_NAME

configure_logging()
log = logging.getLogger(__name__)


def main() -> int:
    db.init_db(strict=bool(os.environ.get("DATABASE_URL")))
    mode = db.get_armed_mode(JOB_NAME)
    if os.environ.get("PIPELINE_MODE") and os.environ.get("PIPELINE_MODE") != "healthy":
        mode = os.environ["PIPELINE_MODE"]
        db.set_armed_mode(JOB_NAME, mode)

    result = execute_run(
        mode=mode,
        last_success_at=db.last_success_at(),
        source="cron",
    )
    run_dict = result.to_dict()
    db.save_run(run_dict)

    log.info(
        "cron run finished",
        extra={
            "run_id": result.run_id,
            "event": "cron_run",
            "status": result.status,
        },
    )
    print(
        f"[{result.run_id}] {result.job_name} -> {result.status} "
        f"(in={result.rows_in}, out={result.rows_out}, {result.duration_ms}ms)"
    )

    if result.status == "failed":
        emission = emit_incident(run_dict)
        print(f"  error: {result.error_type}: {result.error_message}")
        print(f"  incident emitted to SuperPlane: {emission.get('sent')}")
        if not emission.get("sent"):
            print(f"  webhook error: {emission.get('reason')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
