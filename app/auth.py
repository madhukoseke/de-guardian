"""API key authentication for mutating control-plane endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app import config


def verify_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """
    Enforces API key authentication for mutating control-plane requests.
    
    This function checks whether authentication is required via config.auth_required(). If required, it extracts an API token from the X-API-Key header or the Authorization Bearer header and validates it against config.API_KEY. If validation fails, the request is rejected.
    
    Parameters:
        authorization (str | None): Value of the Authorization header (expected format: "Bearer <token>").
        x_api_key (str | None): Value of the X-API-Key header.
    
    Raises:
        HTTPException: with status_code 401 and detail "Invalid or missing API key (Authorization: Bearer … or X-API-Key)" when no usable token is provided, config.API_KEY is not set, or the token does not match config.API_KEY.
    """
    if not config.auth_required():
        return
    token = _extract_token(authorization, x_api_key)
    if not token or not config.API_KEY or token != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (Authorization: Bearer … or X-API-Key)",
        )


def _extract_token(authorization: str | None, x_api_key: str | None) -> str | None:
    """
    Extract an API token from either the X-API-Key header or an Authorization Bearer header.
    
    X-API-Key takes precedence; if present its trimmed value is returned. Otherwise, if the Authorization header
    starts with the case-insensitive prefix "Bearer ", the substring after that prefix is returned trimmed.
    Returns None if no usable token is found.
    
    Parameters:
        authorization (str | None): The raw Authorization header value, e.g. "Bearer <token>".
        x_api_key (str | None): The raw X-API-Key header value.
    
    Returns:
        str | None: The extracted token string (trimmed) or None when no token is available.
    """
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
