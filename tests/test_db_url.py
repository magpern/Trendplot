from pathlib import Path

from app.config import Settings, _PROJECT_ROOT
from app.db import normalize_database_url, resolve_sqlite_database_path, sqlite_database_file


def test_resolve_sqlite_database_path_makes_relative_path_absolute() -> None:
    relative = "sqlite+aiosqlite:///./data/seo_content_worker.db"
    resolved = resolve_sqlite_database_path(relative, base_dir=_PROJECT_ROOT)
    expected = (_PROJECT_ROOT / "data" / "seo_content_worker.db").resolve().as_posix()
    assert expected in resolved
    assert "./" not in resolved


def test_settings_database_url_is_absolute() -> None:
    settings = Settings()
    db_file = sqlite_database_file(settings.database_url)
    assert db_file is not None
    assert db_file.is_absolute()
    assert db_file == (_PROJECT_ROOT / "data" / "seo_content_worker.db").resolve()


def test_normalize_database_url_preserves_async_driver() -> None:
    normalized = normalize_database_url("sqlite:///./data/seo_content_worker.db")
    assert normalized.startswith("sqlite+aiosqlite:///")
    assert Path(make_url_path(normalized)).is_absolute()


def make_url_path(database_url: str) -> str:
    from sqlalchemy.engine import make_url

    return make_url(database_url).database or ""
