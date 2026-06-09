# UI cleanup plan (Phase 2)

## Analyze steps (10 only)

`workspace_setup` → `sitemap_discovery` → `website_crawl` → `website_analysis` → `niche_intelligence` → `ai_opportunity_ideation` → `opportunity_ranking` (label: **Recommendations**) → `content_calendar` → `draft_generation` → `wordpress_upload`

**Removed from UI and flow:** `competitor_discovery`, `competitor_analysis`, `market_intelligence`, `entity_relevance`, `editorial_opportunity`, `ai_editorial_strategist`, `ai_recommendation_review`.

## Rerun actions

| Action | Partial rerun type |
|--------|-------------------|
| Re-run AI recommendations | `recommendations` |
| Re-generate schedule | `schedule` |
| Start full re-analysis | `full` |

**Removed:** competitor discovery/analysis reruns, legacy recommendation keys.

## Diagnostics

- No `ideation_short_circuit` banner or hidden-step allowlists.
- `visibleAnalyzeSteps` shows all product steps.
- Persisted runs: unknown legacy step keys stripped on load (read-only compat).

## Files

- [`app/analyze_ui.py`](../../app/analyze_ui.py) — Analyze Website page  
- [`app/analyze_flow.py`](../../app/analyze_flow.py) — step definitions and summaries  
