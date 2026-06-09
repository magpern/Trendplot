"""add demand observations

Revision ID: 0009_demand_observations
Revises: 0008_opportunity_recommendations
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_demand_observations"
down_revision = "0008_opportunity_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demand_observation_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.Column("date_start", sa.String(), nullable=True),
        sa.Column("date_end", sa.String(), nullable=True),
        sa.Column("rows_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_persisted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_demand_observation_runs_workspace",
        "demand_observation_runs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "idx_demand_observation_runs_provider",
        "demand_observation_runs",
        ["workspace_id", "provider", "status"],
    )

    op.create_table(
        "demand_observations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("observed_at", sa.String(), nullable=False),
        sa.Column("date_start", sa.String(), nullable=True),
        sa.Column("date_end", sa.String(), nullable=True),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("entity", sa.Text(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("device", sa.String(), nullable=True),
        sa.Column("impressions", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Float(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("position", sa.Float(), nullable=True),
        sa.Column("normalized_demand_score", sa.Float(), nullable=True),
        sa.Column("normalized_opportunity_score", sa.Float(), nullable=True),
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trend_signal_id", sa.String(), nullable=True),
        sa.Column("opportunity_id", sa.String(), nullable=True),
        sa.Column("coverage_id", sa.String(), nullable=True),
        sa.Column("published_content_id", sa.String(), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["demand_observation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trend_signal_id"], ["trend_signals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coverage_id"], ["content_coverage.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_content_id"], ["published_content.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_demand_observations_workspace_observed",
        "demand_observations",
        ["workspace_id", "observed_at"],
    )
    op.create_index(
        "idx_demand_observations_provider",
        "demand_observations",
        ["workspace_id", "provider", "source_type"],
    )
    op.create_index("idx_demand_observations_query", "demand_observations", ["workspace_id", "query"])
    op.create_index("idx_demand_observations_page", "demand_observations", ["workspace_id", "page_url"])
    op.create_index(
        "idx_demand_observations_opportunity",
        "demand_observations",
        ["workspace_id", "normalized_opportunity_score"],
    )
    op.create_index("idx_demand_observations_run", "demand_observations", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_demand_observations_run", table_name="demand_observations")
    op.drop_index("idx_demand_observations_opportunity", table_name="demand_observations")
    op.drop_index("idx_demand_observations_page", table_name="demand_observations")
    op.drop_index("idx_demand_observations_query", table_name="demand_observations")
    op.drop_index("idx_demand_observations_provider", table_name="demand_observations")
    op.drop_index("idx_demand_observations_workspace_observed", table_name="demand_observations")
    op.drop_table("demand_observations")
    op.drop_index("idx_demand_observation_runs_provider", table_name="demand_observation_runs")
    op.drop_index("idx_demand_observation_runs_workspace", table_name="demand_observation_runs")
    op.drop_table("demand_observation_runs")
