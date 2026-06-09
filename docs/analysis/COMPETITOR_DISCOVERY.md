# Competitor Discovery

## Purpose

Trendplot discovers competitor domains automatically and merges them with operator-provided competitor URLs before competitor analysis runs.

## Execution Rules

1. Normalize and keep operator-provided competitor URLs (priority order first).
2. If `COMPETITOR_DISCOVERY_ENABLED=true`, also attempt automatic discovery.
3. Merge provided + discovered candidates, dedupe by registrable domain, reject unsafe domains.
4. Cap the final set at `COMPETITOR_TOTAL_MAX_COMPETITORS`.
5. Pass the merged set to competitor analysis in the same run.
6. If discovery finds nothing, continue analysis and surface a warning (do not fail the run).

If discovery is disabled:

- use provided competitors only when supplied
- otherwise return `source=none` with a disabled warning

## Merge behavior

```text
final_competitors =
    normalized provided competitors
    + normalized discovered competitors
    - duplicates
    - same-domain
    - rejected domains
```

Priority: provided competitors first, discovered second. When the total cap is reached, discovered slots are trimmed before provided slots.

## Sources

Ranked discovery sources (see [COMPETITOR_DISCOVERY_FALLBACKS.md](./COMPETITOR_DISCOVERY_FALLBACKS.md)):

1. Operator-provided URLs (`provided`)
2. Comparison / alternatives / vs page extraction from website crawl (`comparison_page`)
3. Historical niche peers from other workspaces (`niche_peer`)
4. Current workspace competitor snapshots (`competitor_snapshot`)
5. Current workspace site-understanding history (`workspace_history`)
6. Outbound commercial links from crawl (`outbound_domain`)
7. Web search provider (`web_search`) — optional

Deterministic internal sources (no paid API required):

- operator-provided URLs
- website crawl comparison/outbound signals (pre-crawl before discovery)
- cross-workspace niche peer snapshots
- existing site-understanding competitor values
- historical competitor snapshots

Optional (when configured, not required):

- web search via **DuckDuckGo** (`WEB_SEARCH_PROVIDER=duckduckgo`, no API key) or **Brave Search API** (`WEB_SEARCH_PROVIDER=brave`, `BRAVE_SEARCH_API_KEY`) — see [WEB_SEARCH_PROVIDER_CONFIGURATION.md](./WEB_SEARCH_PROVIDER_CONFIGURATION.md)

## Candidate Filtering

- reject same-domain candidates when `COMPETITOR_DISCOVERY_REQUIRE_EXTERNAL_DOMAIN=true`
- reject social and community hosts (`t.me`, `telegram.me`, Facebook, X/Twitter, LinkedIn, YouTube, Discord, Reddit, Pinterest, TikTok, etc.)
- reject **owned social/channel** URLs when the path/handle matches the analyzed brand (e.g. `https://t.me/example-lab` for `example.com`)
- reject official profile URLs found in the site's own outbound links
- reject directory/SEO-aggregator domains
- reject large marketplace/platform domains
- reject link aggregators (`linktr.ee`, `lnk.bio`, …)
- normalize and deduplicate by registrable domain
- select up to `COMPETITOR_DISCOVERY_MAX_COMPETITORS` from the discovered pool before merge
- cap final merged list at `COMPETITOR_TOTAL_MAX_COMPETITORS`

Diagnostics include aggregate rejection counts:

```json
{
  "rejected_by_reason": {
    "owned_social_channel": 1,
    "social_domain": 2
  },
  "rejected_samples": [
    {"url": "https://t.me/example-lab", "reason": "owned social/channel", "reason_code": "owned_social_channel"}
  ]
}
```

## Output Contract

```json
{
  "enabled": true,
  "source": "provided|discovered|provided+discovered|none",
  "queries": 3,
  "candidates_found": 5,
  "provided_count": 2,
  "discovered_count": 3,
  "merged_count": 5,
  "selected_count": 5,
  "competitors_selected": 5,
  "history_checked": true,
  "snapshots_checked": true,
  "web_search_enabled": false,
  "web_search_attempted": false,
  "provider_name": "brave-search",
  "queries_run": 3,
  "raw_results_count": 12,
  "provider_error": null,
  "web_search_summary": "Web search attempted using Brave Search. Found 12 results, 4 candidates, selected 3.",
  "candidates_rejected": 0,
  "reason": "first_run_no_history",
  "reason_message": "First-run workspace with no prior competitor intelligence.",
  "sources_checked": ["comparison_pages", "outbound_domains", "niche_peers", "workspace_history", "competitor_snapshots"],
  "sources_skipped": [
    {
      "source": "web_search",
      "reason": "disabled",
      "detail": "provider not configured"
    }
  ],
  "competitors": [
    {
      "url": "https://rivalco.com",
      "domain": "rivalco.com",
      "origin": "comparison_page",
      "source": "comparison page",
      "confidence": 0.92,
      "reason": "Outbound link from /vs/rival"
    }
  ],
  "warning": "First-run workspace with no prior competitor intelligence."
}
```

## Failure reasons

