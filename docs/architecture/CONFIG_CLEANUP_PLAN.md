# Config cleanup plan (Phase 2)

**Policy:** Two classes only — `KEEP` (product path) and `REMOVE` (legacy full pipeline). No `OPTIONAL` retention.

## Product gate

- `AI_OPPORTUNITY_IDEATION_ENABLED=true` (default) — sole recommendation pipeline gate.
- `Settings.is_ai_ideation_only_mode` ≡ `ai_opportunity_ideation_enabled`.
- **Removed:** `AI_OPPORTUNITY_IDEATION_SHORT_CIRCUIT` and all full-pipeline flags.

## REMOVE (deleted from `app/config.py`, `.env.example`, `.env`)

| Group | Examples |
|-------|----------|
| Short-circuit / dual mode | `AI_OPPORTUNITY_IDEATION_SHORT_CIRCUIT` |
| Market intelligence | `MARKET_*`, `MARKET_INTELLIGENCE_ENABLED` |
| Editorial generator | `EDITORIAL_GENERATOR_*` |
| Entity relevance | `ENTITY_RELEVANCE_*` |
| Strategist | `AI_EDITORIAL_STRATEGIST_*` |
| Reviewer | `AI_RECOMMENDATION_REVIEW_*`, `RECOMMENDATION_MIN_*` |
| Opportunity intelligence | `OPPORTUNITY_INTELLIGENCE_ENABLED` |
| Competitors | `COMPETITOR_*` |
| Trends / demand | `TREND_*`, `DEMAND_*`, `ENABLE_TREND_RESEARCH`, `TREND_REFRESH_INTERVAL_DAYS` |
| Publishing memory | `PUBLISHING_MEMORY_*`, `COVERAGE_*`, `CANNIBALIZATION_*` |
| Seed opportunities | `WEBSITE_ANALYSIS_MAX_SEED_OPPORTUNITIES` |

## KEEP (representative)

`DATABASE_*`, `OPENAI_*`, crawl/sitemap (`MAX_PAGES_PER_SITE`, `SITEMAP_*`, `CRAWL_*`), `NICHE_INTELLIGENCE_ENABLED`, `AI_OPPORTUNITY_IDEATION_*` (except short-circuit), WordPress/publish/safety, `CONTENT_PLAN_HORIZON_DAYS`, article quality flags, `AUTOPILOT_*`, `PROMPT_*`, `ENABLE_EXTERNAL_RESEARCH` (website analysis enrichment), infra/logging.

## `.env.example` sections (after cleanup)

1. Core / database  
2. OpenAI (tiered routing)  
3. Crawl, niche, AI ideation  
4. WordPress and publishing safety  

See [`.env.example`](../../.env.example) for the canonical list.
