"""WordPress connector staging/production environments.

Revision ID: 0019_wordpress_connector_environments
Revises: 0018_workspace_wordpress_connector
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_wordpress_connector_environments"
down_revision = "0018_workspace_wordpress_connector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workspace_wordpress_connector") as batch_op:
        batch_op.add_column(
            sa.Column("active_environment", sa.String(), server_default="staging", nullable=False),
        )
        batch_op.add_column(sa.Column("environments_json", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("workspace_wordpress_connector") as batch_op:
        batch_op.drop_column("environments_json")
        batch_op.drop_column("active_environment")
