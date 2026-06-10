from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class PipelineStatus(str, enum.Enum):
    """Lifecycle states for a pipeline run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineRun(Base):
    """ORM model representing a single ETL pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    pipeline_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[PipelineStatus] = mapped_column(
        sa.Enum(PipelineStatus, name="pipelinestatus", native_enum=False, length=20),
        nullable=False,
        default=PipelineStatus.PENDING,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Python attribute is 'run_metadata'; DB column is 'metadata' to match spec.
    # 'metadata' is reserved on DeclarativeBase, so we use the mapped name trick.
    run_metadata: Mapped[dict | None] = mapped_column(
        "metadata", sa.JSON, nullable=True
    )

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id} name={self.pipeline_name!r} status={self.status}>"
