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
    """
    Provide a summary of prior failed runs that match the given failure mode and job, including whether those failures were later remediated.
    
    Builds a reverse-chronological history of matching failed runs (excluding `exclude_run_id` when given), marks each entry's `remediated` flag when a subsequent successful run occurs after a qualifying heal event, computes the auto-remediation success rate, and returns a short note describing prior incident frequency and recovery behavior.
    
    Parameters:
        exclude_run_id (str | None): A run_id to exclude from consideration (commonly the current run).
        heal_events (list[dict] | None): List of `/heal` events; each event should include at least `job_name` and `healed_at`. A failure is considered remediated only if a heal event for the same job occurs after the failure and a later successful run finishes at or after that heal time.
    
    Returns:
        dict[str, Any]: A dictionary with keys:
            - prior_occurrences (int): Number of matching prior failed runs.
            - history (list[dict]): Up to the last five matching failures, each with:
                - run_id (str | None)
                - failed_at (str | None)
                - error_type (str | None)
                - remediated (bool): True when a later success followed a qualifying heal event.
            - auto_remediation_success_rate (float | None): remediated_count / prior_occurrences rounded to 2 decimals, or None if no occurrences.
            - note (str): Human-readable summary about prior incidents and remediation rate.
    """
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
    """
    Determine whether a failed run was remediated by a later `/heal` event followed by a subsequent successful run for the same job.
    
    Parameters:
        failure (dict): The failed run record; its `"finished_at"` timestamp is used as the failure time.
        later_runs (list[dict]): Subsequent run records to search for a successful run for `job_name`.
        job_name (str | None): Job name to match against heal events and later runs.
        heal_events (list[dict]): Heal event records; each should include `"job_name"` and `"healed_at"`.
    
    Returns:
        bool: `True` if there exists a heal event for `job_name` with `"healed_at"` after the failure and at least one later run for the same `job_name` with `"status" == "success"` and `"finished_at"` greater than or equal to the earliest such heal; `False` otherwise.
    """
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
    """
    Builds a deterministic RCA payload using run-level evidence and incident memory.
    
    Uses fields from `run` (error type/message, failure_mode, offending_record, job_name, rows_in, recent_changes) and metrics from `recall_result` (prior occurrences, auto-remediation success rate, note) to produce a deterministic, non-LLM RCA suitable for automation decisions.
    
    Parameters:
        run (dict): Run-level evidence and metadata used to populate RCA fields (expects keys like `failure_mode`, `error_type`, `error_message`, `offending_record`, `job_name`, `rows_in`, `recent_changes`).
        recall_result (dict): Incident memory summary produced by `recall`, used to determine `confidence`, `remediation_is_safe_to_automate`, and `memory_note` (expects keys like `prior_occurrences`, `auto_remediation_success_rate`, `note`).
    
    Returns:
        dict: RCA object with the following notable keys:
            - root_cause: Human-readable root cause description (from FAILURE_MODES or a fallback).
            - evidence: List of evidence strings (error.type, error.message, memory note, optional offending_record JSON).
            - blast_radius: Human-readable blast radius string.
            - correlated_change: A recent change correlated to the failure_mode, or None.
            - recommended_remediation: Fixed remediation instruction referencing POST /heal and re-run.
            - remediation_is_safe_to_automate: Boolean indicating whether automation is considered safe.
            - confidence: One of "low", "medium", or "high" describing confidence in automation.
            - runbook: List of concise runbook steps for operators.
            - source: Set to "memory".
            - memory_note: The human-readable note from `recall_result`.
    """
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
    """
    Decide whether a cached memory-based RCA can be used instead of invoking Claude.
    
    Parameters:
        run (dict): The current run record (must include at least `job_name`, `run_id`, and `failure_mode`).
        runs (list[dict]): Full run history used by `recall` when `recall_result` is not provided.
        recall_result (dict | None): Optional precomputed recall result; if omitted the function calls
            `recall(...)` using `run`, `runs`, and `heal_events`.
        heal_events (list[dict] | None): Optional list of heal events passed through to `recall` to
            influence remediation detection; treated as empty when `None`.
    
    Returns:
        dict: If prior occurrences meet the configured automation threshold returns:
            {
                "source": "memory",
                "skip_claude": True,
                "rca": <dict> ,            # deterministic RCA built from memory
                "rca_json": <str>         # compact JSON serialization of `rca`
            }
        Otherwise returns:
            {
                "source": "claude_required",
                "skip_claude": False
            }
    """
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
    """
    Selects a recent change record from recent_changes that appears correlated with the given failure mode.
    
    For "schema_drift" this prefers the first change whose message contains "schema" (case-insensitive) or "v3".
    For "null_violation" this prefers the first change whose message contains "not null" (case-insensitive).
    If no targeted match is found, returns the most recent change. If recent_changes is empty, returns None.
    
    Parameters:
        failure_mode (str): Failure mode identifier used to select heuristics.
        recent_changes (list[dict]): Ordered list of change records; each record is expected to include a "message" string.
    
    Returns:
        dict | None: The selected change record when available, otherwise None.
    """
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
    """
    Produce a concise human-readable note summarizing prior incident frequency and observed auto-remediation effectiveness for a given failure mode.
    
    Parameters:
        failure_mode (str): The failure mode identifier to describe.
        occurrences (int): Number of prior incidents observed for this failure mode.
        rate (float | None): Fraction between 0.0 and 1.0 representing observed auto-remediation success rate, or `None` if no successful recoveries have been observed.
    
    Returns:
        str: A brief note describing whether the failure mode is novel, seen before with no recoveries, has fully self-healed historically, or the percentage success of auto-remediation and associated guidance.
    """
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
