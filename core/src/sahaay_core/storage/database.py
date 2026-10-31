"""Database session and connection management for SQLite."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from sahaay_core.config.settings import settings
from sahaay_core.storage.models import Base

_engine: Optional[AsyncEngine] = None
_AsyncSessionLocal = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.async_database_url,
            echo=settings.debug,
            future=True,
        )
    return _engine


def get_session_maker():
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal


# Backward compatibility
engine = None
AsyncSessionLocal = None


async def init_db() -> None:
    """Initialize database tables reliably."""
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    from sahaay_core.storage.persistence import init_persistence_schema

    init_persistence_schema()
    try:
        from sqlalchemy import create_engine

        sync_engine = create_engine(f"sqlite:///{settings.sync_database_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()
    except Exception:
        pass


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around a series of operations."""
    maker = get_session_maker()
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
