"""Permission/ACL management API routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbACL, DbCollection, DbGroup, DbGroupMembership, DbUser
from docsgraph_server.db.session import get_session

router = APIRouter(prefix="/permissions", tags=["permissions"])


class UserCreate(BaseModel):
    """Pydantic model for creating a user."""

    id: UUID | None = None
    username: str
    role: str = "user"


class GroupCreate(BaseModel):
    """Pydantic model for creating a group/role."""

    id: UUID | None = None
    name: str


class MemberAdd(BaseModel):
    """Pydantic model for adding a group member."""

    user_id: UUID


class ACLCreate(BaseModel):
    """Pydantic model for creating an ACL entry."""

    id: UUID | None = None
    subject_id: UUID
    resource_id: UUID
    resource_type: str
    action: str


class CollectionCreate(BaseModel):
    """Pydantic model for creating a collection."""

    id: UUID | None = None
    name: str


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Create a user with an optional custom ID and role."""
    user_id = user.id or uuid4()
    db_user = DbUser(id=user_id, username=user.username, role=user.role)
    db.add(db_user)
    await db.commit()
    return {"id": str(user_id), "username": user.username, "role": user.role}


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    group: GroupCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Create a group/role."""
    group_id = group.id or uuid4()
    db_group = DbGroup(id=group_id, name=group.name)
    db.add(db_group)
    await db.commit()
    return {"id": str(group_id), "name": group.name}


@router.post("/groups/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: UUID,
    member: MemberAdd,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Add a user to a group."""
    db_member = DbGroupMembership(group_id=group_id, user_id=member.user_id)
    db.add(db_member)
    await db.commit()
    return {"group_id": str(group_id), "user_id": str(member.user_id)}


@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection: CollectionCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Create a document collection."""
    collection_id = collection.id or uuid4()
    db_collection = DbCollection(id=collection_id, name=collection.name)
    db.add(db_collection)
    await db.commit()
    return {"id": str(collection_id), "name": collection.name}


@router.post("/acls", status_code=status.HTTP_201_CREATED)
async def create_acl(
    acl: ACLCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """Define an ACL entry."""
    acl_id = acl.id or uuid4()
    db_acl = DbACL(
        id=acl_id,
        subject_id=acl.subject_id,
        resource_id=acl.resource_id,
        resource_type=acl.resource_type,
        action=acl.action,
    )
    db.add(db_acl)
    await db.commit()
    return {
        "id": str(acl_id),
        "subject_id": str(acl.subject_id),
        "resource_id": str(acl.resource_id),
        "resource_type": acl.resource_type,
        "action": acl.action,
    }
