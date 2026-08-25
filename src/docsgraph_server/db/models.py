"""SQLAlchemy ORM models for workflows, documents, and audit logs."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from docsgraph_server.db.base import Base


def utc_now_naive() -> datetime:
    """Helper to return a naive datetime representing UTC time."""
    return datetime.now(UTC).replace(tzinfo=None)


class DbDocument(Base):
    """SQLAlchemy model for documents."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class DbWorkflowDefinition(Base):
    """SQLAlchemy model for workflow definitions (states and transitions)."""

    __tablename__ = "workflow_definitions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    states: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    transitions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class DbWorkflowInstance(Base):
    """SQLAlchemy model for workflow instances attached to documents."""

    __tablename__ = "workflow_instances"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_definition_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    current_state: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class DbAuditEvent(Base):
    """SQLAlchemy model for compliance and security audit logs."""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
