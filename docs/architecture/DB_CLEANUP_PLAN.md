# Database cleanup plan (Phase 2)

**Prerequisite:** Full DB backup and row-count export (`scripts/export_legacy_table_counts.py` → `docs/architecture/legacy_table_counts.json`).

**Migration:** [`migrations/versions/0016_drop_legacy_pipeline_tables.py`](../../migrations/versions/0016_drop_legacy_pipeline_tables.py) — `DROP TABLE` in FK-safe order. Downgrade: restore from backup only.

## KEEP

`autopilot_workspaces`, `workspace_connections`, `analysis_jobs`, `analysis_pages`, `analysis_suggestions`, `analysis_intelligence_artifacts`, `site_understanding_snapshots`, `workspace_niche_profiles`, `workspace_content_inventory`, `ai_opportunity_ideation_runs`, `ai_opportunity_ideation_opportunities`, `opportunity_recommendations`, `content_plans`, `content_plan_items`, `analyze_flow_runs`, `jobs`, `artifacts`, `job_logs`, `approval_events`, `connector_events`, `published_content`, `provider_status`, `reassessment_runs` (if still referenced).

## REMOVE (dropped in 0016)

| Tables | Former owner |
|--------|----------------|
| `market_intelligence_runs`, `market_signals`, `market_signal_evidence`, `market_topic_clusters`, `market_opportunity_candidates` | market_intelligence |
| `editorial_generation_runs`, `editorial_opportunity_concepts` | editorial_opportunity |
| `ai_editorial_strategist_runs`, `ai_editorial_strategist_ideas` | ai_editorial_strategist |
| `ai_recommendation_review_runs`, `ai_recommendation_reviews` | ai_recommendation_review |
| `trend_signals`, `trend_discovery_runs`, `trend_discovery_queries` | trends |
| `demand_observation_runs`, `demand_observations` | demand |
| `competitor_snapshots` | competitor steps |
| `content_entities`, `content_clusters`, `content_coverage` | entity/coverage |
| `opportunities`, `opportunity_clusters`, `opportunity_audiences`, `authority_graph_*`, `opportunity_relationships`, `audience_profiles` | opportunity_engine |
| `opportunity_campaigns`, `opportunity_campaign_items` | campaigns |

**Data:** Optional one-time delete from `opportunity_recommendations` where `source_type != 'ai_opportunity_ideation'`.
