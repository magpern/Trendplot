"""Workspace WordPress connector settings and job draft fields.

Revision ID: 0018_workspace_wordpress_connector
Revises: 0017_manual_recommendations
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_workspace_wordpress_connector"
down_revision = "0017_manual_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_wordpress_connector",
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("connector_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("wordpress_base_url", sa.Text()),
        sa.Column("trendplot_site_id", sa.String()),
        sa.Column("trendplot_shared_secret", sa.Text()),
        sa.Column("last_connection_status", sa.String()),
        sa.Column("last_connection_checked_at", sa.String()),
        sa.Column("last_connection_error", sa.Text()),
        sa.Column("connector_plugin_version", sa.String()),
        sa.Column("connector_api_version", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("wordpress_post_id", sa.String()))
        batch_op.add_column(sa.Column("wordpress_edit_url", sa.Text()))
        batch_op.add_column(sa.Column("wordpress_public_url", sa.Text()))
        batch_op.add_column(sa.Column("wordpress_status", sa.String()))
        batch_op.add_column(sa.Column("wordpress_draft_created_at", sa.String()))
        batch_op.add_column(sa.Column("wordpress_connector_site_url", sa.Text()))
        batch_op.add_column(sa.Column("wordpress_publish_error", sa.Text()))
        batch_op.add_column(sa.Column("wordpress_publish_attempted_at", sa.String()))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("wordpress_publish_attempted_at")
        batch_op.drop_column("wordpress_publish_error")
        batch_op.drop_column("wordpress_connector_site_url")
        batch_op.drop_column("wordpress_draft_created_at")
        batch_op.drop_column("wordpress_status")
        batch_op.drop_column("wordpress_public_url")
        batch_op.drop_column("wordpress_edit_url")
        batch_op.drop_column("wordpress_post_id")
    op.drop_table("workspace_wordpress_connector")
