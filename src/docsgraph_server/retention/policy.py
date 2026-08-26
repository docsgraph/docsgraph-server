"""Retention policy enforcement interface and database implementation."""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbAuditEvent, DbDocument, DbRetentionPolicy


class RetentionPolicyEnforcer(Protocol):
    """Interface implemented by retention policy enforcement."""

    async def apply_policy(self, policy_id: UUID) -> int:
        """Apply a retention policy, returning the number of resources affected."""
        ...

    async def is_under_legal_hold(self, resource_id: UUID) -> bool:
        """Return whether a resource is exempt from retention deletion."""
        ...


class DatabaseRetentionPolicyEnforcer:
    """SQLAlchemy-backed implementation of the retention policy enforcer."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the enforcer with a database session."""
        self.db = db

    async def is_under_legal_hold(self, resource_id: UUID) -> bool:
        """Return whether a document is under legal hold (exempt from purge)."""
        result = await self.db.execute(
            select(DbDocument.legal_hold).where(DbDocument.id == resource_id)
        )
        val = result.scalar_one_or_none()
        return bool(val)

    async def apply_policy(self, policy_id: UUID) -> int:
        """Purge data matching the specified retention policy.

        Returns:
            The number of records purged (deleted).
        """
        res_policy = await self.db.execute(
            select(DbRetentionPolicy).where(DbRetentionPolicy.id == policy_id)
        )
        policy = res_policy.scalar_one_or_none()
        if not policy:
            raise ValueError("Retention policy not found")

        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=policy.retention_days)
        purged_count = 0

        if policy.policy_type == "document":
            doc_query = select(DbDocument).where(
                DbDocument.created_at < cutoff,
                DbDocument.legal_hold == False,  # noqa: E712
            )
            if policy.collection_id:
                doc_query = doc_query.where(DbDocument.collection_id == policy.collection_id)

            result = await self.db.execute(doc_query)
            expired_docs = result.scalars().all()

            for doc in expired_docs:
                await self.db.delete(doc)
                purged_count += 1

        elif policy.policy_type == "audit_log":
            audit_query = select(DbAuditEvent).where(DbAuditEvent.occurred_at < cutoff)
            result = await self.db.execute(audit_query)
            expired_events = result.scalars().all()

            for event in expired_events:
                await self.db.delete(event)
                purged_count += 1

        await self.db.commit()
        return purged_count
