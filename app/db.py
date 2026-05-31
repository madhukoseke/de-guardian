"""
Run-history store, operational state, heal events, and webhook delivery audit.

Uses Render Postgres when DATABASE_URL is set. In production, Postgres is required
and failures are loud — no silent in-memory fallback.
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import DATABASE_URL, IS_PRODUCTION

log = logging.getLogger(__name__)

_mem_lock = threading.Lock()
_mem_runs: list[dict] = []
_mem_state: dict[str, str] = {}
_mem_heals: list[dict] = []
_mem_webhooks: dict[str, dict] = {}
_mem_incidents: dict[str, dict] = {}

_pg = None
_pool = None
_db_ready = False
_db_error: str | None = None

if DATABASE_URL:
    try:
        import psycopg
        from psycopg_pool import ConnectionPool

        _pg = psycopg
    except Exception as exc:  # pragma: no cover
        _pg = None
        _db_error = str(exc)


def _db_url() -> str | None:
    if not DATABASE_URL:
        return None
    return DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _use_memory_store() -> bool:
    if IS_PRODUCTION and DATABASE_URL:
        return False
    return not _pg_available()


def _pg_available() -> bool:
    init_db()
    return _db_ready


@contextmanager
def _connection() -> Iterator[Any]:
    global _pool
    url = _db_url()
    if not (_pg and url and _db_ready):
        raise RuntimeError(_db_error or "Postgres not available")
    if _pool is None:
        _pool = ConnectionPool(url, min_size=1, max_size=5, timeout=10)
    with _pool.connection() as conn:
        yield conn


def init_db(*, strict: bool = False) -> None:
    """Create tables and verify connectivity. strict=True raises on failure."""
    global _db_ready, _db_error
    if _db_ready:
        return
    if not (_pg and DATABASE_URL):
        if strict and IS_PRODUCTION and DATABASE_URL:
            raise RuntimeError(_db_error or "psycopg not installed but DATABASE_URL is set")
        return
    try:
        url = _db_url()
        with _pg.connect(url, autocommit=True, connect_timeout=10) as c:
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
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs (started_at DESC)"
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    job_name    TEXT PRIMARY KEY,
                    armed_mode  TEXT NOT NULL DEFAULT 'healthy',
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS heal_events (
                    id          BIGSERIAL PRIMARY KEY,
                    job_name    TEXT NOT NULL,
                    healed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    run_id      TEXT PRIMARY KEY,
                    sent        BOOLEAN NOT NULL,
                    reason      TEXT,
                    attempts    INTEGER NOT NULL,
                    payload     JSONB,
                    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_status (
                    run_id      TEXT PRIMARY KEY,
                    status      TEXT NOT NULL,
                    rca         TEXT,
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    payload     JSONB
                )
                """
            )
            c.execute("SELECT 1")
        _db_ready = True
        _db_error = None
    except Exception as exc:
        _db_ready = False
        _db_error = str(exc)
        log.error("database init failed", extra={"event": "db_init_failed"})
        if strict:
            raise RuntimeError(f"Postgres unavailable: {exc}") from exc


def check_health() -> dict[str, Any]:
    """Deep health probe for /health."""
    if not DATABASE_URL:
        return {"database": "not_configured", "ok": True}
    try:
        init_db(strict=False)
        if not _db_ready:
            return {"database": "unavailable", "ok": False, "error": _db_error}
        with _connection() as c:
            c.execute("SELECT 1")
        return {"database": "ok", "ok": True}
    except Exception as exc:
        return {"database": "unavailable", "ok": False, "error": str(exc)}


def save_run(run: dict[str, Any]) -> None:
    if _pg_available():
        with _connection() as c:
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
                    run["run_id"],
                    run["job_name"],
                    run["status"],
                    run["started_at"],
                    run["finished_at"],
                    run["duration_ms"],
                    run["rows_in"],
                    run["rows_out"],
                    run.get("failure_mode"),
                    run.get("error_type"),
                    run.get("error_message"),
                    json.dumps(run),
                ),
            )
        return
    if IS_PRODUCTION and DATABASE_URL:
        raise RuntimeError(f"Postgres required in production but unavailable: {_db_error}")
    with _mem_lock:
        _mem_runs.insert(0, run)
        del _mem_runs[100:]


