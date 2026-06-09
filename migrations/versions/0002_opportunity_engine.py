"""opportunity engine

Revision ID: 0002_opportunity_engine
Revises: 0001_initial_schema
Create Date: 2026-05-28 12:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_opportunity_engine"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_pages", sa.Column("h3_json", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("analysis_pages", sa.Column("navigation_links_json", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("analysis_pages", sa.Column("questions_json", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("analysis_pages", sa.Column("entities_json", sa.JSON(none_as_null=True), nullable=True))

    op.create_table(
        "audience_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audience_type", sa.String(), nullable=True),
        sa.Column("expertise_level", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("commercial_intent", sa.Float(), nullable=True),
        sa.Column("research_intent", sa.Float(), nullable=True),
        sa.Column("concerns_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("recurring_questions_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("preferred_content_types_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("authority_topics_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("related_entities_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("related_clusters_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("source_signals_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("manual_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'inferred'"), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audience_profiles_job", "audience_profiles", ["analysis_job_id"])

    op.create_table(
        "opportunity_clusters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_cluster_id", sa.String(), nullable=True),
        sa.Column("entities_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("source_terms_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("authority_value", sa.Float(), nullable=True),
        sa.Column("seo_value", sa.Float(), nullable=True),
        sa.Column("editorial_value", sa.Float(), nullable=True),
        sa.Column("geo_value", sa.Float(), nullable=True),
        sa.Column("opportunity_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("primary_audiences_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("audience_overlap_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("pillar_candidate", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("semantic_authority_role", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunity_clusters_job", "opportunity_clusters", ["analysis_job_id"])

    op.create_table(
        "authority_graph_nodes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_signals_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_authority_graph_nodes_job", "authority_graph_nodes", ["analysis_job_id"])
    op.create_index("idx_authority_graph_nodes_type", "authority_graph_nodes", ["node_type"])

    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("cluster_id", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("target_keyword", sa.Text(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("opportunity_type", sa.String(), nullable=True),
        sa.Column("search_intent", sa.String(), nullable=True),
        sa.Column("funnel_stage", sa.String(), nullable=True),
        sa.Column("content_role", sa.String(), nullable=True),
        sa.Column("primary_audience_id", sa.String(), nullable=True),
        sa.Column("secondary_audience_ids_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("audience_rationale", sa.Text(), nullable=True),
        sa.Column("expertise_level", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("scores_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("related_products_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("related_keywords_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("related_entities_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("authority_graph_node_ids_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("relationship_ids_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("competitor_references_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("suggested_article_length", sa.Integer(), nullable=True),
        sa.Column("suggested_structure_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("suggested_media_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("suggested_internal_links_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("cta_strategy", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'suggested'"), nullable=False),
        sa.Column("generated_job_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["opportunity_clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_audience_id"], ["audience_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunities_job", "opportunities", ["analysis_job_id"])
    op.create_index("idx_opportunities_cluster", "opportunities", ["cluster_id"])
    op.create_index("idx_opportunities_primary_audience", "opportunities", ["primary_audience_id"])
    op.create_index("idx_opportunities_type_status", "opportunities", ["opportunity_type", "status"])

    op.create_table(
        "authority_graph_edges",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("source_node_id", sa.String(), nullable=False),
        sa.Column("target_node_id", sa.String(), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["authority_graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["authority_graph_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_authority_graph_edges_job", "authority_graph_edges", ["analysis_job_id"])
    op.create_index("idx_authority_graph_edges_source", "authority_graph_edges", ["source_node_id"])

    op.create_table(
        "opportunity_audiences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("opportunity_id", sa.String(), nullable=False),
        sa.Column("audience_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_id"], ["audience_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunity_audiences_opportunity", "opportunity_audiences", ["opportunity_id"])
    op.create_index("idx_opportunity_audiences_audience", "opportunity_audiences", ["audience_id"])

    op.create_table(
        "opportunity_relationships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=False),
        sa.Column("child_id", sa.String(), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunity_relationships_parent", "opportunity_relationships", ["parent_id"])
    op.create_index("idx_opportunity_relationships_child", "opportunity_relationships", ["child_id"])

    op.create_table(
        "opportunity_campaigns",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("audience_ids_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("cadence", sa.String(), nullable=True),
        sa.Column("publish_policy", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("plan_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunity_campaigns_job", "opportunity_campaigns", ["analysis_job_id"])

    op.create_table(
        "opportunity_campaign_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("opportunity_id", sa.String(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["opportunity_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_opportunity_campaign_items_campaign", "opportunity_campaign_items", ["campaign_id"])

    op.create_table(
        "analysis_intelligence_artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("analysis_job_id", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("content_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_analysis_intelligence_job_type",
        "analysis_intelligence_artifacts",
        ["analysis_job_id", "artifact_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_analysis_intelligence_job_type", table_name="analysis_intelligence_artifacts")
    op.drop_table("analysis_intelligence_artifacts")
    op.drop_index("idx_opportunity_campaign_items_campaign", table_name="opportunity_campaign_items")
    op.drop_table("opportunity_campaign_items")
    op.drop_index("idx_opportunity_campaigns_job", table_name="opportunity_campaigns")
    op.drop_table("opportunity_campaigns")
    op.drop_index("idx_opportunity_relationships_child", table_name="opportunity_relationships")
    op.drop_index("idx_opportunity_relationships_parent", table_name="opportunity_relationships")
    op.drop_table("opportunity_relationships")
    op.drop_index("idx_opportunity_audiences_audience", table_name="opportunity_audiences")
    op.drop_index("idx_opportunity_audiences_opportunity", table_name="opportunity_audiences")
    op.drop_table("opportunity_audiences")
    op.drop_index("idx_authority_graph_edges_source", table_name="authority_graph_edges")
    op.drop_index("idx_authority_graph_edges_job", table_name="authority_graph_edges")
    op.drop_table("authority_graph_edges")
    op.drop_index("idx_opportunities_type_status", table_name="opportunities")
    op.drop_index("idx_opportunities_primary_audience", table_name="opportunities")
    op.drop_index("idx_opportunities_cluster", table_name="opportunities")
    op.drop_index("idx_opportunities_job", table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_index("idx_authority_graph_nodes_type", table_name="authority_graph_nodes")
    op.drop_index("idx_authority_graph_nodes_job", table_name="authority_graph_nodes")
    op.drop_table("authority_graph_nodes")
    op.drop_index("idx_opportunity_clusters_job", table_name="opportunity_clusters")
    op.drop_table("opportunity_clusters")
    op.drop_index("idx_audience_profiles_job", table_name="audience_profiles")
    op.drop_table("audience_profiles")
    op.drop_column("analysis_pages", "entities_json")
    op.drop_column("analysis_pages", "questions_json")
    op.drop_column("analysis_pages", "navigation_links_json")
    op.drop_column("analysis_pages", "h3_json")
