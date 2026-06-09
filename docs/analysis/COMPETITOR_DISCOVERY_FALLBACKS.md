# Competitor Discovery Fallbacks

## Purpose

Provider-neutral competitor discovery for first-run workspaces. Uses signals already available from the target website crawl and cross-workspace intelligence before optional web-search providers.

## Existing signal audit

| Artifact | Location | Competitor signals |
| --- | --- | --- |
| Sitemap discovery | `url_discovery` on crawled site | Comparison/alternative URL paths (`/vs`, `/alternatives`, `/compare`) |
| Crawl pages | `analysis_pages`, in-memory crawl during analyze | Titles, headings, `text_sample`, `outbound_links`, `commercial_links` |
| Website analysis | `site_understanding_snapshots` | Historical `competitors_json` for current workspace |
| Niche intelligence | `workspace_niche_profiles` | `primary_niche` for cross-workspace peer lookup |
| Market intelligence | market brief / query planner | Niche + entity labels (query context only) |
| Competitor intelligence | `competitor_snapshots` | Prior competitor URLs per workspace; peer domains in same niche |

## Fallback sources (no paid API)

### 1. Comparison / alternatives / vs pages

Deterministic extraction from crawled pages when path or title matches comparison patterns:

- `/vs`, `/compare`, `/alternatives`, `/competitors`
- Titles like `Brand vs Competitor`, `Alternative to X`, `Compared with Y`

Names are converted to domains when possible; outbound links on comparison pages are promoted with higher confidence.

### 2. Outbound domain intelligence

All crawled pages contribute outbound links. Infrastructure domains are filtered:

- Social, directories, marketplaces (existing filters)
- Analytics, CDNs, payments, hosting, documentation providers

Remaining commercial domains are weak competitor signals (`origin=outbound_domain`).

### 3. Niche peer discovery

When a niche hint exists (workspace name, prior niche profile, or understanding), query other workspaces with the same `primary_niche` and reuse their `competitor_snapshots` URLs.

This lets a new workspace benefit from knowledge accumulated elsewhere without requiring its own history.

### 4. Workspace history and snapshots

Unchanged internal sources:

- `site_understanding.competitors` for the current workspace
- Historical `competitor_snapshots` for the current workspace

## Source ranking

Candidates merge in this priority order (higher wins on dedupe):

1. Operator-provided (`provided`)
2. Comparison-page extraction (`comparison_page`)
3. Historical niche peers (`niche_peer`)
4. Competitor snapshots (`competitor_snapshot`)
5. Workspace history (`workspace_history`)
6. Outbound-domain signals (`outbound_domain`)
7. Web-search provider results (`web_search`) — optional, unchanged when configured

Within the same rank, higher `confidence` wins.

Example candidate:

```json
{
  "domain": "rivalco.com",
  "url": "https://rivalco.com",
  "origin": "comparison_page",
  "source": "comparison page",
  "confidence": 0.92,
  "reason": "Outbound link from /vs/rival"
}
```

## Confidence rules

| Source | Base confidence | Notes |
| --- | ---: | --- |
| Provided | 1.0 | Operator input |
| Comparison page (named entity) | 0.72–0.86 | Higher when value looks like a domain |
| Comparison page (outbound link) | 0.78–0.82 | Boost when link text mentions compare/alternative |
| Niche peer | 0.68 | Cross-workspace snapshot reuse |
| Competitor snapshot | 0.75 | Current workspace history |
| Workspace history | 0.72 | Prior understanding |
| Outbound domain | 0.44–0.62 | Weak signal; infrastructure filtered |
| Web search | 0.58 | Optional provider path |

## Analyze flow integration

Competitor discovery now runs **after** a website pre-crawl:

1. Sitemap discovery + website crawl (progress: `sitemap_discovery`, `website_crawl`)
2. Competitor discovery using crawl signals + niche peers + optional web search
3. Full analysis job reuses the prefetched website crawl (no duplicate website fetch)

## Diagnostics

When discovery fails or partially succeeds, diagnostics include:

- **Checked:** comparison pages, outbound domains, niche peers, snapshots, history, web search (when run)
- **Skipped:** web search when provider not configured or disabled
- **Candidates found / Selected**
- Per-competitor `source` attribution in results UI

## Provider vs non-provider discovery

| Mode | Requirements | Typical first-run outcome |
| --- | --- | --- |
| Non-provider | Website crawl only | Comparison/outbound/niche-peer candidates |
| Web search (DuckDuckGo) | `WEB_SEARCH_PROVIDER=duckduckgo`, external research flags | Above + web-search candidates (no API key) |
| Web search (Brave) | `WEB_SEARCH_PROVIDER=brave`, API key, external research flags | Above + web-search candidates (stable configured provider) |

Web search providers remain optional enhancements; they are not required for first-run discovery. DuckDuckGo is suitable for dev/self-hosted use; Brave is preferred when you have an API key.
