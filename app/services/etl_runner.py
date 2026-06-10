from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from app.database import get_session_factory
from app.models.pipeline_run import PipelineRun, PipelineStatus

logger = logging.getLogger(__name__)

# Simulated ETL work duration bounds (seconds)
_MIN_DURATION = 2.0
_MAX_DURATION = 5.0

# Probability of a simulated pipeline failure
_FAILURE_RATE = 0.10


async def run_etl_pipeline(run_id: uuid.UUID) -> None:
    """
    Simulate an ETL pipeline execution as a FastAPI background task.

    Lifecycle: PENDING → RUNNING → SUCCESS | FAILED
    A 10% random failure rate is injected to make monitoring interesting.
    The function uses its own database sessions, independent of the
    request-scoped session that triggered it.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        run = await session.get(PipelineRun, run_id)
        if run is None:
            logger.error("Pipeline run %s not found — aborting ETL task", run_id)
            return

        if run.status == PipelineStatus.CANCELLED:
            logger.info("Pipeline run %s was cancelled before execution started", run_id)
            return

        run.status = PipelineStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "Pipeline run %s started: pipeline=%r",
            run_id,
            run.pipeline_name,
        )

    duration = random.uniform(_MIN_DURATION, _MAX_DURATION)
    logger.debug("Pipeline run %s simulating %.2fs of work", run_id, duration)
    await asyncio.sleep(duration)

    failed = random.random() < _FAILURE_RATE

    async with session_factory() as session:
        run = await session.get(PipelineRun, run_id)
        if run is None:
            logger.error("Pipeline run %s disappeared during execution", run_id)
            return

        run.finished_at = datetime.now(timezone.utc)

        if failed:
            run.status = PipelineStatus.FAILED
            run.error_message = "Simulated failure: upstream data validation error"
            logger.error(
                "Pipeline run %s FAILED after %.2fs: pipeline=%r",
                run_id,
                duration,
                run.pipeline_name,
            )
        else:
            run.status = PipelineStatus.SUCCESS
            logger.info(
                "Pipeline run %s SUCCEEDED after %.2fs: pipeline=%r",
                run_id,
                duration,
                run.pipeline_name,
            )

        await session.commit()