| Reason code | Meaning |
|-------------|---------|
| `discovery_disabled` | `COMPETITOR_DISCOVERY_ENABLED=false` and no provided competitors |
| `first_run_no_history` | No crawl signals, workspace history, snapshots, niche peers, or web search configuration |
| `no_candidate_sources` | Sources were checked but returned zero raw candidates |
| `all_candidates_rejected` | Candidates were found but all failed quality filters |
| `provided_only_invalid` | Provided URLs failed filtering |
| `web_search_no_results` | Web search ran but returned no usable domains |
| `web_search_provider_error` | Web search provider returned an error (fail-open) |

The UI and step warnings surface `reason_message`, `sources_checked`, `sources_skipped`, `web_search_summary`, `provider_name`, `queries_run`, `raw_results_count`, `candidates_found`, and `candidates_rejected` when discovery fails or web search runs.

## Source checks

When discovery runs, Trendplot records which sources were consulted:

- **comparison_pages** — vs/alternatives/compare pages from website pre-crawl
- **outbound_domains** — commercial outbound links from crawl
- **niche_peers** — competitor URLs from other workspaces in the same niche
- **workspace_history** — prior site understanding (`competitors` field)
- **competitor_snapshots** — historical competitor snapshot records for current workspace
- **web_search** — external web search (only when enabled and attempted)

Skipped sources include a reason (`disabled`, `no_results`) and optional detail (for example which env flags blocked web search).

## UI disclosure behavior

Analyze Website progress steps use native `<details>` elements for diagnostics. Expanded state is preserved across polling refreshes using an in-memory `openStepDetails` set synchronized before each re-render. Polling does not collapse panels the operator has opened.

Competitor discovery failures show reason and source checks in:

- step warnings (progress panel) with Checked / Skipped lists
- step Details panel (structured diagnostics + per-competitor source)
- results summary tab (discovered competitors with source attribution)

## Flow order

1. Website pre-crawl (sitemap + page scrape) for discovery signals
2. Competitor discovery (fallbacks + optional web search)
3. Full analysis job (reuses prefetched website crawl; crawls competitors)

## Configuration

```env
COMPETITOR_DISCOVERY_ENABLED=true
COMPETITOR_DISCOVERY_MAX_COMPETITORS=3
COMPETITOR_DISCOVERY_MAX_QUERIES=5
COMPETITOR_DISCOVERY_REQUIRE_EXTERNAL_DOMAIN=true
COMPETITOR_TOTAL_MAX_COMPETITORS=5
WEB_SEARCH_PROVIDER=duckduckgo
BRAVE_SEARCH_API_KEY=
DUCKDUCKGO_SEARCH_TIMEOUT_SECONDS=10
DUCKDUCKGO_SEARCH_MAX_RESULTS=10
ENABLE_EXTERNAL_RESEARCH=true
MARKET_PROVIDER_WEB_ENABLED=true
```

## Domain classification

Discovered domains are classified before competitor selection. Only `competitor` domains are used for competitor analysis; other roles are retained in diagnostics. See [DOMAIN_CLASSIFICATION.md](./DOMAIN_CLASSIFICATION.md).

## Per-source reporting

Discovery exposes `source_summary` with per-source candidate and selected counts. Web search failures (for example DuckDuckGo returning no usable results) are reported at the source level and do not fail overall discovery when another source selects competitors.

Example:

```text
Competitor discovery: SUCCEEDED
Sources:
- competitor snapshots: 2
- niche peers: 1
- web search: 0 usable results
```

## UI summary cases

| Case | Display |
|------|---------|
| Success with sources | Competitors selected: N + per-source lines |
| Provided + discovered | Provided: N, Discovered: M, Total: T (legacy message when source_summary absent) |
| Discovered only | Discovered: M, Total: T |
| Provided only (discovery disabled or none found) | Provided: N, Discovered: 0, Total: T |
| None available | WARNING + competitor analysis SKIPPED |

## Competitor analysis status

Competitor analysis step status is derived from discovery selection plus current-run `competitor_seo_intelligence` artifacts (pages scraped, coverage gaps, benchmarks)—not from stale workspace snapshot lists alone.

| Status | When |
|------|------|
| `succeeded` | Competitors selected and pages or intelligence artifacts exist for the run |
| `warning` | Competitors selected but analysis produced no pages or intelligence |
| `skipped` | No competitors selected |

## Limitations

- Comparison-page name extraction may infer `.com` domains for brand names without explicit URLs; outbound links are preferred when present.
- Niche peer discovery requires at least one other workspace with a matching `primary_niche`.
- DuckDuckGo is best-effort (no SLA); Brave uses the official API. Neither blocks the run on failure. See [WEB_SEARCH_PROVIDER_CONFIGURATION.md](./WEB_SEARCH_PROVIDER_CONFIGURATION.md).

## Verification

See [COMPETITOR_DISCOVERY_VERIFICATION.md](./COMPETITOR_DISCOVERY_VERIFICATION.md) and [COMPETITOR_DISCOVERY_FALLBACKS.md](./COMPETITOR_DISCOVERY_FALLBACKS.md).

A) Competitor discovery with classification, source reporting, and analyze-flow status alignment implemented
