"""SQLAlchemy ORM models for sync operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from docsgraph_server.db.base import Base


class DbSyncOp(Base):
    """SQLAlchemy model for sync operations.

    Maps to the `sync_operations` table, keeping a log of all modifications
    made to synchronize client databases.
    """

    __tablename__ = "sync_operations"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    op_id: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, index=True)
    client_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    client_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
