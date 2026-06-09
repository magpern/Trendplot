"""SEO optimization pass metadata on jobs.

Revision ID: 0023_job_seo_optimization
Revises: 0022_job_seo_sync_metadata
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0023_job_seo_optimization"
down_revision = "0022_job_seo_sync_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("recommended_slug", sa.String()))
        batch_op.add_column(sa.Column("seo_manually_edited", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("suggested_featured_image_alt", sa.Text()))
        batch_op.add_column(sa.Column("suggested_inline_image_alt", sa.Text()))
        batch_op.add_column(sa.Column("seo_optimized_at", sa.String()))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("seo_optimized_at")
        batch_op.drop_column("suggested_inline_image_alt")
        batch_op.drop_column("suggested_featured_image_alt")
        batch_op.drop_column("seo_manually_edited")
        batch_op.drop_column("recommended_slug")
