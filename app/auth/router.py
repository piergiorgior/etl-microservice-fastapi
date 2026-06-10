from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.jwt_utils import create_access_token
from app.auth.schemas import Token
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Exchange username + password for a JWT access token (OAuth2 password flow)."""
    settings = get_settings()
    if form_data.username != settings.api_username or form_data.password != settings.api_password:
        logger.warning("Failed login attempt for user %r", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Unauthorized", "message": "Invalid credentials."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=form_data.username)
    logger.info("Access token issued for user %r", form_data.username)
    return Token(access_token=token)
