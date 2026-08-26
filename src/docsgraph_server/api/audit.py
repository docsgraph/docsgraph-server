"""Audit log query and export API routes."""

import csv
import io
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
    actor_id: UUID | None = None,
    action: str | None = None,
    resource_id: UUID | None = None,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbAuditEvent]:
    """Retrieve and list audit log events with optional filtering."""
    query = select(DbAuditEvent)
    if actor_id:
        query = query.where(DbAuditEvent.actor_id == actor_id)
    if action:
        query = query.where(DbAuditEvent.action == action)
    if resource_id:
        query = query.where(DbAuditEvent.resource_id == resource_id)
    query = query.order_by(DbAuditEvent.occurred_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/export")
async def export_audit_events(
    actor_id: UUID | None = None,
    action: str | None = None,
    resource_id: UUID | None = None,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> StreamingResponse:
    """Export audit log events as a downloadable CSV file."""
    query = select(DbAuditEvent)
    if actor_id:
        query = query.where(DbAuditEvent.actor_id == actor_id)
    if action:
        query = query.where(DbAuditEvent.action == action)
    if resource_id:
        query = query.where(DbAuditEvent.resource_id == resource_id)
    query = query.order_by(DbAuditEvent.occurred_at.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "actor_id", "action", "resource_id", "metadata_json", "occurred_at"])
    for event in events:
        writer.writerow(
            [
                str(event.id),
                str(event.actor_id),
                event.action,
                str(event.resource_id) if event.resource_id else "",
                str(event.metadata_json) if event.metadata_json else "",
                event.occurred_at.isoformat(),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
