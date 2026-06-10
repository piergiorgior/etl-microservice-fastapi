from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.pipeline_run import PipelineStatus


class PipelineRunCreate(BaseModel):
    """Payload for triggering a new pipeline run."""

    pipeline_name: str = Field(..., min_length=1, max_length=255, examples=["daily-ingest"])
    metadata: dict | None = Field(None, examples=[{"source": "s3://bucket/prefix"}])


class PipelineRunRead(BaseModel):
    """Full representation of a pipeline run returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    pipeline_name: str
    status: PipelineStatus
    triggered_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    # ORM stores this as 'run_metadata'; API exposes it as 'metadata'.
    metadata: dict | None = Field(None, validation_alias="run_metadata")


class PipelineRunStatusUpdate(BaseModel):
    """Internal schema for updating a run's status (used by the ETL runner)."""

    status: PipelineStatus
    error_message: str | None = None
