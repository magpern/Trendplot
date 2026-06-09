"""SEO sync error and optional Rank Math score on jobs.

Revision ID: 0022_job_seo_sync_metadata
Revises: 0021_job_seo_fields
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_job_seo_sync_metadata"
down_revision = "0021_job_seo_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("seo_last_error", sa.Text()))
        batch_op.add_column(sa.Column("rank_math_score", sa.Float()))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("rank_math_score")
        batch_op.drop_column("seo_last_error")
