"""Initial migration: create pipeline_runs table

Revision ID: f3e2d1c0b9a8
Revises:
Create Date: 2026-06-10 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3e2d1c0b9a8"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "SUCCESS",
                "FAILED",
                "CANCELLED",
                name="pipelinestatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.create_index("ix_pipeline_runs_pipeline_name", "pipeline_runs", ["pipeline_name"])
    op.create_index(
        "ix_pipeline_runs_triggered_at", "pipeline_runs", ["triggered_at"], postgresql_using="brin"
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_triggered_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_pipeline_name", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
