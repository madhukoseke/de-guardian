#!/usr/bin/env python3
"""Write fixtures/schema_drift_incident.json from a live failed run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.events import build_incident
from app.pipeline import run_pipeline

def main() -> None:
    result = run_pipeline(mode="schema_drift", last_success_at="2026-05-29T06:00:00Z")
    incident = build_incident(result.to_dict())
    out = ROOT / "fixtures" / "schema_drift_incident.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(incident, indent=2) + "\n")
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
