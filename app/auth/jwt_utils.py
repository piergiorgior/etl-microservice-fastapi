from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

logger = logging.getLogger(__name__)


def create_access_token(subject: str) -> str:
    """Create a signed JWT with a configurable expiry."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Validate the token signature and expiry; return the subject claim.

    Raises jwt.InvalidTokenError on any validation failure.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    sub: str | None = payload.get("sub")
    if sub is None:
        raise jwt.InvalidTokenError("Token is missing the 'sub' claim")
    return sub
