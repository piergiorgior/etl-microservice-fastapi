from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models import Base

# Write test DBs inside the project so we avoid Windows AppData temp permission issues
_TEST_DB_DIR = os.path.join(os.path.dirname(__file__), ".test_dbs")
os.makedirs(_TEST_DB_DIR, exist_ok=True)


def _make_test_engine(name: str):
    db_path = os.path.join(_TEST_DB_DIR, f"{name}.db")
    return create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    ), db_path


@pytest_asyncio.fixture
async def test_engine():
    """Fresh SQLite database for each test, cleaned up on teardown."""
    engine, db_path = _make_test_engine(uuid.uuid4().hex)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the test database."""
    return async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client wired to the FastAPI app with:
    - DB dependency overridden to use the isolated test SQLite database.
    - ETL runner mocked so background tasks never touch the DB or sleep.
    """
    factory = test_session_factory

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.routers.pipeline_runs.run_etl_pipeline", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    """Client with a valid Bearer token pre-set on every request."""
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "changeme"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    client.headers = {**client.headers, "Authorization": f"Bearer {token}"}
    return client
