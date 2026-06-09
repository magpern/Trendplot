"""analyze flow run persistence

Revision ID: 0012_analyze_flow_runs
Revises: 0011_editorial_opportunity_concepts
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_analyze_flow_runs"
down_revision = "0011_editorial_opportunity_concepts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyze_flow_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("parent_run_id", sa.String(), nullable=True),
        sa.Column("rerun_type", sa.String(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=False),
        sa.Column("run_label", sa.Text(), nullable=True),
        sa.Column("overall_status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["autopilot_workspaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analyze_flow_runs_created", "analyze_flow_runs", ["created_at"])
    op.create_index("idx_analyze_flow_runs_workspace", "analyze_flow_runs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_analyze_flow_runs_workspace", table_name="analyze_flow_runs")
    op.drop_index("idx_analyze_flow_runs_created", table_name="analyze_flow_runs")
    op.drop_table("analyze_flow_runs")
