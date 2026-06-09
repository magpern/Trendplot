# Workspace Inventory

**Date:** 2026-06-01
**Purpose:** Part 1 — enumerate all workspaces in the system, their analysis status, and whether they are usable for cross-vertical validation.
**Source:** Direct SQLite query against `data/seo_content_worker.db`.

---

## Summary

The database contains **exactly one** autopilot workspace. There are no archived, disabled, or partially configured additional workspaces.

---

## Workspace table

| # | Workspace ID | Name | URL | Status | Mode | Created |
|---|---|---|---|---|---|---|
| 1 | `2a71aaf6-cc69-4663-be7f-7b13e50c3722` | Example Lab | https://www.example.com/ | `analyzed` | `manual_review` | 2026-05-29 |

**No other rows exist in `autopilot_workspaces`.**

---

## Analysis jobs

14 `analysis_jobs` rows exist. All reference one of two URLs:

| URL | Row count | Distinct statuses |
|---|---|---|
| `https://www.example.com/` | 13 | `completed` (11), `failed` (2), `running_crawl` (1) |
| `https://example.com/` | 1 | `completed` |

The `example.com` job has no `workspace_id` (pre-workspace scaffolding run). It is not usable — it is a placeholder crawl with no real niche, no real content, and no opportunity intelligence.

---

## Per-workspace analysis status

| Workspace | Niche | GSC connected | Demand observations | Opportunity recs | Usable for validation |
|---|---|---|---|---|---|
| Example Lab | peptides (research/regulated) | No | 0 | 80 | **Yes — already validated** |

### Supporting data counts (Example Lab only)

| Table | Row count |
|---|---|
| `analysis_pages` | 112 |
| `analysis_suggestions` | 354 |
| `market_intelligence_runs` | 13 |
| `market_signals` | 1,338 |
| `market_topic_clusters` | 805 |
| `market_opportunity_candidates` | 805 |
| `editorial_generation_runs` | 10 |
| `editorial_opportunity_concepts` | 1,119 |
| `opportunity_recommendations` | 80 |
| `content_coverage` | 69 |
| `trend_signals` | 40 |
| `demand_observations` | 0 |
| `site_understanding_snapshots` | 2 |
| `workspace_niche_profiles` | 1 |

---

## Search for hidden or alternate workspaces

The following checks were performed:

- **`autopilot_workspaces`**: 1 row. No `status='disabled'`, `status='archived'`, or `status='setup'` rows exist.
- **`analysis_jobs` without `workspace_id`**: 12 rows — all point to `example.com` or `example.com`. None represent an unlinked real workspace.
- **`site_understanding_snapshots`**: 2 rows, both for workspace `2a71aaf6...` (Example Lab).
- **`workspace_niche_profiles`**: 1 row, Example Lab, primary niche = `peptides`.

**Conclusion: there are no hidden, unlinked, or unanalyzed workspaces. The database is a single-workspace system.**

---

## Usability for validation

| Workspace | Usable | Reason |
|---|---|---|
| Example Lab | Yes | Fully analyzed, 80 recs, quality validated across 4 passes |
| example.com | No | Placeholder, no real website content |

**No additional workspaces exist. Multi-vertical validation requires onboarding new real websites.**
