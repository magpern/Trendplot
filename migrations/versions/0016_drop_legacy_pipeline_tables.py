"""Drop legacy full-pipeline tables (phase 2 cleanup).

Revision ID: 0016_drop_legacy_pipeline
Revises: 0015_ai_opportunity_ideation
Create Date: 2026-06-02
"""

from alembic import op

revision = "0016_drop_legacy_pipeline"
down_revision = "0015_ai_opportunity_ideation"
branch_labels = None
depends_on = None

LEGACY_TABLES = (
    "opportunity_campaign_items",
    "opportunity_campaigns",
    "opportunity_audiences",
    "opportunity_relationships",
    "authority_graph_edges",
    "opportunities",
    "opportunity_clusters",
    "authority_graph_nodes",
    "audience_profiles",
    "ai_recommendation_reviews",
    "ai_recommendation_review_runs",
    "ai_editorial_strategist_ideas",
    "ai_editorial_strategist_runs",
    "editorial_opportunity_concepts",
    "editorial_generation_runs",
    "market_opportunity_candidates",
    "market_signal_evidence",
    "market_signals",
    "market_topic_clusters",
    "market_intelligence_runs",
    "trend_discovery_queries",
    "trend_signals",
    "trend_discovery_runs",
    "demand_observations",
    "demand_observation_runs",
    "competitor_snapshots",
    "content_coverage",
    "content_clusters",
    "content_entities",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    for table in LEGACY_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise NotImplementedError("Restore from database backup to roll back legacy table drops.")
