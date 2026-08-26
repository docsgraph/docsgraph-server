"""Retention policy configuration API routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbRetentionPolicy
from docsgraph_server.db.session import get_session
from docsgraph_server.retention.policy import DatabaseRetentionPolicyEnforcer

router = APIRouter(prefix="/retention", tags=["retention"])


class RetentionPolicyCreate(BaseModel):
    """Pydantic model for creating a retention policy."""

    id: UUID | None = None
    collection_id: UUID | None = None
    policy_type: str = Field(..., description="Either 'document' or 'audit_log'")
    retention_days: int = Field(..., gt=0)


class RetentionPolicyResponse(BaseModel):
    """Pydantic model for retention policy responses."""

    id: UUID
    collection_id: UUID | None
    policy_type: str
    retention_days: int

    model_config = {"from_attributes": True}


@router.post(
    "/policies",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_retention_policy(
    policy: RetentionPolicyCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbRetentionPolicy:
    """Create a new retention policy."""
    if policy.policy_type not in ("document", "audit_log"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="policy_type must be either 'document' or 'audit_log'",
        )
    policy_id = policy.id or uuid4()
    db_policy = DbRetentionPolicy(
        id=policy_id,
        collection_id=policy.collection_id,
        policy_type=policy.policy_type,
        retention_days=policy.retention_days,
    )
    db.add(db_policy)
    await db.commit()
    await db.refresh(db_policy)
    return db_policy


@router.get("/policies", response_model=list[RetentionPolicyResponse])
async def list_retention_policies(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbRetentionPolicy]:
    """List all configured retention policies."""
    result = await db.execute(select(DbRetentionPolicy))
    return list(result.scalars().all())


@router.post("/policies/{policy_id}/apply", status_code=status.HTTP_200_OK)
async def apply_retention_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, int]:
    """Execute a retention policy and purge expired data."""
    enforcer = DatabaseRetentionPolicyEnforcer(db)
    try:
        purged = await enforcer.apply_policy(policy_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return {"purged_count": purged}
