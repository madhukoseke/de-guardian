"""Tests for incident memory recall and skip_claude routing."""

from app import memory


def _run(run_id, status, failure_mode=None, finished_at="2026-01-02T00:00:00Z", source="web"):
    """
    Create a test run dictionary for the `daily_revenue_aggregation` job with the supplied attributes.
    
    Parameters:
        run_id (str): Unique identifier for the run.
        status (str): Run status (e.g., "success", "failed").
        failure_mode (str | None): Optional failure mode identifier when status is "failed".
        finished_at (str): ISO 8601 timestamp when the run finished; defaults to "2026-01-02T00:00:00Z".
        source (str): Origin of the run (e.g., "web", "cron"); defaults to "web".
    
    Returns:
        dict: A mapping with keys `run_id`, `job_name`, `status`, `failure_mode`, `finished_at`, and `source`.
    """
    return {
        "run_id": run_id,
        "job_name": "daily_revenue_aggregation",
        "status": status,
        "failure_mode": failure_mode,
        "finished_at": finished_at,
        "source": source,
    }


def test_remediated_requires_heal_event():
    runs = [
        _run("r3", "success", finished_at="2026-01-03T00:00:00Z", source="cron"),
        _run("r2", "failed", "schema_drift", "2026-01-02T12:00:00Z"),
        _run("r1", "success", finished_at="2026-01-01T00:00:00Z"),
    ]
    heals = [{"job_name": "daily_revenue_aggregation", "healed_at": "2026-01-02T13:00:00Z"}]
    mem = memory.recall("schema_drift", "daily_revenue_aggregation", runs, heal_events=heals)
    assert mem["prior_occurrences"] == 1
    assert mem["auto_remediation_success_rate"] == 1.0

    # Cron success without heal does not count
    heals_none = []
    mem2 = memory.recall("schema_drift", "daily_revenue_aggregation", runs, heal_events=heals_none)
    assert mem2["auto_remediation_success_rate"] == 0.0


def test_skip_claude_requires_min_success_rate():
    run = {"failure_mode": "schema_drift", "job_name": "daily_revenue_aggregation"}
    recall_low = {"prior_occurrences": 2, "auto_remediation_success_rate": 0.0, "note": "caution"}
    inv = memory.resolve(run, [], recall_result=recall_low)
    assert inv["skip_claude"] is False

    recall_ok = {"prior_occurrences": 2, "auto_remediation_success_rate": 1.0, "note": "ok"}
    inv2 = memory.resolve(run, [], recall_result=recall_ok)
    assert inv2["skip_claude"] is True
    assert "rca_json" in inv2


def test_novel_failure_skips_claude():
    run = {"failure_mode": "schema_drift", "job_name": "daily_revenue_aggregation"}
    recall = {"prior_occurrences": 0, "auto_remediation_success_rate": None, "note": "novel"}
    inv = memory.resolve(run, [], recall_result=recall)
    assert inv["skip_claude"] is False
