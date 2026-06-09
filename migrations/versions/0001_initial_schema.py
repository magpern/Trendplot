"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-27 20:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("request_input", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_attempt_at", sa.String(), nullable=True),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=False),
        sa.Column("competitor_urls_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("max_pages_per_site", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("raw_response_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analysis_jobs_created_at", "analysis_jobs", ["created_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("content_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=True),
        sa.Column("token_output", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_artifacts_job_type", "artifacts", ["job_id", "artifact_type"])

    op.create_table(
        "job_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_logs_job_id", "job_logs", ["job_id"])

    op.create_table(
        "analysis_pages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("h1_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("h2_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("extracted_links_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("body_sample", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analysis_pages_job_id", "analysis_pages", ["analysis_job_id"])

    op.create_table(
        "analysis_suggestions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("target_keyword", sa.Text(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("generated_job_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analysis_suggestions_job_id", "analysis_suggestions", ["analysis_job_id"])


def downgrade() -> None:
    op.drop_index("idx_analysis_suggestions_job_id", table_name="analysis_suggestions")
    op.drop_table("analysis_suggestions")
    op.drop_index("idx_analysis_pages_job_id", table_name="analysis_pages")
    op.drop_table("analysis_pages")
    op.drop_index("idx_job_logs_job_id", table_name="job_logs")
    op.drop_table("job_logs")
    op.drop_index("idx_artifacts_job_type", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("idx_analysis_jobs_created_at", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_table("jobs")
