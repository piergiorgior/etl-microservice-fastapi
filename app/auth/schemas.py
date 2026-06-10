from __future__ import annotations

from pydantic import BaseModel


class Token(BaseModel):
    """Response body for a successful authentication."""

    access_token: str
    token_type: str = "bearer"
