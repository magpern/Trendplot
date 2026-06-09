"""workspace content inventory

Revision ID: 0013_workspace_content_inventory
Revises: 0012_analyze_flow_runs
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_workspace_content_inventory"
down_revision = "0012_analyze_flow_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_content_inventory",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("slug", sa.String()),
        sa.Column("content_type", sa.String(), server_default="unknown", nullable=False),
        sa.Column("source", sa.String(), server_default="existing_site", nullable=False),
        sa.Column("wordpress_post_id", sa.String()),
        sa.Column("created_by_trendplot", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("generated_job_id", sa.String()),
        sa.Column("published_at", sa.String()),
        sa.Column("last_seen_at", sa.String(), nullable=False),
        sa.Column("topic_fingerprint", sa.Text()),
        sa.Column("coverage_topics_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workspace_content_inventory_workspace",
        "workspace_content_inventory",
        ["workspace_id"],
    )
    op.create_index(
        "idx_workspace_content_inventory_canonical",
        "workspace_content_inventory",
        ["workspace_id", "canonical_url"],
    )
    op.create_index(
        "idx_workspace_content_inventory_fingerprint",
        "workspace_content_inventory",
        ["workspace_id", "topic_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("idx_workspace_content_inventory_fingerprint", table_name="workspace_content_inventory")
    op.drop_index("idx_workspace_content_inventory_canonical", table_name="workspace_content_inventory")
    op.drop_index("idx_workspace_content_inventory_workspace", table_name="workspace_content_inventory")
    op.drop_table("workspace_content_inventory")
