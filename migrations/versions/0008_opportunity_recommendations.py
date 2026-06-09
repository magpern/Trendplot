"""add opportunity recommendations

Revision ID: 0008_opportunity_recommendations
Revises: 0007_workspace_niche_profiles
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_opportunity_recommendations"
down_revision = "0007_workspace_niche_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_recommendations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("target_keyword", sa.Text(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("business_relevance", sa.Float(), nullable=True),
        sa.Column("niche_relevance", sa.Float(), nullable=True),
        sa.Column("trend_relevance", sa.Float(), nullable=True),
        sa.Column("coverage_gap", sa.Float(), nullable=True),
        sa.Column("freshness", sa.Float(), nullable=True),
        sa.Column("audience_relevance", sa.Float(), nullable=True),
        sa.Column("competitor_gap", sa.Float(), nullable=True),
        sa.Column("cannibalization_risk", sa.Float(), nullable=True),
        sa.Column("reasons_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("related_opportunity_id", sa.String(), nullable=True),
        sa.Column("related_content_id", sa.String(), nullable=True),
        sa.Column("trend_signal_id", sa.String(), nullable=True),
        sa.Column("coverage_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_opportunity_recommendations_workspace", "opportunity_recommendations", ["workspace_id"])
    op.create_index("idx_opportunity_recommendations_action", "opportunity_recommendations", ["workspace_id", "action", "priority"])
    op.create_index("idx_opportunity_recommendations_status", "opportunity_recommendations", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_opportunity_recommendations_status", table_name="opportunity_recommendations")
    op.drop_index("idx_opportunity_recommendations_action", table_name="opportunity_recommendations")
    op.drop_index("idx_opportunity_recommendations_workspace", table_name="opportunity_recommendations")
    op.drop_table("opportunity_recommendations")
