from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.pipeline_run import PipelineRun, PipelineStatus
from app.services.etl_runner import run_etl_pipeline

_TEST_DB_DIR = os.path.join(os.path.dirname(__file__), ".test_dbs")
os.makedirs(_TEST_DB_DIR, exist_ok=True)


@pytest_asyncio.fixture
async def db_factory():
    """Fresh SQLite session factory for each ETL runner test."""
    db_path = os.path.join(_TEST_DB_DIR, f"etl_{uuid.uuid4().hex}.db")
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


async def _seed_run(factory: async_sessionmaker, pipeline_name: str) -> uuid.UUID:
    """Insert a PENDING pipeline run and return its ID."""
    run_id = uuid.uuid4()
    async with factory() as session:
        run = PipelineRun(
            id=run_id,
            pipeline_name=pipeline_name,
            status=PipelineStatus.PENDING,
            triggered_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
    return run_id


async def test_etl_runner_success(db_factory) -> None:
    """ETL runner should mark a run SUCCESS on a normal execution."""
    run_id = await _seed_run(db_factory, "success-pipeline")

    with (
        patch("app.services.etl_runner.get_session_factory", return_value=db_factory),
        patch("random.random", return_value=0.5),  # above failure threshold → success
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await run_etl_pipeline(run_id)

    async with db_factory() as session:
        run = await session.get(PipelineRun, run_id)

    assert run is not None
    assert run.status == PipelineStatus.SUCCESS
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.error_message is None


async def test_etl_runner_failure(db_factory) -> None:
    """ETL runner should mark a run FAILED when the random failure fires."""
    run_id = await _seed_run(db_factory, "failing-pipeline")

    with (
        patch("app.services.etl_runner.get_session_factory", return_value=db_factory),
        patch("random.random", return_value=0.05),  # below 0.10 threshold → failure
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await run_etl_pipeline(run_id)

    async with db_factory() as session:
        run = await session.get(PipelineRun, run_id)

    assert run is not None
    assert run.status == PipelineStatus.FAILED
    assert run.error_message is not None
    assert run.finished_at is not None


async def test_etl_runner_sets_running_before_sleep(db_factory) -> None:
    """Status must transition to RUNNING before the simulated work starts."""
    run_id = await _seed_run(db_factory, "status-check-pipeline")
    captured_status: list[PipelineStatus] = []

    async def fake_sleep(_duration: float) -> None:
        async with db_factory() as session:
            run = await session.get(PipelineRun, run_id)
            captured_status.append(run.status)

    with (
        patch("app.services.etl_runner.get_session_factory", return_value=db_factory),
        patch("random.random", return_value=0.5),
        patch("asyncio.sleep", side_effect=fake_sleep),
    ):
        await run_etl_pipeline(run_id)

    assert captured_status == [PipelineStatus.RUNNING]


async def test_etl_runner_skips_cancelled_run(db_factory) -> None:
    """A CANCELLED run must not be transitioned to RUNNING."""
    run_id = await _seed_run(db_factory, "cancelled-pipeline")

    async with db_factory() as session:
        run = await session.get(PipelineRun, run_id)
        run.status = PipelineStatus.CANCELLED
        await session.commit()

    with (
        patch("app.services.etl_runner.get_session_factory", return_value=db_factory),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await run_etl_pipeline(run_id)

    async with db_factory() as session:
        run = await session.get(PipelineRun, run_id)

    assert run.status == PipelineStatus.CANCELLED
    assert run.started_at is None


async def test_etl_runner_nonexistent_run(db_factory) -> None:
    """The runner must handle a missing run ID gracefully without raising."""
    with patch("app.services.etl_runner.get_session_factory", return_value=db_factory):
        await run_etl_pipeline(uuid.uuid4())  # should not raise
