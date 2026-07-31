"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from docsgraph_server.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Return a cached async SQLAlchemy engine built from application settings."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False, future=True)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the shared engine."""
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an `AsyncSession` for the request lifetime."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session
