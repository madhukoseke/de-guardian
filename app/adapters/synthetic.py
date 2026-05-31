"""Built-in synthetic pipeline used for demos and local dev."""

from __future__ import annotations

from app.pipeline import RunResult, run_pipeline


class SyntheticAdapter:
    def run(
        self,
        mode: str,
        last_success_at: str | None,
        *,
        source: str = "web",
        after_heal: bool = False,
    ) -> RunResult:
        """
        Run the synthetic pipeline with the given mode and timing/options.
        
        Parameters:
            mode (str): Name of the pipeline run mode that controls pipeline behavior.
            last_success_at (str | None): ISO-8601 timestamp of the last successful run, or `None` if there was no prior success.
            source (str): Origin identifier for the run (defaults to "web").
            after_heal (bool): If `True`, indicates this run is being executed after a healing operation (defaults to `False`).
        
        Returns:
            RunResult: The result produced by `run_pipeline`.
        """
        return run_pipeline(
            mode=mode,
            last_success_at=last_success_at,
            source=source,
            after_heal=after_heal,
        )
