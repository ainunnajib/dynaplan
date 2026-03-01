from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.database import (
    build_engine_kwargs,
    is_sqlite_url,
    normalize_database_url,
    resolve_read_replica_urls,
)


def test_settings_parses_read_replica_urls_from_csv() -> None:
    settings = Settings(database_read_replica_urls="postgresql://replica-a/db,postgresql://replica-b/db")

    assert settings.database_read_replica_urls == [
        "postgresql://replica-a/db",
        "postgresql://replica-b/db",
    ]


def test_settings_parses_read_replica_urls_from_list() -> None:
    settings = Settings(
        database_read_replica_urls=["postgresql://replica-a/db", "postgresql://replica-b/db"]
    )

    assert settings.database_read_replica_urls == [
        "postgresql://replica-a/db",
        "postgresql://replica-b/db",
    ]


def test_settings_parses_blank_read_replica_urls_as_empty_list() -> None:
    settings = Settings(database_read_replica_urls="  ")

    assert settings.database_read_replica_urls == []


def test_normalize_database_url_converts_postgresql_driver() -> None:
    normalized = normalize_database_url("postgresql://user:pass@localhost:5432/dynaplan")

    assert normalized.startswith("postgresql+asyncpg://")


def test_normalize_database_url_converts_postgres_driver() -> None:
    normalized = normalize_database_url("postgres://user:pass@localhost:5432/dynaplan")

    assert normalized.startswith("postgresql+asyncpg://")


def test_normalize_database_url_keeps_sqlite() -> None:
    url = "sqlite+aiosqlite:////tmp/test.db"

    assert normalize_database_url(url) == url


def test_is_sqlite_url() -> None:
    assert is_sqlite_url("sqlite+aiosqlite:////tmp/test.db") is True
    assert is_sqlite_url("postgresql+asyncpg://localhost:5432/dynaplan") is False


def test_build_engine_kwargs_uses_null_pool_for_sqlite() -> None:
    kwargs = build_engine_kwargs("sqlite+aiosqlite:////tmp/test.db", echo=False)

    assert kwargs["poolclass"] is NullPool
    assert kwargs["connect_args"] == {"check_same_thread": False}


def test_build_engine_kwargs_uses_pool_settings_for_postgres() -> None:
    kwargs = build_engine_kwargs("postgresql+asyncpg://localhost:5432/dynaplan", echo=True)

    assert kwargs["echo"] is True
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800


def test_resolve_read_replica_urls_deduplicates_and_normalizes() -> None:
    resolved = resolve_read_replica_urls(
        "postgresql://primary:5432/dynaplan",
        ["postgresql://replica:5432/dynaplan", "postgres://replica:5432/dynaplan"],
    )

    assert resolved == ["postgresql+asyncpg://replica:5432/dynaplan"]


def test_resolve_read_replica_urls_falls_back_to_primary() -> None:
    resolved = resolve_read_replica_urls("postgres://primary:5432/dynaplan", [])

    assert resolved == ["postgresql+asyncpg://primary:5432/dynaplan"]
