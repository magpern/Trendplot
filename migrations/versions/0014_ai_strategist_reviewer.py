"""AI editorial strategist and recommendation reviewer tables.

Revision ID: 0014_ai_strategist_reviewer
Revises: 0013_workspace_content_inventory
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_ai_strategist_reviewer"
down_revision = "0013_workspace_content_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_editorial_strategist_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String()),
        sa.Column("ideas_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_editorial_strategist_runs_workspace",
        "ai_editorial_strategist_runs",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "ai_editorial_strategist_ideas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("idea_type", sa.String(), nullable=False),
        sa.Column("entity", sa.Text()),
        sa.Column("rationale", sa.Text()),
        sa.Column("priority", sa.String()),
        sa.Column("target_keyword", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_editorial_strategist_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_editorial_strategist_ideas_workspace", "ai_editorial_strategist_ideas", ["workspace_id"])
    op.create_index("idx_ai_editorial_strategist_ideas_run", "ai_editorial_strategist_ideas", ["run_id"])

    op.create_table(
        "ai_recommendation_review_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String()),
        sa.Column("items_reviewed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_recommendation_review_runs_workspace",
        "ai_recommendation_review_runs",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "ai_recommendation_reviews",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("recommendation_id", sa.String(), nullable=False),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("business_alignment_score", sa.Float()),
        sa.Column("niche_alignment_score", sa.Float()),
        sa.Column("content_usefulness_score", sa.Float()),
        sa.Column("recommended_action", sa.String(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_recommendation_review_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_recommendation_reviews_run", "ai_recommendation_reviews", ["run_id"])
    op.create_index("idx_ai_recommendation_reviews_recommendation", "ai_recommendation_reviews", ["recommendation_id"])


def downgrade() -> None:
    op.drop_index("idx_ai_recommendation_reviews_recommendation", table_name="ai_recommendation_reviews")
    op.drop_index("idx_ai_recommendation_reviews_run", table_name="ai_recommendation_reviews")
    op.drop_table("ai_recommendation_reviews")
    op.drop_index("idx_ai_recommendation_review_runs_workspace", table_name="ai_recommendation_review_runs")
    op.drop_table("ai_recommendation_review_runs")
    op.drop_index("idx_ai_editorial_strategist_ideas_run", table_name="ai_editorial_strategist_ideas")
    op.drop_index("idx_ai_editorial_strategist_ideas_workspace", table_name="ai_editorial_strategist_ideas")
    op.drop_table("ai_editorial_strategist_ideas")
    op.drop_index("idx_ai_editorial_strategist_runs_workspace", table_name="ai_editorial_strategist_runs")
    op.drop_table("ai_editorial_strategist_runs")
