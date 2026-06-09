from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event, make_url
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class Database:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def close(self) -> None:
        await self.engine.dispose()


def resolve_sqlite_database_path(database_url: str, *, base_dir: Path | None = None) -> str:
    """Resolve relative SQLite file paths against the project root."""
    if not database_url:
        return database_url

    url = make_url(database_url)
    if url.drivername not in {"sqlite", "sqlite+aiosqlite"}:
        return database_url
    if not url.database or url.database == ":memory:":
        return database_url

    db_path = Path(url.database)
    if db_path.is_absolute():
        return database_url

    root = base_dir or _PROJECT_ROOT
    absolute_path = (root / db_path).resolve()
    return url.set(database=absolute_path.as_posix()).render_as_string(hide_password=False)


def sqlite_database_file(database_url: str) -> Path | None:
    """Return the on-disk SQLite file for a database URL, if applicable."""
    url = make_url(resolve_sqlite_database_path(database_url))
    if url.drivername not in {"sqlite", "sqlite+aiosqlite"}:
        return None
    if not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


def normalize_database_url(database_url: str) -> str:
    if not database_url:
        raise ValueError("DATABASE_URL must not be empty.")

    database_url = resolve_sqlite_database_path(database_url)
    url = make_url(database_url)
    if url.drivername == "sqlite":
        return url.set(drivername="sqlite+aiosqlite").render_as_string(hide_password=False)
    if url.drivername == "sqlite+aiosqlite":
        return url.render_as_string(hide_password=False)
    if url.drivername == "postgresql+psycopg":
        return url.render_as_string(hide_password=False)

    raise ValueError(
        "Unsupported DATABASE_URL. Use sqlite:///..., sqlite+aiosqlite:///..., "
        "or postgresql+psycopg://..."
    )


def sync_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "sqlite+aiosqlite":
        return url.set(drivername="sqlite").render_as_string(hide_password=False)
    return url.render_as_string(hide_password=False)


def create_database(database_url: str) -> Database:
    normalized_url = normalize_database_url(database_url)
    _ensure_sqlite_parent_directory(make_url(normalized_url))

    engine = create_async_engine(normalized_url)
    if make_url(normalized_url).drivername == "sqlite+aiosqlite":
        _enable_sqlite_foreign_keys(engine)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return Database(engine=engine, session_factory=session_factory)


def _ensure_sqlite_parent_directory(url: URL) -> None:
    if url.drivername != "sqlite+aiosqlite" or not url.database or url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
