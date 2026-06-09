"""AI opportunity ideation tables.

Revision ID: 0015_ai_opportunity_ideation
Revises: 0014_ai_strategist_reviewer
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_ai_opportunity_ideation"
down_revision = "0014_ai_strategist_reviewer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_opportunity_ideation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String()),
        sa.Column("opportunities_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_opportunity_ideation_runs_workspace",
        "ai_opportunity_ideation_runs",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "ai_opportunity_ideation_opportunities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("search_intent", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("recommendation_type", sa.String(), server_default="create", nullable=False),
        sa.Column("related_products_json", sa.JSON()),
        sa.Column("related_topics_json", sa.JSON()),
        sa.Column("target_audience", sa.Text()),
        sa.Column("priority_reason", sa.Text()),
        sa.Column("safety_notes_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_opportunity_ideation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_opportunity_ideation_opportunities_workspace",
        "ai_opportunity_ideation_opportunities",
        ["workspace_id"],
    )
    op.create_index(
        "idx_ai_opportunity_ideation_opportunities_run",
        "ai_opportunity_ideation_opportunities",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_ai_opportunity_ideation_opportunities_run", table_name="ai_opportunity_ideation_opportunities")
    op.drop_index(
        "idx_ai_opportunity_ideation_opportunities_workspace",
        table_name="ai_opportunity_ideation_opportunities",
    )
    op.drop_table("ai_opportunity_ideation_opportunities")
    op.drop_index("idx_ai_opportunity_ideation_runs_workspace", table_name="ai_opportunity_ideation_runs")
    op.drop_table("ai_opportunity_ideation_runs")
