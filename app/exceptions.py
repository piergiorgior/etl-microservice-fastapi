from __future__ import annotations

from fastapi import HTTPException, status


class PipelineRunNotFoundError(HTTPException):
    """Raised when a pipeline run cannot be found by its ID."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "PipelineRunNotFound",
                "message": f"Pipeline run '{run_id}' not found.",
            },
        )


class InvalidStatusTransitionError(HTTPException):
    """Raised when an operation would result in an illegal status change."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "InvalidStatusTransition",
                "message": f"Cannot transition from '{current}' to '{target}'.",
            },
        )
