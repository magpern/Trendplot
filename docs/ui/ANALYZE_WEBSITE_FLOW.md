# Analyze Website Flow

## User Flow

The operator-facing Analyze Website view is available at:

```text
/app/analyze
```

The flow is intentionally simple:

1. Enter a website URL.
2. Optionally enter a workspace name, competitors, target market/language, max pages, and niche notes.
3. Keep the default publishing mode as manual review, or choose a gated publishing intent.
4. Press Analyze.
5. Watch step-by-step progress.
6. Review warnings, recommendations, and the proposed schedule.
7. Select a recommendation or schedule item to generate a draft.
8. Upload a WordPress draft only through an explicit operator action.

No low-level flags, model names, thresholds, cache TTLs, or Phase 2A tuning controls are exposed.

## Backend Steps

The UI starts a run through:

```text
POST /app/analyze/runs
GET /app/analyze/runs/{job_id}
GET /app/analyze/runs/recent
POST /app/analyze/runs/{parent_job_id}/rerun
```

Runs are persisted in `analyze_flow_runs` (summary + step state only; no prompt bodies). Refreshing `/app/analyze` loads **Recent analysis** and supports `?run={job_id}` to reopen a completed run.

Partial reruns (without full site recrawl when artifacts exist):

| Action | API `rerun_type` | Reuses |
|--------|------------------|--------|
| Re-run competitor discovery | `competitor_discovery` | Saved website crawl pages or light re-crawl |
| Re-run competitor analysis | `competitor_analysis` | Saved website pages; crawls current competitor list |
| Re-run recommendations | `recommendations` | Existing analysis job + intelligence artifacts |
| Re-generate schedule | `schedule` | Current recommendations |
| Start full re-analysis | `full` | New full flow (same as Analyze) |

### Recent analysis (compact)

The page shows the **latest three** completed runs by default. Each card includes site URL, status, timestamp, pages analyzed, recommendations count, and a primary **Open result** button.

Older runs are behind **View all previous analyses** (collapsible `<details>`). Inline rerun buttons are not shown on cards.

### Rerun menu

A compact **⋯** control on each recent run (and **↻** in the Progress header when viewing a completed run) opens a dropdown menu:

- Re-run competitor discovery
- Re-run competitor analysis
- Re-run recommendations
- Re-generate schedule
- Start full re-analysis

Disabled items stay in the menu but are not clickable; the reason appears in the `title` tooltip (for example “No competitors selected.”), not as inline page text.

**Delete analysis** removes the run from recent history (`DELETE /app/analyze/runs/{job_id}`). The workspace and its SEO artifacts are not deleted. Runs that are still in progress cannot be deleted (HTTP 409).

### Step-level rerun icons

When viewing a completed run, rerunnable steps show a small **↻** next to the step status:

- Competitor discovery
- Competitor analysis
- Opportunity ranking (re-runs recommendations)
- Content calendar (re-generates schedule)

Icons are hidden for non-terminal steps or when the action is unavailable (disabled icon with tooltip).

During a partial rerun, completed steps from the parent run stay succeeded in the progress list; only the targeted step is re-run. The prior summary is preserved in `prior_summary` and merged into the updated summary. Competitor analysis reruns resolve URLs from workspace settings, the parent run’s `competitor_discovery`, or saved competitor snapshots.

The backend creates or reuses an Autopilot workspace and then delegates to existing services:

- workspace setup
- sitemap discovery
- website crawl
- website analysis
- niche intelligence
- competitor discovery
- competitor analysis
- competitor SEO intelligence (coverage gaps + benchmark metrics)
- market intelligence
- Phase 2A entity relevance scoring
- editorial opportunity generation
- AI opportunity ideation (when `AI_OPPORTUNITY_IDEATION_ENABLED=true`; replaces AI editorial strategist) or AI editorial strategist (default)
- Opportunity Intelligence ranking
- content calendar generation
- draft generation by explicit action
- WordPress upload by explicit action

The implementation does not duplicate EOG, OI, Phase 2A, or scoring logic. It wraps existing `AutopilotService` and article-generation endpoints with a polling status object.

## Status Model

Polling returns:

```json
{
  "workspace_id": "...",
  "job_id": "...",
  "overall_status": "running",
  "steps": [
    {
      "key": "website_analysis",
      "label": "Website analysis",
      "status": "running",
      "started_at": "...",
      "completed_at": null,
      "duration_seconds": null,
      "message": "Analyzing crawled pages",
      "error": null,
      "warnings": []
    }
  ],
  "summary": {}
}
```

Step statuses are:

- `queued`
- `running`
- `succeeded`
- `failed`
- `skipped`
- `warning`

Only one step should be `running` at a time. Future steps remain `queued` until the backend reaches them. Completed steps remain `succeeded`, `warning`, `failed`, or `skipped`.

