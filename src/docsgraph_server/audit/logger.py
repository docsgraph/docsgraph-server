"""Audit event recording interface.

Defines the contract used to append immutable audit log entries for
security- and compliance-relevant actions (document access, permission
changes, exports, ...). No concrete storage backend is chosen yet.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


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
        """Append an immutable audit log entry.

        Args:
            actor_id: The subject (user/service) performing the action.
            action: A short machine-readable action name, e.g. `"document.read"`.
            resource_id: The affected resource, if any.
            metadata: Additional structured context about the event.
            occurred_at: When the event occurred; defaults to server time if omitted.
        """
        ...
