"""
Incident memory — what the agent recalls about past failures.

Memory is derived from the run-history audit trail (app.db), not a separate
store. Remediation is counted only when a heal event occurred between the
failure and a subsequent successful run (cron-only successes do not count).
"""

from __future__ import annotations

import json
from typing import Any

from app.config import MEMORY_SKIP_CLAUDE_MIN_RATE
from app.pipeline import FAILURE_MODES


def recall(
    failure_mode: str | None,
    job_name: str | None,
    runs: list[dict],
    exclude_run_id: str | None = None,
    *,
    heal_events: list[dict] | None = None,
) -> dict[str, Any]:
    """Summarise prior incidents of this failure mode from run history."""
    if not failure_mode:
        return {
            "prior_occurrences": 0,
            "history": [],
            "auto_remediation_success_rate": None,
            "note": "No failure mode on the event — nothing to recall.",
        }

    heals = heal_events or []
    chrono = [r for r in reversed(runs) if r.get("run_id") != exclude_run_id]

    history: list[dict[str, Any]] = []
    for i, r in enumerate(chrono):
        if (
            r.get("status") == "failed"
            and r.get("failure_mode") == failure_mode
            and r.get("job_name") == job_name
        ):
            remediated = _was_remediated(r, chrono[i + 1 :], job_name, heals)
            history.append(
                {
                    "run_id": r.get("run_id"),
                    "failed_at": r.get("finished_at"),
                    "error_type": r.get("error_type"),
                    "remediated": remediated,
                }
            )

    occurrences = len(history)
    remediated_count = sum(1 for h in history if h["remediated"])
    rate = round(remediated_count / occurrences, 2) if occurrences else None

    return {
        "prior_occurrences": occurrences,
        "history": history[-5:],
        "auto_remediation_success_rate": rate,
        "note": _note(failure_mode, occurrences, rate),
    }


def _was_remediated(
    failure: dict,
    later_runs: list[dict],
    job_name: str | None,
    heal_events: list[dict],
) -> bool:
    """True only if /heal was applied before the next successful run."""
    failure_at = failure.get("finished_at") or ""
    heals_after = [
        h for h in heal_events
        if h.get("job_name") == job_name and (h.get("healed_at") or "") > failure_at
    ]
    if not heals_after:
        return False
    first_heal_at = min(h["healed_at"] for h in heals_after)
    for later in later_runs:
        if later.get("job_name") != job_name:
            continue
        if later.get("status") != "success":
            continue
        if (later.get("finished_at") or "") >= first_heal_at:
            return True
    return False


def build_cached_rca(run: dict[str, Any], recall_result: dict[str, Any]) -> dict[str, Any]:
    """Deterministic RCA from run evidence and memory track record (no LLM)."""
    failure_mode = run.get("failure_mode") or "unknown"
    error = {
        "type": run.get("error_type"),
        "message": run.get("error_message"),
        "failure_mode": failure_mode,
        "offending_record": run.get("offending_record"),
    }
    recent_changes = run.get("recent_changes") or []
    correlated = _correlated_change(failure_mode, recent_changes)
    rate = recall_result.get("auto_remediation_success_rate")
    occurrences = recall_result.get("prior_occurrences", 0)

    if rate == 1.0:
        confidence = "high"
        safe_to_automate = True
    elif rate is not None and rate >= MEMORY_SKIP_CLAUDE_MIN_RATE:
        confidence = "medium"
        safe_to_automate = False
    else:
        confidence = "medium" if occurrences else "low"
        safe_to_automate = False

    root_cause = FAILURE_MODES.get(
        failure_mode,
        f"Pipeline failed with failure_mode={failure_mode}.",
    )

    evidence = [
        f"error.type={error.get('type')}",
        f"error.message={error.get('message')}",
        recall_result.get("note", ""),
    ]
    if error.get("offending_record"):
        evidence.append(f"offending_record={json.dumps(error['offending_record'], sort_keys=True)}")

    return {
        "root_cause": root_cause,
        "evidence": [e for e in evidence if e],
        "blast_radius": f"{run.get('job_name', 'pipeline')} — {run.get('rows_in', 0)} rows in flight",
        "correlated_change": correlated,
        "recommended_remediation": "POST /heal to clear the armed failure mode, then re-run the pipeline.",
        "remediation_is_safe_to_automate": safe_to_automate,
        "confidence": confidence,
        "runbook": [
            "Confirm failure_mode matches a known pattern in incident memory.",
            "Review memory.note and prior_occurrences before approving automation.",
            "POST /heal, then POST /run to verify recovery.",
        ],
        "source": "memory",
        "memory_note": recall_result.get("note"),
    }


def resolve(
    run: dict[str, Any],
    runs: list[dict],
    *,
    recall_result: dict[str, Any] | None = None,
    heal_events: list[dict] | None = None,
) -> dict[str, Any]:
    """Decide whether Claude is needed or memory can supply the RCA."""
    job_name = run.get("job_name")
    recall_result = recall_result or recall(
        run.get("failure_mode"),
        job_name,
        runs,
        exclude_run_id=run.get("run_id"),
        heal_events=heal_events,
    )
    occurrences = recall_result.get("prior_occurrences", 0)
    rate = recall_result.get("auto_remediation_success_rate")
    if occurrences > 0 and rate is not None and rate >= MEMORY_SKIP_CLAUDE_MIN_RATE:
        rca = build_cached_rca(run, recall_result)
        return {
            "source": "memory",
            "skip_claude": True,
            "rca": rca,
            "rca_json": json.dumps(rca, separators=(",", ":")),
        }
    return {
        "source": "claude_required",
        "skip_claude": False,
    }


def _correlated_change(failure_mode: str, recent_changes: list[dict]) -> dict | None:
    if not recent_changes:
        return None
    if failure_mode == "schema_drift":
        for change in recent_changes:
            if "schema" in change.get("message", "").lower() or "v3" in change.get("message", ""):
                return change
    if failure_mode == "null_violation":
        for change in recent_changes:
            if "not null" in change.get("message", "").lower():
                return change
    return recent_changes[0]


def _note(failure_mode: str, occurrences: int, rate: float | None) -> str:
    if occurrences == 0:
        return f"No prior {failure_mode} incidents on record — treat as novel; prefer human review."
    if rate is None:
        return f"Seen {failure_mode} {occurrences}x before, but no recovery observed yet."
    if rate >= 1.0:
        return (
            f"{failure_mode} has self-healed {occurrences}/{occurrences} times — "
            "strong track record; safe to automate."
        )
    pct = int(rate * 100)
    return (
        f"{failure_mode} seen {occurrences}x; auto-remediation succeeded {pct}% of the time — "
        "automate with caution."
    )
