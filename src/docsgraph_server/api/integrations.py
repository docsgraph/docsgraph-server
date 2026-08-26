"""Integrations management and dispatch API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbIntegrationConfig
from docsgraph_server.db.session import get_session
from docsgraph_server.integrations.engine import IntegrationManager

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationConfigUpdate(BaseModel):
    """Pydantic model for updating an integration configuration."""

    enabled: bool
    config_json: dict[str, Any]


class IntegrationStatusResponse(BaseModel):
    """Pydantic model for integration status responses."""

    id: str
    name: str
    enabled: bool
    config_json: dict[str, Any]


class DispatchTestRequest(BaseModel):
    """Pydantic model for triggering a test event dispatch."""

    event_type: str
    payload: dict[str, Any]


@router.get("", response_model=list[IntegrationStatusResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all registered integrations and their current configurations."""
    manager = IntegrationManager()
    await manager.load_configurations(db)

    response = []
    for integration_id, integration in manager.registry.items():
        result = await db.execute(
            select(DbIntegrationConfig).where(DbIntegrationConfig.id == integration_id)
        )
        db_cfg = result.scalar_one_or_none()

        response.append(
            {
                "id": integration_id,
                "name": integration.get_name(),
                "enabled": db_cfg.enabled if db_cfg else False,
                "config_json": db_cfg.config_json if db_cfg else {},
            }
        )
    return response


@router.post("/{integration_id}/configure", response_model=IntegrationStatusResponse)
async def configure_integration(
    integration_id: str,
    req: IntegrationConfigUpdate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    """Configure and enable/disable a specific integration."""
    manager = IntegrationManager()
    if integration_id not in manager.registry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_id}' not found",
        )

    result = await db.execute(
        select(DbIntegrationConfig).where(DbIntegrationConfig.id == integration_id)
    )
    db_cfg = result.scalar_one_or_none()

    if not db_cfg:
        db_cfg = DbIntegrationConfig(
            id=integration_id,
            enabled=req.enabled,
            config_json=req.config_json,
        )
        db.add(db_cfg)
    else:
        db_cfg.enabled = req.enabled
        db_cfg.config_json = req.config_json

    await db.commit()

    await manager.load_configurations(db)
    integration = manager.registry[integration_id]

    return {
        "id": integration_id,
        "name": integration.get_name(),
        "enabled": db_cfg.enabled,
        "config_json": db_cfg.config_json,
    }


@router.post("/dispatch")
async def dispatch_event(
    req: DispatchTestRequest,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    """Dispatch a test event to all active integrations."""
    manager = IntegrationManager()
    await manager.load_configurations(db)
    outcomes = await manager.dispatch(req.event_type, req.payload)
    return {"outcomes": outcomes}
