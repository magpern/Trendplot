"""add trendplot connector events

Revision ID: 0005_trendplot_connector_events
Revises: 0004_trendplot_autopilot
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_trendplot_connector_events"
down_revision = "0004_trendplot_autopilot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("post_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_connector_events_site_event", "connector_events", ["site_id", "event_id"])
    op.create_index("idx_connector_events_workspace", "connector_events", ["workspace_id"])
    op.create_index("idx_connector_events_type", "connector_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_connector_events_type", table_name="connector_events")
    op.drop_index("idx_connector_events_workspace", table_name="connector_events")
    op.drop_index("idx_connector_events_site_event", table_name="connector_events")
    op.drop_table("connector_events")
