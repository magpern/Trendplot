# Sitemap Discovery

Trendplot uses sitemap-first URL discovery during website analysis so production-like runs observe a broader, more representative page set before recommendations are generated.

## How Discovery Works

For each analyzed site, Trendplot now:

1. Normalizes the submitted website URL.
2. Fetches `/robots.txt`.
3. Parses all `Sitemap:` directives.
4. If robots.txt exposes no sitemap, tries common public sitemap locations:
   - `/sitemap_index.xml`
   - `/sitemap.xml`
   - `/wp-sitemap.xml`
   - `/page-sitemap.xml`
   - `/post-sitemap.xml`
   - `/product-sitemap.xml`
5. Parses sitemap index files recursively.
6. Parses regular URL set sitemap files.
7. Selects a bounded representative URL set.
8. Scrapes the selected pages with the existing page scraper.
9. Uses the existing internal-link crawl as a fallback or supplement when sitemap discovery fails or returns too few selected pages.

The selected URL list and reasons are attached to the analysis `url_discovery` artifact. INFO logs contain only aggregate counts, not large URL lists.

## Why The WordPress Plugin Is Not Required

The WordPress plugin does not need to generate a sitemap for this workflow.

Most WordPress sites already expose public XML sitemaps through WordPress core or SEO plugins. Trendplot consumes those public sitemaps first. The plugin can later expose richer private inventory or publishing data, but plugin-backed sitemap generation is intentionally out of scope.

## URL Selection

Trendplot does not scrape every sitemap URL. It ranks and selects a representative set, preferring:

- homepage
- about/company pages
- FAQ, help, support, or documentation pages
- product, service, solution, pricing, and category pages
- blog, article, guide, resource, and learn pages
- recent pages when `lastmod` is present
- evergreen pages such as case studies and use cases

It filters or deprioritizes obvious low-value URLs such as cart, checkout, account, login, admin, feed, tag archives, search pages, legal utility pages, paginated archives, external domains, and query-string utility URLs.

## Fallback Crawling

Fallback crawling is used when:

- robots.txt cannot be fetched
- no sitemap directives are present
- common sitemap paths are missing
- sitemap XML is malformed
- sitemaps contain too few usable content URLs

Fallback uses the existing homepage internal-link selection logic, so current crawling behavior remains available and no connector/plugin access is required.

## Configuration

Defaults:

```env
SITEMAP_DISCOVERY_ENABLED=true
CRAWL_FALLBACK_ENABLED=true
MAX_PAGES_PER_SITE=30
SITEMAP_MAX_URLS_TO_PARSE=5000
SITEMAP_MAX_SITEMAPS_TO_PARSE=50
```

Notes:

- `MAX_PAGES_PER_SITE` caps scraped pages on **large** sites; small sites (useful URLs ≤ `CRAWL_SMALL_SITE_FULL_THRESHOLD`) scrape all useful URLs. See [CRAWL_BUDGET.md](CRAWL_BUDGET.md).
- `SITEMAP_MAX_URLS_TO_PARSE` protects large sites from full sitemap ingestion.
- `SITEMAP_MAX_SITEMAPS_TO_PARSE` limits recursive sitemap-index traversal.
- Explicit request limits below `MAX_PAGES_PER_SITE` are still respected.

## Observability

Analysis metadata includes:

- `sitemap_discovery_enabled`
- `robots_txt_checked`
- `sitemap_urls_found`
- `sitemap_files_parsed`
- `sitemap_urls_discovered`
- `sitemap_urls_selected`
- `crawl_fallback_used`
- `skipped_url_counts_by_reason`
- selected URL list with reasons

INFO logs emit the same aggregate counts without the selected URL list.

## Limitations

- JavaScript-only sites may still produce sparse page text.
- Sitemaps that omit important pages can still require crawl fallback.
- External-domain sitemap URLs are ignored by default.
- Private WordPress inventory and authenticated plugin data are not used.
- The selector is heuristic and intentionally conservative; it favors representative content over exhaustive coverage.

A) Sitemap-first discovery implemented