## Progress Reporting

Steps may include optional progress fields:

```json
{
  "progress_current": 10,
  "progress_total": 30,
  "progress_label": "Scraping page 10 of 30",
  "details": {
    "current_url": "https://example.com/faq/",
    "sitemap_urls_found": 4,
    "sitemap_urls_discovered": 39,
    "sitemap_urls_selected": 30,
    "crawl_fallback_used": false
  },
  "timing_note": "included in analysis phase"
}
```

Queued means the step has not started. Running means it is the current active backend phase. Succeeded, warning, failed, and skipped are terminal states.

Durations are shown only when a step has a real measured `started_at` and `completed_at`. If a step is finalized from coarse-grained backend results without direct step timing, `duration_seconds` is omitted and `timing_note` is used instead.

Sitemap discovery details can include robots.txt status, sitemap files found/parsed, URLs discovered, **useful URL count**, URLs selected, fallback usage, and skipped URL counts. When all useful URLs are selected (small-site budget), the step message reads like `Found 39 useful URL(s)`.

Website crawl progress shows **scraped vs selected** counts (for example `Scraped 30 of 39 selected pages. 9 skipped due to page limit.`) so page-cap truncation is never hidden. Details include `urls_crawled`, `urls_skipped_by_cap`, `skipped_by_cap_examples`, and `crawl_budget`. See [CRAWL_BUDGET.md](../analysis/CRAWL_BUDGET.md).

Content inventory is updated during crawl and used by Opportunity Intelligence to avoid duplicate CREATE recommendations. See [CONTENT_INVENTORY.md](../analysis/CONTENT_INVENTORY.md).

Website crawl uses bounded concurrent HTTP fetching (default 4 requests per domain). Progress may show `Scraped N of M pages. K requests active.` Details include `crawl_timing` (duration, failures, concurrency). See [CONCURRENT_CRAWLING.md](../analysis/CONCURRENT_CRAWLING.md).

Website analysis surfaces high-level AI-call messages such as sending crawled content, waiting for the model response, and parsed site understanding. Prompt/body text is not exposed.

Phase 2A entity relevance details can include aggregate counts such as entities requested/scored, model calls, cache hits/misses, filtered/down-ranked counts, and fallback count/reason.

Known limitation: some backend phases still run inside `AutopilotService.analyze_workspace()`, so progress is more granular for sitemap/crawl/website analysis than for every downstream recommendation sub-step.

## Automatic Competitor Discovery

Trendplot always normalizes operator-provided competitor URLs. The analyze flow **pre-crawls the website** (sitemap + page scrape), then runs automatic discovery using crawl signals, cross-workspace niche peers, workspace history, and optional web search before competitor analysis.

Ranked discovery sources (see [COMPETITOR_DISCOVERY_FALLBACKS.md](../analysis/COMPETITOR_DISCOVERY_FALLBACKS.md)):

1. Provided competitors
2. Comparison / alternatives / vs pages from crawl
3. Historical niche peers (other workspaces, same niche)
4. Competitor snapshots (current workspace)
5. Outbound commercial links from crawl
6. Web search (optional: DuckDuckGo without API key, or Brave when configured)

Merge rules:

- provided competitors first (priority)
- discovered competitors second
- dedupe by registrable domain
- classify domains (see [DOMAIN_CLASSIFICATION.md](../analysis/DOMAIN_CLASSIFICATION.md)); only `competitor` enters selection
- reject same-domain and low-quality URLs within the competitor pool
- cap final total at `COMPETITOR_TOTAL_MAX_COMPETITORS`

If discovery succeeds (alone or merged), competitor analysis runs against the final set and the summary includes a `competitor_discovery` block with source, counts, and selected competitor domains **with per-domain source attribution** (for example `Source: comparison page`).

Summary cases:

- **Provided + discovered:** `Provided competitors: N`, `Discovered competitors: M`, `Total analyzed: T`
- **Discovered only:** `Discovered competitors: M`, `Total analyzed: T`
- **Provided only:** `Provided competitors: N`, `Discovered competitors: 0`, `Total analyzed: T`
- **None available:** discovery WARNING + competitor analysis SKIPPED
- **Competitor analysis succeeded:** message reflects pages scraped and coverage gaps from the current run (not contradictory SKIPPED + scraped counts)

If discovery finds no safe candidates and none were provided, the run continues with a warning. Competitor analysis is marked skipped with a clear reason rather than silently skipped. When competitors are selected and intelligence artifacts exist, competitor analysis is `succeeded` even if workspace snapshot lists are empty in the summary payload.

Failure diagnostics include:

