"""Select the active pipeline adapter."""

from __future__ import annotations

import os

from app.adapters.synthetic import SyntheticAdapter
from app.pipeline import RunResult


def get_adapter():
    name = os.environ.get("PIPELINE_ADAPTER", "synthetic").lower()
    if name == "synthetic":
        return SyntheticAdapter()
    raise ValueError(f"Unknown PIPELINE_ADAPTER '{name}' (supported: synthetic)")


def execute_run(
    mode: str,
    last_success_at: str | None,
    *,
    source: str = "web",
    after_heal: bool = False,
) -> RunResult:
    return get_adapter().run(mode, last_success_at, source=source, after_heal=after_heal)
