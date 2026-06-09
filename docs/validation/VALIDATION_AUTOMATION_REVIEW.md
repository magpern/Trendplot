# Validation Automation Review

**Date:** 2026-06-01
**Purpose:** Part 3 — assess the efficiency of the validation pipeline; identify bottlenecks, manual steps, and automation opportunities.
**Scope:** Deterministic path only. No AI refinement step is included.

---

## Pipeline overview

To validate a new workspace, the following pipeline must run in order:

```
Step 1: Create workspace            (API call, instant)
Step 2: Website analysis            (crawl + OpenAI LLM call, ~3–10 min)
Step 3: Niche intelligence          (deterministic, runs inside Step 2)
Step 4: Market intelligence         (competitor crawl + deterministic scoring, ~2–5 min)
Step 5: Editorial opportunity gen   (deterministic EOG, <1 min)
Step 6: Opportunity intelligence    (deterministic scoring/ranking, <1 min)
Step 7: Validation export           (script, <1 min)
```

Total wall-clock time per workspace: **~5–15 minutes** (dominated by crawl + OpenAI call in Step 2).

---

## Step-by-step analysis

### Step 1 — Create workspace

**Method:** POST `/api/workspaces` with `website_url`, optional `competitors`, `name`
**Duration:** <1 second
**Manual input required:** website URL, competitor URLs (1–3 recommended)
**Automatable:** Yes — a seed list of URLs can drive batch workspace creation

---

### Step 2 — Website analysis

**Method:** POST `/api/workspaces/{id}/analyze`
**Duration:** 3–10 minutes per workspace
**What it does:**
- Crawls the target site and competitor sites (up to `max_pages_per_site`, default 3)
- Sends crawled content to OpenAI for structured analysis (niche, audiences, opportunities, entities)
- Persists `analysis_pages`, `analysis_suggestions`, `site_understanding_snapshots`

**Dependencies:**
- Live internet access (crawl must succeed)
- OpenAI API key with sufficient quota
- `max_pages_per_site` controls crawl depth (3 is reasonable for validation; higher = better coverage but slower)

**Bottlenecks:**
- OpenAI latency (~20–60 sec per LLM call for website analysis)
- Crawl latency (variable; JS-rendered sites may time out or return thin content)
- Rate-limited or bot-protected sites will produce sparse pages

**Manual steps:**
- Selecting `max_pages_per_site` (default 3 is sufficient for validation)
- Verifying crawl succeeded (check `analysis_pages` count > 0 before proceeding)

**Failure modes to watch:**
- `status = failed` in `analysis_jobs` → restart with same workspace; crawl may have hit a rate limit
- Zero pages scraped → site may have bot protection; use a different candidate
- OpenAI timeout → retry (the job system has retry logic)

---

### Step 3 — Niche intelligence

**Method:** Runs automatically inside `analyze_workspace`
**Duration:** <5 seconds (deterministic)
**Manual input required:** None
**Notes:** Produces `workspace_niche_profiles` row. Confidence will be lower for sparse-content sites (local business). This is expected behavior, not a defect.

---

### Step 4 — Market intelligence

**Method:** Called automatically inside `analyze_workspace` when `MARKET_INTELLIGENCE_ENABLED=true`
**Duration:** 2–5 minutes (competitor crawl + internal scoring)
**What it does:**
- Crawls competitor pages for additional signal
- Produces `market_signals`, `market_topic_clusters`, `market_opportunity_candidates`
- Currently configured: competitor provider only (`MARKET_PROVIDER_COMPETITOR_ENABLED=true`); web/news/YouTube providers are disabled

**Bottlenecks:**
- Competitor crawl latency (same constraints as main crawl)
- If no competitors are specified at workspace creation, this step produces sparse candidates

**Manual steps:**
- Specify 2–3 real competitors at workspace creation time for better candidate coverage

---

### Step 5 — Editorial opportunity generation (EOG)

**Method:** Runs automatically inside `analyze_workspace` → `_refresh_market_intelligence` → calls `EditorialOpportunityService`
**Duration:** <30 seconds (deterministic pipeline, no LLM)
**What it does:**
- Produces `editorial_opportunity_concepts` and `editorial_generation_runs`
- All filters are deterministic: orphan filter, fragment filter, nav-label filter, content-type balancer

