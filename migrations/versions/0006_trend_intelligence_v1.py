"""add trend intelligence v1 and publishing memory

Revision ID: 0006_trend_intelligence_v1
Revises: 0005_trendplot_connector_events
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_trend_intelligence_v1"
down_revision = "0005_trendplot_connector_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trend_signals", sa.Column("run_id", sa.String(), nullable=True))
    op.add_column("trend_signals", sa.Column("query_id", sa.String(), nullable=True))
    op.add_column("trend_signals", sa.Column("query", sa.Text(), nullable=True))
    op.add_column("trend_signals", sa.Column("niche_relevance", sa.Float(), nullable=True))
    op.add_column("trend_signals", sa.Column("audience_relevance", sa.Float(), nullable=True))
    op.add_column("trend_signals", sa.Column("business_relevance", sa.Float(), nullable=True))
    op.add_column("trend_signals", sa.Column("opportunity_score", sa.Float(), nullable=True))
    op.add_column("trend_signals", sa.Column("why_it_matters", sa.Text(), nullable=True))
    op.add_column("trend_signals", sa.Column("recommended_angle", sa.Text(), nullable=True))
    op.add_column("trend_signals", sa.Column("raw_signal_json", sa.JSON(), nullable=True))
    op.add_column("trend_signals", sa.Column("status", sa.String(), nullable=False, server_default="active"))

    op.create_table(
        "trend_discovery_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("provider_status_json", sa.JSON(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_trend_discovery_runs_workspace", "trend_discovery_runs", ["workspace_id"])
    op.create_index("idx_trend_discovery_runs_analysis", "trend_discovery_runs", ["analysis_job_id"])

    op.create_table(
        "trend_discovery_queries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(), nullable=True),
        sa.Column("target_entity", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_trend_discovery_queries_run", "trend_discovery_queries", ["run_id"])

    op.create_table(
        "content_entities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("post_id", sa.String(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("content_plan_item_id", sa.String(), nullable=True),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_content_entities_workspace", "content_entities", ["workspace_id"])
    op.create_index("idx_content_entities_entity", "content_entities", ["entity"])

    op.create_table(
        "content_clusters",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("post_id", sa.String(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("content_plan_item_id", sa.String(), nullable=True),
        sa.Column("cluster", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_content_clusters_workspace", "content_clusters", ["workspace_id"])
    op.create_index("idx_content_clusters_cluster", "content_clusters", ["cluster"])

    op.create_table(
        "content_coverage",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("coverage_type", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=True),
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draft_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gap_score", sa.Float(), nullable=True),
        sa.Column("saturation_score", sa.Float(), nullable=True),
        sa.Column("cannibalization_risk", sa.Float(), nullable=True),
        sa.Column("duplicate_topic_risk", sa.Float(), nullable=True),
        sa.Column("refresh_score", sa.Float(), nullable=True),
        sa.Column("refresh_candidate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("refresh_reason", sa.Text(), nullable=True),
        sa.Column("last_published", sa.String(), nullable=True),
        sa.Column("last_updated", sa.String(), nullable=True),
        sa.Column("last_major_update", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_content_coverage_workspace", "content_coverage", ["workspace_id"])
    op.create_index("idx_content_coverage_type_name", "content_coverage", ["workspace_id", "coverage_type", "name"])


def downgrade() -> None:
    op.drop_index("idx_content_coverage_type_name", table_name="content_coverage")
    op.drop_index("idx_content_coverage_workspace", table_name="content_coverage")
    op.drop_table("content_coverage")
    op.drop_index("idx_content_clusters_cluster", table_name="content_clusters")
    op.drop_index("idx_content_clusters_workspace", table_name="content_clusters")
    op.drop_table("content_clusters")
    op.drop_index("idx_content_entities_entity", table_name="content_entities")
    op.drop_index("idx_content_entities_workspace", table_name="content_entities")
    op.drop_table("content_entities")
    op.drop_index("idx_trend_discovery_queries_run", table_name="trend_discovery_queries")
    op.drop_table("trend_discovery_queries")
    op.drop_index("idx_trend_discovery_runs_analysis", table_name="trend_discovery_runs")
    op.drop_index("idx_trend_discovery_runs_workspace", table_name="trend_discovery_runs")
    op.drop_table("trend_discovery_runs")
    op.drop_column("trend_signals", "status")
    op.drop_column("trend_signals", "raw_signal_json")
    op.drop_column("trend_signals", "recommended_angle")
    op.drop_column("trend_signals", "why_it_matters")
    op.drop_column("trend_signals", "opportunity_score")
    op.drop_column("trend_signals", "business_relevance")
    op.drop_column("trend_signals", "audience_relevance")
    op.drop_column("trend_signals", "niche_relevance")
    op.drop_column("trend_signals", "query")
    op.drop_column("trend_signals", "query_id")
    op.drop_column("trend_signals", "run_id")
