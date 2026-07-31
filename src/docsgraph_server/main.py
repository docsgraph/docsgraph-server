"""FastAPI application factory for docsgraph-server."""

from fastapi import FastAPI

from docsgraph_server.api import audit, documents, permissions, workflows
from docsgraph_server.sync.router import router as sync_router


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
        """Liveness check used by orchestrators/self-host deployments."""
        return {"status": "ok"}

    return app


app = create_app()
