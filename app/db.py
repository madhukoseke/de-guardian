"""
Run-history store. Uses Render Postgres when DATABASE_URL is set (your 2nd
Render Service), and falls back to an in-memory list so the app still runs
locally with zero setup.

The full run history is your audit trail — show it on stage as proof that
the agent's actions are logged and queryable, which is the whole SuperPlane
"safe agents near prod" thesis.
"""

from __future__ import annotations

import os
import json
import threading
from typing import Any

DATABASE_URL = os.environ.get("DATABASE_URL")

_mem_lock = threading.Lock()
_mem_runs: list[dict] = []

_pg = None
_db_ready = False
if DATABASE_URL:
    try:
        import psycopg
        _pg = psycopg
    except Exception:  # pragma: no cover - psycopg optional locally
        _pg = None


def _conn():
    # Render Postgres external URLs sometimes use the postgres:// scheme.
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1) if DATABASE_URL else None
    return _pg.connect(url, autocommit=True, connect_timeout=10)


def init_db() -> None:
    """Create tables if Postgres is available. Never raises — falls back to memory."""
    global _db_ready
    if _db_ready or not (_pg and DATABASE_URL):
        return
    try:
        with _conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id        TEXT PRIMARY KEY,
                    job_name      TEXT,
                    status        TEXT,
                    started_at    TIMESTAMPTZ,
                    finished_at   TIMESTAMPTZ,
                    duration_ms   INTEGER,
                    rows_in       INTEGER,
                    rows_out      INTEGER,
                    failure_mode  TEXT,
                    error_type    TEXT,
                    error_message TEXT,
                    payload       JSONB
                )
                """
            )
        _db_ready = True
    except Exception:  # pragma: no cover - Render cold-start / transient DB
        _db_ready = False


def _pg_available() -> bool:
    init_db()
    return _db_ready


def save_run(run: dict[str, Any]) -> None:
    if _pg_available():
        with _conn() as c:
            c.execute(
                """
                INSERT INTO pipeline_runs
                    (run_id, job_name, status, started_at, finished_at,
                     duration_ms, rows_in, rows_out, failure_mode,
                     error_type, error_message, payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (
                    run["run_id"], run["job_name"], run["status"],
                    run["started_at"], run["finished_at"], run["duration_ms"],
                    run["rows_in"], run["rows_out"], run.get("failure_mode"),
                    run.get("error_type"), run.get("error_message"),
                    json.dumps(run),
                ),
            )
        return
    with _mem_lock:
        _mem_runs.insert(0, run)
        del _mem_runs[100:]


def recent_runs(limit: int = 20) -> list[dict]:
    if _pg_available():
        with _conn() as c:
            cur = c.execute(
                "SELECT payload FROM pipeline_runs ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            return [row[0] for row in cur.fetchall()]
    with _mem_lock:
        return list(_mem_runs[:limit])


def last_success_at() -> str | None:
    for r in recent_runs(100):
        if r.get("status") == "success":
            return r.get("finished_at")
    return None
