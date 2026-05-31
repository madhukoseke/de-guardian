"""API key authentication for mutating control-plane endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app import config


def verify_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not config.auth_required():
        return
    token = _extract_token(authorization, x_api_key)
    if not token or not config.API_KEY or token != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (Authorization: Bearer … or X-API-Key)",
        )


def _extract_token(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
