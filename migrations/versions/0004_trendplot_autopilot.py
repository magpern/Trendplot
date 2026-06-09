"""add trendplot autopilot state

Revision ID: 0004_trendplot_autopilot
Revises: 0003_external_research_evidence
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_trendplot_autopilot"
down_revision = "0003_external_research_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("workspace_id", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("content_plan_item_id", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("origin_type", sa.String(), nullable=True))
    op.add_column("analysis_jobs", sa.Column("workspace_id", sa.String(), nullable=True))

    op.create_table(
        "autopilot_workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="manual_review"),
        sa.Column("status", sa.String(), nullable=False, server_default="setup"),
        sa.Column("cadence", sa.String(), nullable=False, server_default="weekly"),
        sa.Column("user_context", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.JSON(), nullable=True),
        sa.Column("last_analysis_job_id", sa.String(), nullable=True),
        sa.Column("last_content_plan_id", sa.String(), nullable=True),
        sa.Column("last_reassessment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_autopilot_workspaces_status", "autopilot_workspaces", ["status"])
    op.create_index("idx_autopilot_workspaces_url", "autopilot_workspaces", ["website_url"])

    op.create_table(
        "workspace_connections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("connection_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="not_connected"),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("last_checked_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_workspace_connections_workspace", "workspace_connections", ["workspace_id"])
    op.create_index("idx_workspace_connections_type", "workspace_connections", ["connection_type"])

    op.create_table(
        "site_understanding_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detected_niche", sa.Text(), nullable=True),
        sa.Column("niche_confidence", sa.Float(), nullable=True),
        sa.Column("products_services_json", sa.JSON(), nullable=True),
        sa.Column("audiences_json", sa.JSON(), nullable=True),
        sa.Column("competitors_json", sa.JSON(), nullable=True),
        sa.Column("brand_voice_json", sa.JSON(), nullable=True),
        sa.Column("trust_topics_json", sa.JSON(), nullable=True),
        sa.Column("content_gaps_json", sa.JSON(), nullable=True),
        sa.Column("vertical_detection_json", sa.JSON(), nullable=True),
        sa.Column("source_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_site_understanding_workspace", "site_understanding_snapshots", ["workspace_id"])
    op.create_index("idx_site_understanding_analysis", "site_understanding_snapshots", ["analysis_job_id"])

    op.create_table(
        "competitor_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("competitor_url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("topics_json", sa.JSON(), nullable=True),
        sa.Column("products_services_json", sa.JSON(), nullable=True),
        sa.Column("content_formats_json", sa.JSON(), nullable=True),
        sa.Column("gap_notes_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_competitor_snapshots_workspace", "competitor_snapshots", ["workspace_id"])

    op.create_table(
        "trend_signals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("trend_topic", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_provider", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("trend_velocity", sa.Float(), nullable=True),
        sa.Column("recommended_format", sa.String(), nullable=True),
        sa.Column("evergreen_classification", sa.String(), nullable=True),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("content_opportunity_id", sa.String(), nullable=True),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence_items_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_trend_signals_workspace", "trend_signals", ["workspace_id"])
    op.create_index("idx_trend_signals_topic", "trend_signals", ["trend_topic"])

    op.create_table(
        "content_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(), nullable=False),
        sa.Column("publish_policy", sa.String(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_content_plans_workspace", "content_plans", ["workspace_id"])

    op.create_table(
        "content_plan_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("content_plan_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("opportunity_id", sa.String(), nullable=True),
        sa.Column("trend_signal_id", sa.String(), nullable=True),
        sa.Column("generated_job_id", sa.String(), nullable=True),
        sa.Column("published_content_id", sa.String(), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="planned"),
        sa.Column("content_role", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("target_keyword", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("policy", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_content_plan_items_plan", "content_plan_items", ["content_plan_id"])
    op.create_index("idx_content_plan_items_workspace_state", "content_plan_items", ["workspace_id", "state"])
    op.create_index("idx_content_plan_items_scheduled", "content_plan_items", ["scheduled_for"])

    op.create_table(
        "published_content",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("content_plan_item_id", sa.String(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False, server_default="wordpress"),
        sa.Column("clusters_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.String(), nullable=True),
        sa.Column("refresh_after", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_published_content_workspace", "published_content", ["workspace_id"])
    op.create_index("idx_published_content_external", "published_content", ["external_id"])

    op.create_table(
        "reassessment_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strategy_adjustments_json", sa.JSON(), nullable=True),
        sa.Column("new_opportunities_json", sa.JSON(), nullable=True),
        sa.Column("retired_opportunities_json", sa.JSON(), nullable=True),
        sa.Column("recommended_refreshes_json", sa.JSON(), nullable=True),
        sa.Column("calendar_diff_json", sa.JSON(), nullable=True),
        sa.Column("provider_status_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_reassessment_runs_workspace", "reassessment_runs", ["workspace_id"])

    op.create_table(
        "provider_status",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_provider_status_workspace", "provider_status", ["workspace_id"])
    op.create_index("idx_provider_status_provider", "provider_status", ["provider_name", "provider_type"])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("content_plan_item_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="user"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_approval_events_workspace", "approval_events", ["workspace_id"])
    op.create_index("idx_approval_events_item", "approval_events", ["content_plan_item_id"])


def downgrade() -> None:
    op.drop_index("idx_approval_events_item", table_name="approval_events")
    op.drop_index("idx_approval_events_workspace", table_name="approval_events")
    op.drop_table("approval_events")
    op.drop_index("idx_provider_status_provider", table_name="provider_status")
    op.drop_index("idx_provider_status_workspace", table_name="provider_status")
    op.drop_table("provider_status")
    op.drop_index("idx_reassessment_runs_workspace", table_name="reassessment_runs")
    op.drop_table("reassessment_runs")
    op.drop_index("idx_published_content_external", table_name="published_content")
    op.drop_index("idx_published_content_workspace", table_name="published_content")
    op.drop_table("published_content")
    op.drop_index("idx_content_plan_items_scheduled", table_name="content_plan_items")
    op.drop_index("idx_content_plan_items_workspace_state", table_name="content_plan_items")
    op.drop_index("idx_content_plan_items_plan", table_name="content_plan_items")
    op.drop_table("content_plan_items")
    op.drop_index("idx_content_plans_workspace", table_name="content_plans")
    op.drop_table("content_plans")
    op.drop_index("idx_trend_signals_topic", table_name="trend_signals")
    op.drop_index("idx_trend_signals_workspace", table_name="trend_signals")
    op.drop_table("trend_signals")
    op.drop_index("idx_competitor_snapshots_workspace", table_name="competitor_snapshots")
    op.drop_table("competitor_snapshots")
    op.drop_index("idx_site_understanding_analysis", table_name="site_understanding_snapshots")
    op.drop_index("idx_site_understanding_workspace", table_name="site_understanding_snapshots")
    op.drop_table("site_understanding_snapshots")
    op.drop_index("idx_workspace_connections_type", table_name="workspace_connections")
    op.drop_index("idx_workspace_connections_workspace", table_name="workspace_connections")
    op.drop_table("workspace_connections")
    op.drop_index("idx_autopilot_workspaces_url", table_name="autopilot_workspaces")
    op.drop_index("idx_autopilot_workspaces_status", table_name="autopilot_workspaces")
    op.drop_table("autopilot_workspaces")
    op.drop_column("analysis_jobs", "workspace_id")
    op.drop_column("jobs", "origin_type")
    op.drop_column("jobs", "content_plan_item_id")
    op.drop_column("jobs", "workspace_id")
