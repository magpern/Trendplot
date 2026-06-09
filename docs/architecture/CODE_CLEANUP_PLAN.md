# Code cleanup plan

**Phase 2 (complete):** full removal of legacy analyze pipeline — not optional retention.

See [CLEANUP_PHASE_2_EXECUTION_PLAN.md](CLEANUP_PHASE_2_EXECUTION_PLAN.md), [CONFIG_CLEANUP_PLAN.md](CONFIG_CLEANUP_PLAN.md), [DB_CLEANUP_PLAN.md](DB_CLEANUP_PLAN.md), [UI_CLEANUP_PLAN.md](UI_CLEANUP_PLAN.md).

## Product gate

`AI_OPPORTUNITY_IDEATION_ENABLED=true` → `Settings.is_ai_ideation_only_mode`. **Removed:** `AI_OPPORTUNITY_IDEATION_SHORT_CIRCUIT`, `_analyze_workspace_full`, dual flow builders.

## Module matrix (Phase 2)

| Path | Action |
|------|--------|
| `app/ai_opportunity_ideation/` | **KEEP** |
| `app/catalog/` (+ `filters.py` moved from market_intelligence) | **KEEP** |
| `app/website_analysis.py`, `app/sitemap_discovery.py` | **KEEP** (no opportunity engine in analyze) |
| `app/niche_intelligence/`, `app/planning/calendar.py` | **KEEP** |
| `app/opportunities/` (verticals/schemas only) | **KEEP** — not the dropped DB `opportunities` table |
| `app/autopilot/service.py` | **KEEP** — product analyze only |
| `app/recommendations/explainability.py` | **KEEP** (moved from OI) |
| `app/market_intelligence/` (except filters → catalog) | **REMOVE** |
| `app/editorial_opportunity/`, `app/opportunity_intelligence/` | **REMOVE** |
| `app/ai_editorial_strategist/`, `app/ai_recommendation_reviewer/` | **REMOVE** |
| `app/entity_relevance/`, `app/trends/`, `app/demand/` | **REMOVE** |
| `app/competitor_discovery*.py` | **REMOVE** |
| `app/ai_opportunity_ideation/bridge.py` | **REMOVE** |
| Legacy analyze steps in `analyze_flow.py` | **REMOVE** |

Legacy HTTP routes return **410** via `_legacy_pipeline_removed()` in `app/api/routes.py`.
