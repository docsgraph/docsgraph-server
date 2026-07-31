"""Permission/ACL checking interface.

Defines the contract used to authorize actions against resources
(documents, folders, workflows, ...). No concrete permission model
(RBAC, ABAC, per-object ACLs) is chosen yet; this scaffolds the interface.
"""

from enum import StrEnum
from typing import Protocol
from uuid import UUID


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
