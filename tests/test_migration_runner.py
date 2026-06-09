from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from app.migration_runner import _database_revision, _head_revision, _required_tables_present, run_pending_migrations


def test_run_pending_migrations_skips_when_already_at_head() -> None:
    project_root = Path(__file__).resolve().parents[1]
    db_path = project_root / "data" / "seo_content_worker.db"
    if not db_path.exists():
        return

    database_url = f"sqlite:///{db_path.as_posix()}"
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    sync_url = database_url
    head = _head_revision(cfg)
    current = _database_revision(sync_url)
    assert current == head
    assert _required_tables_present(sync_url, head)
    run_pending_migrations(database_url)
