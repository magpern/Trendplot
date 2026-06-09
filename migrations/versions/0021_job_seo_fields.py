"""Job-level SEO metadata fields for Rank Math sync.

Revision ID: 0021_job_seo_fields
Revises: 0020_wordpress_draft_sync_timestamps
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_job_seo_fields"
down_revision = "0020_wordpress_draft_sync_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("seo_title", sa.Text()))
        batch_op.add_column(sa.Column("seo_description", sa.Text()))
        batch_op.add_column(sa.Column("seo_focus_keyword", sa.String()))
        batch_op.add_column(sa.Column("seo_canonical_url", sa.Text()))
        batch_op.add_column(sa.Column("seo_robots", sa.String()))
        batch_op.add_column(sa.Column("seo_schema_type", sa.String()))
        batch_op.add_column(sa.Column("seo_generated_at", sa.String()))
        batch_op.add_column(sa.Column("seo_synced_at", sa.String()))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("seo_synced_at")
        batch_op.drop_column("seo_generated_at")
        batch_op.drop_column("seo_schema_type")
        batch_op.drop_column("seo_robots")
        batch_op.drop_column("seo_canonical_url")
        batch_op.drop_column("seo_focus_keyword")
        batch_op.drop_column("seo_description")
        batch_op.drop_column("seo_title")
