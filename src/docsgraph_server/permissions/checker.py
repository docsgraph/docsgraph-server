"""Permission/ACL checking interface.

Defines the contract used to authorize actions against resources
(documents, folders, workflows, ...).
"""

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbACL, DbDocument, DbGroupMembership, DbUser


class Action(StrEnum):
    """An action a subject may attempt against a resource."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHARE = "share"
    ADMIN = "admin"


class PermissionChecker(Protocol):
    """Interface implemented by permission/ACL backends."""

    async def can(self, subject_id: UUID, action: Action, resource_id: UUID) -> bool:
        """Return whether `subject_id` may perform `action` on `resource_id`."""
        ...


class DatabasePermissionChecker:
    """SQLAlchemy-backed permission checker enforcing RBAC and ACLs."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with a database session."""
        self.db = db

    async def can(self, subject_id: UUID, action: Action, resource_id: UUID) -> bool:
        """Return whether the user or their groups have the permission to act on the resource."""
        # 1. Get the user's role. Admin bypasses all checks.
        user_res = await self.db.execute(select(DbUser).where(DbUser.id == subject_id))
        user = user_res.scalar_one_or_none()
        if user and user.role == "admin":
            return True

        # 2. Collect subject IDs (user's own ID + all group/role IDs they are part of)
        subject_ids = [subject_id]
        groups_res = await self.db.execute(
            select(DbGroupMembership.group_id).where(DbGroupMembership.user_id == subject_id)
        )
        subject_ids.extend(groups_res.scalars().all())

        # 3. Check direct ACLs on this resource
        acl_res = await self.db.execute(
            select(DbACL).where(
                DbACL.subject_id.in_(subject_ids),
                DbACL.resource_id == resource_id,
                DbACL.action == action.value,
            )
        )
        if acl_res.scalar_one_or_none():
            return True

        # 4. If the resource is a document, check collection-level ACL
        doc_res = await self.db.execute(select(DbDocument).where(DbDocument.id == resource_id))
        doc = doc_res.scalar_one_or_none()
        if doc and doc.collection_id:
            coll_acl_res = await self.db.execute(
                select(DbACL).where(
                    DbACL.subject_id.in_(subject_ids),
                    DbACL.resource_id == doc.collection_id,
                    DbACL.resource_type == "collection",
                    DbACL.action == action.value,
                )
            )
            if coll_acl_res.scalar_one_or_none():
                return True

        return False
