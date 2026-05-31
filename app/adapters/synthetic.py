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
        return run_pipeline(
            mode=mode,
            last_success_at=last_success_at,
            source=source,
            after_heal=after_heal,
        )
