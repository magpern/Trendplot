"""WordPress draft update sync timestamps on jobs.

Revision ID: 0020_wordpress_draft_sync_timestamps
Revises: 0019_wordpress_connector_environments
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_wordpress_draft_sync_timestamps"
down_revision = "0019_wordpress_connector_environments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("wordpress_draft_updated_at", sa.String()))
        batch_op.add_column(sa.Column("last_wordpress_sync_at", sa.String()))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("last_wordpress_sync_at")
        batch_op.drop_column("wordpress_draft_updated_at")
