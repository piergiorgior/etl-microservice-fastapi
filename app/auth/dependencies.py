from __future__ import annotations

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_utils import decode_access_token

logger = logging.getLogger(__name__)

# auto_error=False lets us return a consistent 401 instead of FastAPI's default 403
# when the Authorization header is absent entirely.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency — validates Bearer JWT and returns the username.

    Raises HTTP 401 for both missing and invalid tokens.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Unauthorized", "message": "Authentication required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        username = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Unauthorized", "message": "Invalid or expired token."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return username