def recent_runs(limit: int = 20) -> list[dict]:
    limit = max(1, min(limit, 500))
    if _pg_available():
        with _connection() as c:
            cur = c.execute(
                "SELECT payload FROM pipeline_runs ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            return [row[0] for row in cur.fetchall()]
    if IS_PRODUCTION and DATABASE_URL:
        raise RuntimeError(f"Postgres required in production but unavailable: {_db_error}")
    with _mem_lock:
        return list(_mem_runs[:limit])


def last_success_at() -> str | None:
    for r in recent_runs(100):
        if r.get("status") == "success":
            return r.get("finished_at")
    return None


def get_armed_mode(job_name: str) -> str:
    if _pg_available():
        with _connection() as c:
            row = c.execute(
                "SELECT armed_mode FROM pipeline_state WHERE job_name = %s",
                (job_name,),
            ).fetchone()
            if row:
                return row[0]
            return "healthy"
    with _mem_lock:
        return _mem_state.get(job_name, "healthy")


def set_armed_mode(job_name: str, mode: str) -> None:
    if _pg_available():
        with _connection() as c:
            c.execute(
                """
                INSERT INTO pipeline_state (job_name, armed_mode, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (job_name) DO UPDATE
                SET armed_mode = EXCLUDED.armed_mode, updated_at = NOW()
                """,
                (job_name, mode),
            )
        return
    with _mem_lock:
        _mem_state[job_name] = mode


def record_heal(job_name: str) -> None:
    if _pg_available():
        with _connection() as c:
            c.execute(
                "INSERT INTO heal_events (job_name, healed_at) VALUES (%s, NOW())",
                (job_name,),
            )
        return
    with _mem_lock:
        _mem_heals.append({"job_name": job_name})


def heal_events(job_name: str, limit: int = 100) -> list[dict]:
    if _pg_available():
        with _connection() as c:
            cur = c.execute(
                """
                SELECT job_name, healed_at::text AS healed_at
                FROM heal_events
                WHERE job_name = %s
                ORDER BY healed_at ASC
                LIMIT %s
                """,
                (job_name, limit),
            )
            return [{"job_name": r[0], "healed_at": r[1]} for r in cur.fetchall()]
    with _mem_lock:
        return list(_mem_heals)


def consume_pending_heal(job_name: str) -> bool:
    """True if a heal was recorded since the last run consumed one (web /run after /heal)."""
    # For web runs: any heal event after the most recent run counts.
    heals = heal_events(job_name)
    if not heals:
        return False
    runs = recent_runs(1)
    if not runs:
        return True
    last_finished = runs[0].get("finished_at") or ""
    return any(h.get("healed_at", "") > last_finished for h in heals)


def save_webhook_delivery(
    run_id: str,
    sent: bool,
    reason: str | None,
    attempts: int,
    payload: dict | None = None,
) -> None:
    if _pg_available():
        with _connection() as c:
            c.execute(
                """
                INSERT INTO webhook_deliveries (run_id, sent, reason, attempts, payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE
                SET sent = EXCLUDED.sent, reason = EXCLUDED.reason,
                    attempts = EXCLUDED.attempts, payload = EXCLUDED.payload,
                    delivered_at = NOW()
                """,
                (run_id, sent, reason, attempts, json.dumps(payload) if payload else None),
            )
        return
    with _mem_lock:
        _mem_webhooks[run_id] = {
            "sent": sent,
            "reason": reason,
            "attempts": attempts,
        }


def get_webhook_delivery(run_id: str) -> dict | None:
    if _pg_available():
        with _connection() as c:
            row = c.execute(
                "SELECT sent, reason, attempts FROM webhook_deliveries WHERE run_id = %s",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            return {"sent": row[0], "reason": row[1], "attempts": row[2]}
    with _mem_lock:
        return _mem_webhooks.get(run_id)


def upsert_incident_status(run_id: str, status: str, rca: str | None = None, payload: dict | None = None) -> None:
    """Sync SuperPlane canvas outcomes back to Postgres (dual-memory strategy)."""
    if _pg_available():
        with _connection() as c:
            c.execute(
                """
                INSERT INTO incident_status (run_id, status, rca, payload, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (run_id) DO UPDATE
                SET status = EXCLUDED.status, rca = EXCLUDED.rca,
                    payload = EXCLUDED.payload, updated_at = NOW()
                """,
                (run_id, status, rca, json.dumps(payload) if payload else None),
            )
        return
    with _mem_lock:
        _mem_incidents[run_id] = {"status": status, "rca": rca, "payload": payload}


def list_incidents(limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 200))
    if _pg_available():
        with _connection() as c:
            cur = c.execute(
                """
                SELECT run_id, status, rca, updated_at::text, payload
                FROM incident_status
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [
                {
                    "run_id": r[0],
                    "status": r[1],
                    "rca": r[2],
                    "updated_at": r[3],
                    "payload": r[4],
                }
                for r in cur.fetchall()
            ]
    with _mem_lock:
        return list(_mem_incidents.values())[:limit]
