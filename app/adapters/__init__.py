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
    ) -> RunResult: ...
