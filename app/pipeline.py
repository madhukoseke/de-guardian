"""
daily_revenue_aggregation — a simulated fintech data pipeline.

In healthy mode it pulls synthetic transactions, aggregates revenue per
merchant, and "loads" the result. Each failure mode reproduces a real,
recognizable data-engineering incident so the agent has something concrete
to investigate.
"""

from __future__ import annotations

import random
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any

JOB_NAME = "daily_revenue_aggregation"

# Failure modes you can trigger live from the stage via POST /break?mode=...
FAILURE_MODES = {
    "schema_drift": "Upstream renamed `amount` -> `txn_amount`; transform still reads `amount`.",
    "null_violation": "A transaction arrived with NULL revenue; target column is NOT NULL.",
    "upstream_timeout": "Source API returned 504 Gateway Timeout after 30s.",
    "type_mismatch": "Revenue value 'N/A' could not be cast to numeric.",
    "duplicate_pk": "Duplicate transaction_id violates the primary key on load.",
}

# A fake recent-change log so the agent can reason about *why* it broke now.
RECENT_CHANGES = [
    {
        "sha": "a3f91c2",
        "author": "data-platform-bot",
        "when": "2h ago",
        "message": "feat(ingest): bump source-api client to v3 (response schema changed)",
    },
    {
        "sha": "7d20e5b",
        "author": "mkoseke",
        "when": "yesterday",
        "message": "chore(dbt): tighten revenue column to NOT NULL",
    },
    {
        "sha": "1c884aa",
        "author": "ci",
        "when": "3 days ago",
        "message": "ops: move daily_revenue_aggregation to 06:00 UTC cron",
    },
]


class PipelineError(Exception):
    """Carries structured context the agent can investigate."""

    def __init__(self, error_type: str, message: str, offending_record: dict | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.offending_record = offending_record or {}


@dataclass
class RunResult:
    run_id: str
    job_name: str
    status: str  # "success" | "failed"
    started_at: str
    finished_at: str
    duration_ms: int
    rows_in: int
    rows_out: int
    failure_mode: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    traceback: str | None = None
    offending_record: dict = field(default_factory=dict)
    recent_changes: list = field(default_factory=list)
    last_success_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _synthetic_transactions(n: int = 5000) -> list[dict]:
    merchants = ["mk-coffee", "grandline-goods", "milpitas-mart", "arc-payments", "quiet-store"]
    return [
        {
            "transaction_id": str(uuid.uuid4()),
            "merchant": random.choice(merchants),
            "amount": round(random.uniform(1.0, 480.0), 2),
            "currency": "USD",
        }
        for _ in range(n)
    ]


def _aggregate(rows: list[dict], mode: str) -> list[dict]:
    """Transform step. Each failure mode breaks here in a realistic way."""
    # --- inject the failure exactly where a real pipeline would break ---
    if mode == "upstream_timeout":
        raise PipelineError(
            "UpstreamTimeout",
            "source-api GET /v3/transactions timed out after 30000ms (504)",
        )

    if mode == "schema_drift":
        # source v3 renamed the field; transform still references the old key
        for r in rows:
            r["txn_amount"] = r.pop("amount")
        sample = rows[0]
        # KeyError is what the real job throws — capture it as structured context
        if "amount" not in sample:
            raise PipelineError(
                "SchemaDrift",
                "KeyError: 'amount' — field missing from source payload (found 'txn_amount')",
                offending_record=sample,
            )

    if mode == "null_violation":
        bad = dict(rows[42])
        bad["amount"] = None
        rows[42] = bad
        raise PipelineError(
            "NullConstraintViolation",
            "null value in column \"revenue\" violates not-null constraint",
            offending_record=rows[42],
        )

    if mode == "type_mismatch":
        bad = dict(rows[7])
        bad["amount"] = "N/A"
        rows[7] = bad
        raise PipelineError(
            "TypeCastError",
            "could not convert string 'N/A' to numeric for column revenue",
            offending_record=rows[7],
        )

    if mode == "duplicate_pk":
        rows.append(dict(rows[0]))  # same transaction_id twice
        raise PipelineError(
            "DuplicatePrimaryKey",
            f"duplicate key value violates unique constraint \"revenue_pkey\" "
            f"(transaction_id={rows[0]['transaction_id']})",
            offending_record=rows[0],
        )

    # --- healthy path ---
    totals: dict[str, float] = {}
    for r in rows:
        totals[r["merchant"]] = totals.get(r["merchant"], 0.0) + r["amount"]
    return [{"merchant": m, "revenue": round(v, 2)} for m, v in totals.items()]


def run_pipeline(mode: str = "healthy", last_success_at: str | None = None) -> RunResult:
    """Execute one run. `mode` is 'healthy' or a key from FAILURE_MODES."""
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    rows = _synthetic_transactions()
    rows_in = len(rows)

    try:
        out = _aggregate(rows, mode)
        finished = datetime.now(timezone.utc)
        return RunResult(
            run_id=run_id,
            job_name=JOB_NAME,
            status="success",
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            rows_in=rows_in,
            rows_out=len(out),
            last_success_at=finished.isoformat(),
        )
    except PipelineError as e:
        finished = datetime.now(timezone.utc)
        return RunResult(
            run_id=run_id,
            job_name=JOB_NAME,
            status="failed",
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            rows_in=rows_in,
            rows_out=0,
            failure_mode=mode,
            error_type=e.error_type,
            error_message=e.message,
            traceback="".join(traceback.format_stack(limit=4)),
            offending_record=e.offending_record,
            recent_changes=RECENT_CHANGES,
            last_success_at=last_success_at
            or (started - timedelta(days=1)).isoformat(),
        )