- `reason` / `reason_message` — why no competitors were selected
- **Checked** — comparison pages, outbound domains, niche peers, history, snapshots, web search (when attempted)
- **Skipped** — web search disabled, API key missing, or not configured
- `candidates_found` / `selected_count` — pipeline transparency
- `source_summary` — per-source candidate/selected counts (web search failures are source-level, not overall discovery failure)
- `classification_counts` / `other_discovered_domains` — non-competitor domains preserved for future use
- `web_search_summary` — when a provider ran or was skipped (informational when other sources succeeded)
- Per-competitor `source` in results (no raw crawl dumps)

These appear in step warnings, the step Details panel, and the results summary tab.

First-run workspaces without history can discover competitors **without a paid API** using crawl fallbacks and/or DuckDuckGo:

```env
ENABLE_EXTERNAL_RESEARCH=true
MARKET_PROVIDER_WEB_ENABLED=true
WEB_SEARCH_PROVIDER=duckduckgo
```

Optional Brave Search (`WEB_SEARCH_PROVIDER=brave`, `BRAVE_SEARCH_API_KEY=...`) adds a more stable configured provider when you have an API key.

See [WEB_SEARCH_PROVIDER_CONFIGURATION.md](../analysis/WEB_SEARCH_PROVIDER_CONFIGURATION.md) and [COMPETITOR_DISCOVERY_FALLBACKS.md](../analysis/COMPETITOR_DISCOVERY_FALLBACKS.md).

## Step Details disclosure

Progress steps may include a **Details** disclosure (`<details>`). Expanded state is preserved across polling updates:

- before each re-render, currently open step keys are captured
- re-rendered Details elements restore the `open` attribute
- toggle events keep an in-memory set in sync with operator actions

Polling stops when the overall run reaches a terminal status, but disclosure preservation also covers in-flight updates while downstream steps (for example content calendar) are still running.

## Results

When the run finishes, the UI shows:

- workspace URL/name/mode
- detected niche and confidence
- pages analyzed
- competitor coverage
- competitor intelligence benchmark deltas
- competitor coverage gaps and top opportunity signals
- low-content warning
- recommendation counts
- full recommendation items (all actions) for queue filters
- proposed schedule/calendar
- sitemap discovery warnings
- Phase 2A fallback warnings
- WordPress/publishing safety state

The diagnostics tab exposes the full polling object for operator debugging. If summary action counts do not match the recommendation item list (for example after a partial rerun), mismatch warnings appear at the top of Diagnostics only.

## Recommendations tab — action queues

The Recommendations tab shows clickable queue filters:

```text
[Create N] [Refresh N] [Monitor N] [Ignore N] [All N]
```

Default filter: **Create**. The active filter is highlighted.

| Queue | Shows | Primary action |
|-------|-------|----------------|
| Create | `action = create` | **Select for draft** |
| Refresh | `action = refresh` | **Review refresh task** (+ existing page URL/title when linked) |
| Monitor | `action = monitor` | **Keep monitoring** (label) + optional **Promote to draft** |
| Ignore | `action = ignore` | Explanation only — no draft button |
| All | Every recommendation | Action-specific buttons as above |

Within each queue, items keep the existing score/priority ordering from Opportunity Intelligence (no re-ranking).

**AI opportunity ideation** recommendations (`source_type = ai_opportunity_ideation`) show additional fields when present:

- Abstract
- Related products
- Search intent and content type
- Recommendation type (`create`, `refresh`, `expand`, `follow_up`)
- Origin label: **AI opportunity ideation**

Prompt text and brief JSON are not exposed in the UI.

Empty queue: `No recommendations in this queue.`

## Draft Generation

Draft generation uses the existing article generation pipeline:

```text
POST /generate-article
```

The operator must select a recommendation or schedule item first. Generated articles remain viewable through the existing job JSON and preview endpoints, even when publishing is disabled.

When the selected recommendation came from AI opportunity ideation, draft generation also sends `opportunity_context` (headline, abstract, search intent, related products/topics, audience, safety notes) into the article generation prompt as editorial brief context.

## Publishing Behavior

Manual review remains the default.

Draft upload:

- requires explicit operator action
- requires WordPress configuration
- uses existing draft publishing endpoint

Live publish:

- disabled unless `ALLOW_LIVE_PUBLISH=true`
- still relies on existing quality and sanity gates
- requires explicit operator action

The UI does not clear credentials, does not require connector mode, and does not bypass safety gates.

## Known Limitations

- Step timing is coarse for phases bundled inside the current monolithic analysis method.
- The polling status store is in-memory and is intended for current-process operator sessions.
- Draft generation from a recommendation uses existing article generation fields and may require operator review of topic/title metadata.
- WordPress upload behavior is not tested by this flow unless WordPress is configured and the operator explicitly clicks upload.

A) Web-search provider implemented
