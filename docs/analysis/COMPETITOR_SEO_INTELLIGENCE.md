# Competitor SEO Intelligence

Date: 2026-06-02

## Purpose

Trendplot now analyzes competitor websites using public SEO-visible signals and converts those findings into structured opportunity inputs for the existing recommendation pipeline.

This implementation does not access private WordPress data, Rank Math internals, Search Console, paid SEO APIs, or connector/plugin-only data.

## How It Works

1. Competitor URLs are sourced from provided inputs or automatic competitor discovery.
2. For each competitor site:
   - sitemap-first discovery is used when available
   - fallback crawl is used when sitemap discovery is unavailable or sparse
   - page selection is capped by `COMPETITOR_MAX_PAGES` (default `20`)
3. Each selected page is parsed for structured SEO signals.
4. Competitor coverage is compared against workspace coverage topics.
5. Coverage gaps are transformed into opportunity signals and fed into existing OI flow through competitor snapshots.

## Signals Collected

Per page, Trendplot extracts and stores structured fields (no raw HTML persistence added):

- title
- meta description
- URL structure (path + depth)
- canonical URL
- H1 / H2 / H3
- schema types (JSON-LD `@type`)
- internal links
- outbound links
- FAQ presence
- word count
- image count
- entity/topic candidates
- inferred content type

## Comparison Process

Trendplot builds:

- workspace topic set from workspace page signals
- competitor topic sets per competitor domain
- coverage gaps for topics covered by one or more competitors but missing on workspace

Gap signals include:

- topic
- competitor list
- competitor count
- reason text

## Opportunity Generation Path

Competitor gap signals are injected into existing pipeline inputs via competitor snapshots (`topics` + `gap_notes`), so Opportunity Intelligence can rank them with existing scoring and safety logic.

No bypass of OI ranking or recommendation gating is introduced.

## Benchmarking

Trendplot computes comparison metrics:

- workspace averages:
  - `avg_word_count`
  - `avg_faq_count`
  - `avg_internal_links`
  - `avg_outbound_links`
  - `avg_image_count`
- competitor averages for the same metrics
- delta (`competitor_average - workspace`)

## UI Surface

Analyze Website summary now includes a Competitor Intelligence section with:

- competitor pages analyzed
- coverage gap count
- top gap topics
- top SEO observations

The UI does not expose raw crawl dumps.

## Observability

Structured summary logging is added:

- `competitor_seo_intelligence_summary` (INFO)
  - competitors analyzed
  - competitor pages analyzed
  - coverage gap count

Detailed payloads are stored in analysis intelligence artifacts (`competitor_seo_intelligence`) for diagnostics and downstream summarization.

## Config

- `COMPETITOR_MAX_PAGES=20` (default)
- existing sitemap/crawl controls remain active:
  - `SITEMAP_DISCOVERY_ENABLED`
  - `CRAWL_FALLBACK_ENABLED`
  - `MAX_PAGES_PER_SITE`
  - `SITEMAP_MAX_URLS_TO_PARSE`
  - `SITEMAP_MAX_SITEMAPS_TO_PARSE`

## Limitations

- Competitor intelligence is based on publicly crawlable pages only.
- Topic extraction is heuristic and intentionally conservative.
- No SERP/ranking data is used in this pass.
- Some downstream phases still run in coarse-grained analyze steps, so timing remains partially aggregated.
