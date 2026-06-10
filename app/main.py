from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.database import init_db
from app.routers import pipeline_runs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Manage application startup and shutdown."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )
    logger.info("Starting ETL Microservice [env=%s]", settings.app_env)
    await init_db()
    yield
    logger.info("ETL Microservice shutting down")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="ETL Microservice",
        description=(
            "Production-ready FastAPI microservice for triggering, monitoring, "
            "and managing ETL pipeline runs."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(pipeline_runs.router, prefix="/api/v1")

    @app.get("/health", tags=["ops"], summary="Liveness probe")
    async def health() -> dict[str, Any]:
        """Return service health. Used by Docker and load-balancer health checks."""
        return {"status": "healthy"}

    return app


app = create_app()
