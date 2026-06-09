"""Export row counts for legacy database tables."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import resolve_sqlite_database_path, sync_database_url

OUTPUT_PATH = ROOT / "docs" / "architecture" / "legacy_table_counts.json"

LEGACY_TABLES: tuple[str, ...] = (
    "market_intelligence_runs",
    "market_signals",
    "market_signal_evidence",
    "market_topic_clusters",
    "market_opportunity_candidates",
    "editorial_generation_runs",
    "editorial_opportunity_concepts",
    "ai_editorial_strategist_runs",
    "ai_editorial_strategist_ideas",
    "ai_recommendation_review_runs",
    "ai_recommendation_reviews",
    "trend_signals",
    "trend_discovery_runs",
    "trend_discovery_queries",
    "demand_observation_runs",
    "demand_observations",
    "competitor_snapshots",
    "content_entities",
    "content_clusters",
    "content_coverage",
    "opportunities",
    "opportunity_clusters",
    "opportunity_audiences",
    "authority_graph_nodes",
    "authority_graph_edges",
    "opportunity_relationships",
    "audience_profiles",
    "opportunity_campaigns",
    "opportunity_campaign_items",
)


def _count_table(engine, table_name: str) -> dict[str, object]:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return {"exists": False, "count": None}

    try:
        with engine.connect() as connection:
            count = connection.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar_one()
        return {"exists": True, "count": int(count)}
    except SQLAlchemyError as exc:
        return {"exists": True, "count": None, "error": str(exc)}


def main() -> None:
    settings = get_settings()
    database_url = sync_database_url(
        resolve_sqlite_database_path(settings.database_url)
    )
    engine = create_engine(database_url)

    tables: dict[str, dict[str, object]] = {}
    try:
        for table_name in LEGACY_TABLES:
            tables[table_name] = _count_table(engine, table_name)
    finally:
        engine.dispose()

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "database_url": database_url.split("@")[-1] if "@" in database_url else database_url,
        "tables": tables,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
