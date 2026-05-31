"""Runtime configuration and production guards."""

from __future__ import annotations

import os

ENV = os.environ.get("ENV", "development").lower()
IS_PRODUCTION = ENV == "production" or bool(os.environ.get("RENDER"))

DATABASE_URL = os.environ.get("DATABASE_URL")
API_KEY = (os.environ.get("API_KEY") or os.environ.get("DE_GUARDIAN_API_KEY") or "").strip() or None

SUPERPLANE_WEBHOOK_URL = os.environ.get("SUPERPLANE_WEBHOOK_URL")
SUPERPLANE_WEBHOOK_SECRET = (os.environ.get("SUPERPLANE_WEBHOOK_SECRET") or "").strip() or None

SERVICE_BASE_URL = os.environ.get("SERVICE_BASE_URL", "http://localhost:8000").rstrip("/")
RENDER_SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "local")

# Skip Claude when prior_occurrences > 0 and rate >= this threshold (0.0–1.0).
MEMORY_SKIP_CLAUDE_MIN_RATE = float(os.environ.get("MEMORY_SKIP_CLAUDE_MIN_RATE", "0.5"))

# Optional: auto-approve in canvas when rate == 1.0 (documented for operators).
AUTO_HEAL_MIN_RATE = float(os.environ.get("AUTO_HEAL_MIN_RATE", "1.0"))

WEBHOOK_MAX_ATTEMPTS = int(os.environ.get("WEBHOOK_MAX_ATTEMPTS", "3"))
WEBHOOK_RETRY_BACKOFF_SEC = float(os.environ.get("WEBHOOK_RETRY_BACKOFF_SEC", "1.0"))

# Optional Slack Incoming Webhook for direct incident alerts from the service.
SLACK_WEBHOOK_URL = (os.environ.get("SLACK_WEBHOOK_URL") or "").strip() or None

RUNS_LIMIT_DEFAULT = 20
RUNS_LIMIT_MAX = 200


def validate_startup() -> list[str]:
    """Return fatal configuration errors (empty list = OK)."""
    errors: list[str] = []
    if IS_PRODUCTION:
        if not API_KEY:
            errors.append("API_KEY is required when ENV=production or running on Render")
        if SUPERPLANE_WEBHOOK_URL and not SUPERPLANE_WEBHOOK_SECRET:
            errors.append(
                "SUPERPLANE_WEBHOOK_SECRET is required in production when SUPERPLANE_WEBHOOK_URL is set"
            )
        if DATABASE_URL and SERVICE_BASE_URL.startswith("http://localhost"):
            errors.append("SERVICE_BASE_URL must be a public https URL in production")
    return errors


def auth_required() -> bool:
    """Mutating endpoints require credentials when an API key is configured."""
    return bool(API_KEY)
