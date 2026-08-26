"""SQLAlchemy ORM models for retention policies, audit events, and documents."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from docsgraph_server.db.base import Base


def utc_now_naive() -> datetime:
    """Helper to return a naive datetime representing UTC time."""
    return datetime.now(UTC).replace(tzinfo=None)


class DbCollection(Base):
    """SQLAlchemy model for collections."""

    __tablename__ = "collections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class DbDocument(Base):
    """SQLAlchemy model for documents."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    collection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DbAuditEvent(Base):
    """SQLAlchemy model for compliance and security audit logs."""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class DbRetentionPolicy(Base):
    """SQLAlchemy model for document and log retention policies."""

    __tablename__ = "retention_policies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    collection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("collections.id", ondelete="CASCADE"), nullable=True
    )
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
