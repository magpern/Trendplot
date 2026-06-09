"""add workspace niche profiles

Revision ID: 0007_workspace_niche_profiles
Revises: 0006_trend_intelligence_v1
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_workspace_niche_profiles"
down_revision = "0006_trend_intelligence_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_niche_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("primary_niche", sa.Text(), nullable=True),
        sa.Column("secondary_niches_json", sa.JSON(), nullable=True),
        sa.Column("known_entities_json", sa.JSON(), nullable=True),
        sa.Column("known_products_json", sa.JSON(), nullable=True),
        sa.Column("known_categories_json", sa.JSON(), nullable=True),
        sa.Column("known_audiences_json", sa.JSON(), nullable=True),
        sa.Column("common_terminology_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sources_json", sa.JSON(), nullable=True),
        sa.Column("last_updated", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_workspace_niche_profiles_workspace", "workspace_niche_profiles", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_workspace_niche_profiles_workspace", table_name="workspace_niche_profiles")
    op.drop_table("workspace_niche_profiles")
