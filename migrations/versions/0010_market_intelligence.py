"""market intelligence engine tables

Revision ID: 0010_market_intelligence
Revises: 0009_demand_observations
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_market_intelligence"
down_revision = "0009_demand_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_intelligence_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String()),
        sa.Column("signals_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("signals_persisted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clusters_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidates_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_market_intelligence_runs_workspace", "market_intelligence_runs", ["workspace_id", "created_at"])

    op.create_table(
        "market_signals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("topic", sa.Text()),
        sa.Column("entity", sa.Text()),
        sa.Column("audience", sa.Text()),
        sa.Column("market_scope", sa.String()),
        sa.Column("language", sa.String()),
        sa.Column("country", sa.String()),
        sa.Column("confidence", sa.Float()),
        sa.Column("freshness", sa.Float()),
        sa.Column("velocity", sa.Float()),
        sa.Column("novelty", sa.Float()),
        sa.Column("relevance", sa.Float()),
        sa.Column("evidence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("observed_at", sa.String(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["market_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_market_signals_workspace_observed", "market_signals", ["workspace_id", "observed_at"])
    op.create_index("idx_market_signals_provider", "market_signals", ["workspace_id", "provider", "signal_type"])
    op.create_index("idx_market_signals_topic", "market_signals", ["workspace_id", "topic"])
    op.create_index("idx_market_signals_run", "market_signals", ["run_id"])

    op.create_table(
        "market_signal_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.String(), nullable=False),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("snippet", sa.Text()),
        sa.Column("source_name", sa.Text()),
        sa.Column("published_at", sa.String()),
        sa.Column("metric_name", sa.String()),
        sa.Column("metric_value", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("raw_payload_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["market_signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_market_signal_evidence_signal", "market_signal_evidence", ["signal_id"])

    op.create_table(
        "market_topic_clusters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("entities_json", sa.JSON()),
        sa.Column("audiences_json", sa.JSON()),
        sa.Column("dominant_intents_json", sa.JSON()),
        sa.Column("source_mix_json", sa.JSON()),
        sa.Column("confidence", sa.Float()),
        sa.Column("freshness", sa.Float()),
        sa.Column("velocity", sa.Float()),
        sa.Column("novelty", sa.Float()),
        sa.Column("relevance", sa.Float()),
        sa.Column("saturation", sa.Float()),
        sa.Column("opportunity_score", sa.Float()),
        sa.Column("signal_ids_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["market_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_market_topic_clusters_workspace", "market_topic_clusters", ["workspace_id", "opportunity_score"])
    op.create_index("idx_market_topic_clusters_run", "market_topic_clusters", ["run_id"])

    op.create_table(
        "market_opportunity_candidates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("cluster_id", sa.String()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("target_keyword", sa.Text()),
        sa.Column("content_format", sa.String()),
        sa.Column("editorial_angle", sa.Text()),
        sa.Column("audience", sa.Text()),
        sa.Column("intent", sa.String()),
        sa.Column("action_hint", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("source_signal_ids_json", sa.JSON()),
        sa.Column("risk_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["market_topic_clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["market_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_market_opportunity_candidates_workspace", "market_opportunity_candidates", ["workspace_id", "confidence"])
    op.create_index("idx_market_opportunity_candidates_run", "market_opportunity_candidates", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_market_opportunity_candidates_run", table_name="market_opportunity_candidates")
    op.drop_index("idx_market_opportunity_candidates_workspace", table_name="market_opportunity_candidates")
    op.drop_table("market_opportunity_candidates")
    op.drop_index("idx_market_topic_clusters_run", table_name="market_topic_clusters")
    op.drop_index("idx_market_topic_clusters_workspace", table_name="market_topic_clusters")
    op.drop_table("market_topic_clusters")
    op.drop_index("idx_market_signal_evidence_signal", table_name="market_signal_evidence")
    op.drop_table("market_signal_evidence")
    op.drop_index("idx_market_signals_run", table_name="market_signals")
    op.drop_index("idx_market_signals_topic", table_name="market_signals")
    op.drop_index("idx_market_signals_provider", table_name="market_signals")
    op.drop_index("idx_market_signals_workspace_observed", table_name="market_signals")
    op.drop_table("market_signals")
    op.drop_index("idx_market_intelligence_runs_workspace", table_name="market_intelligence_runs")
    op.drop_table("market_intelligence_runs")
