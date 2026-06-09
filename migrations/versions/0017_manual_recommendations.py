"""Manual recommendations table.

Revision ID: 0017_manual_recommendations
Revises: 0016_drop_legacy_pipeline
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_manual_recommendations"
down_revision = "0016_drop_legacy_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_recommendations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), server_default="manual", nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw_headline", sa.Text(), nullable=False),
        sa.Column("raw_notes", sa.Text()),
        sa.Column("enhanced_headline", sa.Text()),
        sa.Column("abstract", sa.Text()),
        sa.Column("search_intent", sa.String()),
        sa.Column("content_type", sa.String()),
        sa.Column("recommendation_type", sa.String(), server_default="create", nullable=False),
        sa.Column("related_products_json", sa.JSON()),
        sa.Column("related_topics_json", sa.JSON()),
        sa.Column("target_audience", sa.Text()),
        sa.Column("priority_reason", sa.Text()),
        sa.Column("safety_notes_json", sa.JSON()),
        sa.Column("enrichment_json", sa.JSON()),
        sa.Column("duplicate_warnings_json", sa.JSON()),
        sa.Column("recommendation_id", sa.String()),
        sa.Column("created_by", sa.String()),
        sa.Column("ai_enriched_at", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_manual_recommendations_workspace",
        "manual_recommendations",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_manual_recommendations_workspace", table_name="manual_recommendations")
    op.drop_table("manual_recommendations")
