"""
Incident memory — what the agent recalls about past failures.

Memory is derived from the run-history audit trail (app.db), not a separate
store: for a given failure mode, how often it has happened before and whether
the run that followed each occurrence recovered. That yields an auto-remediation
success rate the agent can cite — "schema_drift has self-healed 3/3 times" — so
its automation confidence is grounded in track record, not a guess.
"""

from __future__ import annotations

from typing import Any


def recall(
    failure_mode: str | None,
    job_name: str | None,
    runs: list[dict],
    exclude_run_id: str | None = None,
) -> dict[str, Any]:
    """Summarise prior incidents of this failure mode from run history.

    `runs` is newest-first (as returned by db.recent_runs). The current run is
    excluded via `exclude_run_id` so memory reflects only what came before.
    """
    if not failure_mode:
        return {
            "prior_occurrences": 0,
            "history": [],
            "auto_remediation_success_rate": None,
            "note": "No failure mode on the event — nothing to recall.",
        }

    # Walk oldest-first so we can inspect the run that followed each failure.
    chrono = [r for r in reversed(runs) if r.get("run_id") != exclude_run_id]

    history: list[dict[str, Any]] = []
    for i, r in enumerate(chrono):
        if (
            r.get("status") == "failed"
            and r.get("failure_mode") == failure_mode
            and r.get("job_name") == job_name
        ):
            next_run = next(
                (later for later in chrono[i + 1:] if later.get("job_name") == job_name),
                None,
            )
            history.append(
                {
                    "run_id": r.get("run_id"),
                    "failed_at": r.get("finished_at"),
                    "error_type": r.get("error_type"),
                    "remediated": bool(next_run and next_run.get("status") == "success"),
                }
            )

    occurrences = len(history)
    remediated = sum(1 for h in history if h["remediated"])
    rate = round(remediated / occurrences, 2) if occurrences else None

    return {
        "prior_occurrences": occurrences,
        "history": history[-5:],  # most recent five
        "auto_remediation_success_rate": rate,
        "note": _note(failure_mode, occurrences, rate),
    }


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