**Bottlenecks:** None significant. CPU-bound but fast.

**Manual steps:** None

---

### Step 6 — Opportunity intelligence

**Method:** Runs automatically inside `analyze_workspace` → `refresh_opportunity_intelligence`
**Duration:** <20 seconds (deterministic scoring)
**What it does:**
- Scores and ranks candidates from all sources (analysis, trends, market, editorial)
- Produces `opportunity_recommendations`

**Bottlenecks:** None significant.
**Manual steps:** None

---

### Step 7 — Validation export

**Method:** `python scripts/run_opportunity_quality_validation.py`
**Duration:** <30 seconds
**What it does:**
- Iterates all workspaces in `autopilot_workspaces`
- Exports JSON snapshots and metrics to `docs/validation/runs/{RUN_ID}/`
- Produces `REPORT.md`, `metrics.json`, `top25_analysis.json` per workspace

**Manual steps:**
- Run the script
- Manually review `top25_analysis.json` for human-rated publishable/junk assessment

**Notes:**
- The script already iterates all workspaces — adding more workspaces automatically expands the cohort
- The `--refresh` flag re-runs market intelligence before exporting; not needed for initial validation of new workspaces

---

## Automation opportunities

| Opportunity | Effort | Impact |
|---|---|---|
| Batch workspace creation from a URL list | Low — one script loop | Eliminates per-workspace API call |
| Verify crawl success before proceeding | Low — check `analysis_pages` count | Prevents silent data gaps |
| Automated metrics extraction (already done) | Done — `metrics.json` per workspace | |
| Human review template (publishable/junk rubric per rec) | Low — structured scoring sheet | Standardizes the only remaining manual step |
| Multi-workspace parallel analysis | Medium — the API currently processes one at a time | Would reduce total wall time for 5-workspace cohort |
| Automated re-run on crawl failure | Low — retry existing logic exists | |

---

## Bottleneck summary

| Step | Wall time | Parallelizable | Main constraint |
|---|---|---|---|
| Workspace creation | <1 sec | Yes | None |
| Website analysis | 3–10 min | Not yet (sequential) | Crawl + OpenAI latency |
| Market intelligence | 2–5 min | Not yet | Competitor crawl |
| EOG | <30 sec | N/A | None |
| OI scoring | <20 sec | N/A | None |
| Validation export | <30 sec | N/A | None |
| **Total per workspace** | **~5–15 min** | — | Crawl/LLM |
| **Total for 5 workspaces (sequential)** | **~25–75 min** | — | — |

---

## Estimated runtime for the validation dataset

- 5 workspaces × ~15 min average = **~75 minutes** end-to-end for full onboarding
- Validation export (all workspaces): <5 min additional
- Human review of top-25 per workspace: ~20 min per workspace × 5 = **~100 minutes human time**

**Total elapsed (setup + auto pipeline + human review): ~3–4 hours for a 5-workspace cohort.**

---

## Required manual steps (summary)

1. Choose 5 sites (done — see [VALIDATION_DATASET_PLAN.md](VALIDATION_DATASET_PLAN.md))
2. For each site: identify 2–3 real competitor URLs
3. Create workspace via API (or batch script)
4. Trigger analysis via API
5. Verify analysis completed (`status = analyzed`)
6. Run `python scripts/run_opportunity_quality_validation.py`
7. Open `top25_analysis.json` per workspace; apply human publishable/junk rubric
8. Record results in cross-vertical comparison table

---

## What the current pipeline cannot automate

- **Crawl quality verification**: a site behind Cloudflare or requiring JS rendering may crawl silently but return low-quality pages. A human must check `analysis_pages` content.
- **Human publishable/junk rating**: the automated metrics (`junk_rate`, `market_led_create_share`, `explainability_pass_rate`) are proxies. The actual publishable-rate estimate requires a human to read the top-25 titles and judge them.
- **Competitor selection**: no automated competitor discovery exists. A human must supply 2–3 competitors per workspace.
