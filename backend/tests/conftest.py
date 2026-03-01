import os
import tempfile
from typing import Optional, Tuple

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.main import app
from app.models import Base

# File-backed SQLite fallback for async test runs (production-like connection semantics).
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "dynaplan_test.sqlite3")
TEST_DB_BACKEND_MODE = os.getenv("DYNAPLAN_TEST_DB_BACKEND", "auto").strip().lower()
TEST_DATABASE_URL = os.getenv("DYNAPLAN_TEST_DATABASE_URL", "").strip()
_POSTGRES_CONTAINER = None


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url

    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url[len("postgresql://"):]

    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url[len("postgres://"):]

    return database_url


def _create_sqlite_engine() -> AsyncEngine:
    return create_async_engine(
        f"sqlite+aiosqlite:///{TEST_DB_PATH}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )


def _create_engine_from_url(database_url: str) -> AsyncEngine:
    normalized_url = _normalize_database_url(database_url)
    if normalized_url.startswith("sqlite"):
        return create_async_engine(
            normalized_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

    return create_async_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
    )


def _create_postgres_container_engine() -> Tuple[Optional[AsyncEngine], Optional[object]]:
    try:
        from testcontainers.postgres import PostgresContainer
    except Exception:
        return None, None

    container = None
    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
        connection_url = container.get_connection_url()
        engine = _create_engine_from_url(connection_url)
        return engine, container
    except Exception:
        if container is not None:
            container.stop()
        return None, None


def _build_test_engine() -> Tuple[AsyncEngine, str]:
    global _POSTGRES_CONTAINER

    if TEST_DATABASE_URL:
        engine = _create_engine_from_url(TEST_DATABASE_URL)
        normalized_url = _normalize_database_url(TEST_DATABASE_URL)
        backend = "sqlite" if normalized_url.startswith("sqlite") else "postgresql"
        return engine, backend

    if TEST_DB_BACKEND_MODE in {"auto", "postgres"}:
        postgres_engine, postgres_container = _create_postgres_container_engine()
        if postgres_engine is not None:
            _POSTGRES_CONTAINER = postgres_container
            return postgres_engine, "postgresql"

        if TEST_DB_BACKEND_MODE == "postgres":
            raise RuntimeError(
                "DYNAPLAN_TEST_DB_BACKEND=postgres requested but PostgreSQL "
                "test container could not be started."
            )

    return _create_sqlite_engine(), "sqlite"


engine, TEST_DB_BACKEND = _build_test_engine()
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def pytest_sessionfinish(session, exitstatus):
    del session
    del exitstatus
    if _POSTGRES_CONTAINER is not None:
        _POSTGRES_CONTAINER.stop()
