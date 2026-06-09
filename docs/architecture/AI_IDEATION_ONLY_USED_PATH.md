# Product analyze path (AI ideation)

**Only path after Phase 2.** No hidden legacy steps or short-circuit flag.

## Flow

```text
workspace_setup → sitemap_discovery → website_crawl → website_analysis
→ niche_intelligence → ai_opportunity_ideation → opportunity_ranking
→ content_calendar → draft_generation → wordpress_upload
```

## Services

| Step | Module |
|------|--------|
| Workspace | `app/autopilot/service.py` |
| Sitemap / crawl | `app/sitemap_discovery.py`, crawl budget |
| Website analysis | `app/website_analysis.py` (no opportunity engine seed) |
| Niche | `app/niche_intelligence/` |
| Ideation | `app/ai_opportunity_ideation/` |
| Recommendations | `_persist_ideation_recommendations` in autopilot |
| Calendar / draft / WP | `app/planning/calendar.py`, `app/services/jobs.py`, WordPress connector |

## Tables (active)

`autopilot_workspaces`, `analysis_*`, `site_understanding_snapshots`, `workspace_niche_profiles`, `workspace_content_inventory`, `ai_opportunity_ideation_*`, `opportunity_recommendations`, `content_plans`, `analyze_flow_runs`, `jobs`, `artifacts`.

## Config

`AI_OPPORTUNITY_IDEATION_ENABLED=true` — see [CONFIG_CLEANUP_PLAN.md](CONFIG_CLEANUP_PLAN.md).

## UI keys

Same 10 step keys as flow; `opportunity_ranking` labeled **Recommendations**. Partial reruns: `recommendations`, `schedule`, `full` only.

## Draft

After analyze: operator selects recommendation or calendar item → `draft_generation` → optional `wordpress_upload`.
