from __future__ import annotations

import jwt
import pytest
from httpx import AsyncClient

from app.auth.jwt_utils import create_access_token, decode_access_token
from app.config import get_settings

TOKEN_URL = "/api/v1/auth/token"


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------


async def test_login_success(client: AsyncClient) -> None:
    response = await client.post(
        TOKEN_URL, data={"username": "admin", "password": "changeme"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient) -> None:
    response = await client.post(
        TOKEN_URL, data={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "Unauthorized"


async def test_login_unknown_user(client: AsyncClient) -> None:
    response = await client.post(
        TOKEN_URL, data={"username": "ghost", "password": "changeme"}
    )
    assert response.status_code == 401


async def test_login_missing_fields_returns_422(client: AsyncClient) -> None:
    response = await client.post(TOKEN_URL, data={"username": "admin"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Bearer token validation
# ---------------------------------------------------------------------------


async def test_valid_token_grants_access(client: AsyncClient) -> None:
    token = (
        await client.post(TOKEN_URL, data={"username": "admin", "password": "changeme"})
    ).json()["access_token"]

    response = await client.get(
        "/api/v1/pipeline-runs", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


async def test_missing_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pipeline-runs")
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/pipeline-runs",
        headers={"Authorization": "Bearer this.is.not.valid"},
    )
    assert response.status_code == 401


async def test_expired_token_returns_401(client: AsyncClient, monkeypatch) -> None:
    """Force an expired token by patching jwt_expire_minutes to 0."""
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_expire_minutes", -1)

    token = create_access_token(subject="admin")

    response = await client.get(
        "/api/v1/pipeline-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# jwt_utils unit tests
# ---------------------------------------------------------------------------


def test_decode_valid_token() -> None:
    token = create_access_token(subject="testuser")
    assert decode_access_token(token) == "testuser"


def test_decode_tampered_token_raises() -> None:
    token = create_access_token(subject="testuser")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered)
