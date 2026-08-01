"""Retention policy enforcement interface.

Defines the contract used to apply organization-configured retention
rules (e.g. "delete after N days", "legal hold") to documents and other
resources. No concrete scheduling/enforcement mechanism is chosen yet.
"""

from typing import Protocol
from uuid import UUID


class RetentionPolicyEnforcer(Protocol):
    """Interface implemented by retention policy enforcement."""

    async def apply_policy(self, policy_id: UUID) -> int:
        """Apply a retention policy, returning the number of resources affected."""
        ...

    async def is_under_legal_hold(self, resource_id: UUID) -> bool:
        """Return whether a resource is exempt from retention deletion."""
        ...
