"""SQLAlchemy ORM models for permissions and document management."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from docsgraph_server.db.base import Base


class DbUser(Base):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)


class DbGroup(Base):
    """SQLAlchemy model for groups/roles."""

    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class DbGroupMembership(Base):
    """SQLAlchemy model linking users to groups."""

    __tablename__ = "group_memberships"

    group_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class DbCollection(Base):
    """SQLAlchemy model for document collections."""

    __tablename__ = "collections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class DbDocument(Base):
    """SQLAlchemy model for documents."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    collection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True
    )


class DbACL(Base):
    """SQLAlchemy model for Access Control Lists (ACLs)."""

    __tablename__ = "acls"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "subject_id", "resource_id", "action", name="uq_acl_subject_resource_action"
        ),
    )
