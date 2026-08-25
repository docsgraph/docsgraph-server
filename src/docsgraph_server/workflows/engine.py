"""Workflow/automation engine interface and database execution."""

from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.audit.logger import DatabaseAuditLogger
from docsgraph_server.db.models import DbWorkflowDefinition, DbWorkflowInstance


class WorkflowEngine(Protocol):
    """Interface implemented by the workflow engine."""

    async def start_workflow(
        self,
        workflow_definition_id: UUID,
        document_id: UUID,
        actor_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> UUID:
        """Start a new workflow run and return its instance ID."""
        ...

    async def advance(self, instance_id: UUID, event: str, actor_id: UUID) -> None:
        """Advance a running workflow instance in response to `event`."""
        ...


class DatabaseWorkflowEngine:
    """SQLAlchemy-backed workflow engine implementing state machine execution."""

    def __init__(self, db: AsyncSession, audit_logger: DatabaseAuditLogger) -> None:
        """Initialize with DB session and audit logger."""
        self.db = db
        self.audit_logger = audit_logger

    async def start_workflow(
        self,
        workflow_definition_id: UUID,
        document_id: UUID,
        actor_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> UUID:
        """Start a new workflow run for a document."""
        # 1. Fetch workflow definition
        result = await self.db.execute(
            select(DbWorkflowDefinition).where(DbWorkflowDefinition.id == workflow_definition_id)
        )
        definition = result.scalar_one_or_none()
        if not definition:
            raise ValueError("Workflow definition not found")

        # 2. Get initial state (the first state in the states list)
        if not definition.states:
            raise ValueError("Workflow definition must have at least one state")
        initial_state = definition.states[0]

        # 3. Create workflow instance
        instance_id = uuid4()
        db_instance = DbWorkflowInstance(
            id=instance_id,
            workflow_definition_id=workflow_definition_id,
            document_id=document_id,
            current_state=initial_state,
            context=context or {},
        )
        self.db.add(db_instance)
        await self.db.commit()

        # 4. Audit log event
        await self.audit_logger.record_event(
            actor_id=actor_id,
            action="workflow.started",
            resource_id=instance_id,
            metadata={
                "workflow_definition_id": str(workflow_definition_id),
                "document_id": str(document_id),
                "initial_state": initial_state,
            },
        )

        return instance_id

    async def advance(self, instance_id: UUID, event: str, actor_id: UUID) -> None:
        """Advance a running workflow instance state."""
        # 1. Fetch the workflow instance
        res_instance = await self.db.execute(
            select(DbWorkflowInstance).where(DbWorkflowInstance.id == instance_id)
        )
        instance = res_instance.scalar_one_or_none()
        if not instance:
            raise ValueError("Workflow instance not found")

        # 2. Fetch the definition
        res_def = await self.db.execute(
            select(DbWorkflowDefinition).where(
                DbWorkflowDefinition.id == instance.workflow_definition_id
            )
        )
        definition = res_def.scalar_one_or_none()
        if not definition:
            raise ValueError("Workflow definition not found")

        # 3. Find matching transition
        from_state = instance.current_state
        to_state = None
        for transition in definition.transitions:
            if transition.get("from_state") == from_state and transition.get("event") == event:
                to_state = transition.get("to_state")
                break

        if not to_state:
            raise ValueError(f"Invalid transition from state '{from_state}' on event '{event}'")

        # 4. Update the state
        instance.current_state = to_state
        await self.db.commit()

        # 5. Record the state change audit log
        await self.audit_logger.record_event(
            actor_id=actor_id,
            action="workflow.state_change",
            resource_id=instance_id,
            metadata={
                "from_state": from_state,
                "to_state": to_state,
                "event": event,
                "document_id": str(instance.document_id),
            },
        )
