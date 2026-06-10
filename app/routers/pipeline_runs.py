from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.exceptions import InvalidStatusTransitionError, PipelineRunNotFoundError
from app.models.pipeline_run import PipelineRun, PipelineStatus
from app.schemas.pipeline_run import PipelineRunCreate, PipelineRunRead
from app.services.etl_runner import run_etl_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pipeline-runs",
    tags=["pipeline-runs"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=PipelineRunRead, status_code=http_status.HTTP_202_ACCEPTED)
async def create_pipeline_run(
    payload: PipelineRunCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineRun:
    """Trigger a new pipeline run. Returns 202 immediately; execution is async."""
    run = PipelineRun(
        pipeline_name=payload.pipeline_name,
        status=PipelineStatus.PENDING,
        run_metadata=payload.metadata,
    )
    db.add(run)
    # Flush to generate the PK and server defaults, then commit so the
    # background task can read the row from its own session.
    await db.flush()
    await db.refresh(run)
    await db.commit()

    background_tasks.add_task(run_etl_pipeline, run.id)
    logger.info("Pipeline run %s queued: pipeline=%r", run.id, run.pipeline_name)
    return run


@router.get("", response_model=list[PipelineRunRead])
async def list_pipeline_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: PipelineStatus | None = Query(
        None, alias="status", description="Filter runs by status"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[PipelineRun]:
    """List all pipeline runs, newest first. Supports ?status= filtering and pagination."""
    stmt = (
        select(PipelineRun)
        .order_by(PipelineRun.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        stmt = stmt.where(PipelineRun.status == status_filter)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{run_id}", response_model=PipelineRunRead)
async def get_pipeline_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineRun:
    """Fetch a single pipeline run by its UUID."""
    run = await db.get(PipelineRun, run_id)
    if run is None:
        raise PipelineRunNotFoundError(str(run_id))
    return run


@router.delete("/{run_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def cancel_pipeline_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Cancel a pipeline run. Only PENDING runs can be cancelled."""
    run = await db.get(PipelineRun, run_id)
    if run is None:
        raise PipelineRunNotFoundError(str(run_id))

    if run.status != PipelineStatus.PENDING:
        raise InvalidStatusTransitionError(run.status.value, PipelineStatus.CANCELLED.value)

    run.status = PipelineStatus.CANCELLED
    await db.flush()
    logger.info("Pipeline run %s cancelled", run_id)
