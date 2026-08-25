"""Audit event recording interface.

Defines the contract used to append immutable audit log entries.
"""

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbAuditEvent


class AuditLogger(Protocol):
    """Interface implemented by audit log backends."""

    async def record_event(
        self,
        actor_id: UUID,
        action: str,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Append an immutable audit log entry."""
        ...


class DatabaseAuditLogger:
    """SQLAlchemy-backed audit logger appending immutable events to the database."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the audit logger with a database session."""
        self.db = db

    async def record_event(
        self,
        actor_id: UUID,
        action: str,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Append an immutable audit log entry.

        Args:
            actor_id: The subject (user/service) performing the action.
            action: A short machine-readable action name, e.g. `"document.read"`.
            resource_id: The affected resource, if any.
            metadata: Additional structured context about the event.
            occurred_at: When the event occurred; defaults to server time if omitted.
        """
        event_id = uuid4()
        db_event = DbAuditEvent(
            id=event_id,
            actor_id=actor_id,
            action=action,
            resource_id=resource_id,
            metadata_json=metadata,
            occurred_at=occurred_at or datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(db_event)
        await self.db.commit()
