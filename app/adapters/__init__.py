"""Pluggable pipeline runners for production integration."""

from __future__ import annotations

from typing import Protocol

from app.pipeline import RunResult


class PipelineAdapter(Protocol):
    """Run a pipeline job and return structured run metadata."""

    def run(
        self,
        mode: str,
        last_success_at: str | None,
        *,
        source: str = "web",
        after_heal: bool = False,
    ) -> RunResult: """
        Execute a pipeline job and return structured run metadata.
        
        Parameters:
            mode (str): Pipeline execution mode.
            last_success_at (str | None): ISO-8601 timestamp of the last successful run, or `None` if unavailable.
            source (str): Origin of the run request (default: "web").
            after_heal (bool): Whether this run follows a healing process (default: False).
        
        Returns:
            RunResult: Structured metadata about the execution, such as status, timestamps, and any produced metrics.
        """
        ...
