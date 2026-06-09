"""editorial opportunity concepts phase 1

Revision ID: 0011_editorial_opportunity_concepts
Revises: 0010_market_intelligence
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_editorial_opportunity_concepts"
down_revision = "0010_market_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "editorial_generation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("market_run_id", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String()),
        sa.Column("seeds_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("concepts_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("finalists_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["market_run_id"], ["market_intelligence_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_editorial_generation_runs_workspace", "editorial_generation_runs", ["workspace_id", "created_at"])

    op.create_table(
        "editorial_opportunity_concepts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("seed_candidate_id", sa.String()),
        sa.Column("cluster_id", sa.String()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("audience", sa.Text()),
        sa.Column("intent", sa.String()),
        sa.Column("angle", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("novelty", sa.Float()),
        sa.Column("authority_value", sa.Float()),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("source_signal_ids_json", sa.JSON()),
        sa.Column("target_keyword", sa.Text()),
        sa.Column("action_hint", sa.String(), nullable=False),
        sa.Column("related_content_ids_json", sa.JSON()),
        sa.Column("is_finalist", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["market_topic_clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["editorial_generation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seed_candidate_id"], ["market_opportunity_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_editorial_opportunity_concepts_workspace", "editorial_opportunity_concepts", ["workspace_id", "is_finalist"])
    op.create_index("idx_editorial_opportunity_concepts_seed", "editorial_opportunity_concepts", ["seed_candidate_id"])
    op.create_index("idx_editorial_opportunity_concepts_run", "editorial_opportunity_concepts", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_editorial_opportunity_concepts_run", table_name="editorial_opportunity_concepts")
    op.drop_index("idx_editorial_opportunity_concepts_seed", table_name="editorial_opportunity_concepts")
    op.drop_index("idx_editorial_opportunity_concepts_workspace", table_name="editorial_opportunity_concepts")
    op.drop_table("editorial_opportunity_concepts")
    op.drop_index("idx_editorial_generation_runs_workspace", table_name="editorial_generation_runs")
    op.drop_table("editorial_generation_runs")
