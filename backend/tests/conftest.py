"""
Global pytest configuration and fixtures.
Sets test environment variables, sets up in-memory database, and overrides dependencies.
"""

import os
from collections.abc import AsyncGenerator

# Configure test environment before any application modules load
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["LIVE_TRADING"] = "false"
os.environ["JWT_SECRET"] = "test_super_secure_random_string_at_least_32_characters_long"

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings
from backend.core.kill_switch import kill_switch
from backend.database.models import Base
from backend.database.session import get_db
from backend.main import app

# Invalidate settings cache to load test environment overrides
get_settings.cache_clear()

# Shared SQLite in-memory engine across test runs
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    future=True,
)
test_sessionmaker = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Setup clean tables before each test and tear down after."""
    kill_switch.deactivate()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    kill_switch.deactivate()


@pytest.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated database session for direct model manipulation in tests."""
    async with test_sessionmaker() as session:
        yield session

