"""Audit log query API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbAuditEvent
from docsgraph_server.db.session import get_session

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    """Pydantic model for audit event responses."""

    id: UUID
    actor_id: UUID
    action: str
    resource_id: UUID | None
    metadata_json: dict[str, Any] | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditEventResponse])
async def list_audit_events(
    resource_id: UUID | None = None,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbAuditEvent]:
    """Retrieve and list audit log events, optionally filtered by resource ID."""
    query = select(DbAuditEvent)
    if resource_id:
        query = query.where(DbAuditEvent.resource_id == resource_id)
    query = query.order_by(DbAuditEvent.occurred_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())
