"""FastAPI application factory for docsgraph-server."""

import logging

from fastapi import FastAPI, HTTPException, status
from sqlalchemy.sql import text

from docsgraph_server.api import audit, documents, permissions, workflows
from docsgraph_server.sync.router import router as sync_router

logger = logging.getLogger("docsgraph_server.health")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Mounts all domain routers under `/api/v1` and exposes a top-level
    `/health` endpoint for liveness checks.
    """
    app = FastAPI(
        title="docsgraph-server",
        description=(
            "Self-hostable backend for organizations: synchronization, document "
            "processing, OCR, indexing, permissions, collaboration, workflows, "
            "audit logs, retention policies, and external integrations."
        ),
        version="0.1.0",
    )

    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(permissions.router, prefix="/api/v1")
    app.include_router(workflows.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness check used by orchestrators/self-host deployments.

        Verifies API responsiveness, database connectivity, and Redis availability.
        """
        # Verify database connectivity
        try:
            from docsgraph_server.db.session import get_engine

            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error("Health check failed: Database connection error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed",
            ) from e

        # Verify Redis connectivity
        try:
            import redis.asyncio as redis

            from docsgraph_server.core.config import get_settings

            settings = get_settings()
            client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
            await client.ping()
            await client.close()
        except Exception as e:
            logger.error("Health check failed: Redis connection error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis connection failed",
            ) from e

        return {"status": "ok"}

    return app


app = create_app()
