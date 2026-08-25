"""Workflow/automation API routes."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.audit.logger import DatabaseAuditLogger
from docsgraph_server.db.models import DbWorkflowDefinition, DbWorkflowInstance
from docsgraph_server.db.session import get_session
from docsgraph_server.workflows.engine import DatabaseWorkflowEngine

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowDefinitionCreate(BaseModel):
    """Pydantic model for creating a workflow definition."""

    id: UUID | None = None
    name: str
    states: list[str]
    transitions: list[dict[str, Any]]


class WorkflowDefinitionResponse(BaseModel):
    """Pydantic model for workflow definition responses."""

    id: UUID
    name: str
    states: list[str]
    transitions: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class WorkflowInstanceCreate(BaseModel):
    """Pydantic model for creating a workflow instance."""

    id: UUID | None = None
    workflow_definition_id: UUID
    document_id: UUID
    actor_id: UUID
    context: dict[str, Any] | None = None


class WorkflowInstanceResponse(BaseModel):
    """Pydantic model for workflow instance responses."""

    id: UUID
    workflow_definition_id: UUID
    document_id: UUID
    current_state: str
    context: dict[str, Any]

    model_config = {"from_attributes": True}


class AdvanceRequest(BaseModel):
    """Pydantic model for advancing a workflow instance."""

    event: str
    actor_id: UUID


@router.post(
    "/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_definition(
    defn: WorkflowDefinitionCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbWorkflowDefinition:
    """Create a new workflow definition."""
    defn_id = defn.id or uuid4()
    db_defn = DbWorkflowDefinition(
        id=defn_id,
        name=defn.name,
        states=defn.states,
        transitions=defn.transitions,
    )
    db.add(db_defn)
    await db.commit()
    await db.refresh(db_defn)
    return db_defn


@router.post(
    "/instances",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow_instance(
    inst: WorkflowInstanceCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbWorkflowInstance:
    """Start a new workflow instance for a document."""
    audit_logger = DatabaseAuditLogger(db)
    engine = DatabaseWorkflowEngine(db, audit_logger)
    try:
        instance_id = await engine.start_workflow(
            workflow_definition_id=inst.workflow_definition_id,
            document_id=inst.document_id,
            actor_id=inst.actor_id,
            context=inst.context,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    result = await db.execute(
        select(DbWorkflowInstance).where(DbWorkflowInstance.id == instance_id)
    )
    return result.scalar_one()


@router.post("/instances/{instance_id}/advance", status_code=status.HTTP_200_OK)
async def advance_workflow_instance(
    instance_id: UUID,
    req: AdvanceRequest,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Advance the workflow instance state through a transition event."""
    audit_logger = DatabaseAuditLogger(db)
    engine = DatabaseWorkflowEngine(db, audit_logger)
    try:
        await engine.advance(
            instance_id=instance_id,
            event=req.event,
            actor_id=req.actor_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {"status": "success"}


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceResponse)
async def get_workflow_instance(
    instance_id: UUID,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbWorkflowInstance:
    """Retrieve the current state of a workflow instance."""
    result = await db.execute(
        select(DbWorkflowInstance).where(DbWorkflowInstance.id == instance_id)
    )
    db_inst = result.scalar_one_or_none()
    if not db_inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow instance not found",
        )
    return db_inst
