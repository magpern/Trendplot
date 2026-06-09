from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db import resolve_sqlite_database_path, sqlite_database_file, sync_database_url

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_INVENTORY_TABLE = "workspace_content_inventory"
_INVENTORY_REVISION = "0013_workspace_content_inventory"
_SQLITE_CONNECT_ARGS = {"timeout": 30}


def run_pending_migrations(database_url: str) -> None:
    """Apply Alembic migrations before serving requests."""
    started = time.perf_counter()
    alembic_ini = _PROJECT_ROOT / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found at %s; skipping migrations", alembic_ini)
        return

    cfg = _alembic_config(alembic_ini, database_url)
    sync_url = cfg.get_main_option("sqlalchemy.url") or ""
    db_file = sqlite_database_file(database_url)

    _repair_stale_inventory_revision(cfg, sync_url)

    head = _head_revision(cfg)
    current = _database_revision(sync_url)
    if current == head and _required_tables_present(sync_url, head):
        logger.info(
            "Database schema already at head (%s)%s; skipped migration upgrade in %.2fs",
            head,
            f" [{db_file}]" if db_file else "",
            time.perf_counter() - started,
        )
        return

    logger.info(
        "Upgrading database schema from %s to %s%s",
        current or "none",
        head,
        f" [{db_file}]" if db_file else "",
    )
    command.upgrade(cfg, "head")
    logger.info("Database schema upgrade complete in %.2fs", time.perf_counter() - started)


def _alembic_config(alembic_ini: Path, database_url: str) -> Config:
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    resolved_url = resolve_sqlite_database_path(database_url, base_dir=_PROJECT_ROOT)
    sync_url = sync_database_url(resolved_url)
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _migration_engine(sync_url: str):
    return create_engine(sync_url, connect_args=_SQLITE_CONNECT_ARGS)


def _head_revision(cfg: Config) -> str:
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected a single Alembic head, found: {heads}")
    return heads[0]


def _database_revision(sync_url: str) -> str | None:
    engine = _migration_engine(sync_url)
    try:
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            return None
        with engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()


def _required_tables_present(sync_url: str, head: str) -> bool:
    if head != _INVENTORY_REVISION:
        return True
    engine = _migration_engine(sync_url)
    try:
        return inspect(engine).has_table(_INVENTORY_TABLE)
    finally:
        engine.dispose()


def _repair_stale_inventory_revision(cfg: Config, sync_url: str) -> None:
    """Re-apply 0013 when alembic_version is stamped but the inventory table is missing."""
    engine = _migration_engine(sync_url)
    version: str | None = None
    needs_repair = False
    try:
        inspector = inspect(engine)
        if inspector.has_table(_INVENTORY_TABLE):
            return
        needs_repair = True
        if inspector.has_table("alembic_version"):
            with engine.connect() as connection:
                version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()

    if not needs_repair:
        return

    logger.warning(
        "Missing %s (alembic_version=%s); re-applying inventory migration",
        _INVENTORY_TABLE,
        version,
    )
    if version == _INVENTORY_REVISION:
        command.downgrade(cfg, "0012_analyze_flow_runs")
    command.upgrade(cfg, "head")
