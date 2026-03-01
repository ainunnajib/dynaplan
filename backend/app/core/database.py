from itertools import cycle
from threading import Lock
from typing import Dict, List

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        return str(url.set(drivername="postgresql+asyncpg"))
    return database_url


def is_sqlite_url(database_url: str) -> bool:
    url = make_url(database_url)
    return url.get_backend_name() == "sqlite"


def build_engine_kwargs(database_url: str, echo: bool) -> Dict[str, object]:
    kwargs: Dict[str, object] = {"echo": echo}
    if is_sqlite_url(database_url):
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {"check_same_thread": False}
        return kwargs

    kwargs["pool_pre_ping"] = True
    kwargs["pool_size"] = settings.database_pool_size
    kwargs["max_overflow"] = settings.database_max_overflow
    kwargs["pool_timeout"] = settings.database_pool_timeout
    kwargs["pool_recycle"] = settings.database_pool_recycle
    return kwargs


def resolve_read_replica_urls(primary_url: str, replica_urls: List[str]) -> List[str]:
    normalized_replicas: List[str] = []
    seen = set()

    for replica_url in replica_urls:
        normalized = normalize_database_url(replica_url)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_replicas.append(normalized)

    if normalized_replicas:
        return normalized_replicas

    return [normalize_database_url(primary_url)]


def _build_engine(database_url: str) -> AsyncEngine:
    normalized_url = normalize_database_url(database_url)
    kwargs = build_engine_kwargs(normalized_url, echo=settings.debug)
    return create_async_engine(normalized_url, **kwargs)


engine = _build_engine(settings.database_url)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

read_replica_urls = resolve_read_replica_urls(
    settings.database_url,
    settings.database_read_replica_urls,
)
if settings.database_read_replica_urls:
    read_engines = [_build_engine(replica_url) for replica_url in read_replica_urls]
else:
    read_engines = [engine]
read_async_sessions = [
    async_sessionmaker(read_engine, class_=AsyncSession, expire_on_commit=False)
    for read_engine in read_engines
]
_read_session_cycle = cycle(read_async_sessions)
_read_session_cycle_lock = Lock()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_read_db() -> AsyncSession:
    with _read_session_cycle_lock:
        session_factory = next(_read_session_cycle)

    async with session_factory() as session:
        yield session


async def dispose_engines() -> None:
    seen = set()

    for current_engine in [engine] + read_engines:
        marker = id(current_engine)
        if marker in seen:
            continue
        seen.add(marker)
        await current_engine.dispose()
