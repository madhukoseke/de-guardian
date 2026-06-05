"""Select the active pipeline adapter."""

from __future__ import annotations

import os

from app.adapters.synthetic import SyntheticAdapter
from app.pipeline import RunResult


def get_adapter():
    """
    Selects and returns the active pipeline adapter implementation.
    
    Reads the PIPELINE_ADAPTER environment variable (defaults to "synthetic") and returns a SyntheticAdapter when the value is "synthetic".
    
    Returns:
        SyntheticAdapter: An instance of the selected pipeline adapter.
    
    Raises:
        ValueError: If the environment variable specifies an unsupported adapter.
    """
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
    """
    Execute a pipeline run using the active pipeline adapter.
    
    Parameters:
        mode (str): The run mode identifier (e.g., environment or strategy name).
        last_success_at (str | None): ISO-8601 timestamp of the last successful run, or None if unknown.
        source (str): Origin of the run request (defaults to "web").
        after_heal (bool): True if the run is triggered as part of a healing process, False otherwise.
    
    Returns:
        RunResult: The result produced by the adapter's run method.
    """
    return get_adapter().run(mode, last_success_at, source=source, after_heal=after_heal)
