# Crawl budget

Trendplot separates **sitemap selection** from **page scraping** so small sites are not truncated silently while large sites stay bounded.

## Configuration

```env
MAX_PAGES_PER_SITE=30
CRAWL_SMALL_SITE_FULL_THRESHOLD=50
CRAWL_LARGE_SITE_SAMPLE_LIMIT=100
```

| Setting | Role |
|--------|------|
| `MAX_PAGES_PER_SITE` | Maximum pages scraped per site on large sites |
| `CRAWL_SMALL_SITE_FULL_THRESHOLD` | When useful sitemap URLs are at or below this count, scrape all selected URLs |
| `CRAWL_LARGE_SITE_SAMPLE_LIMIT` | Maximum URLs kept in the ranked selection pool on large sites |

## Useful URLs

After sitemap parsing, URLs are normalized and filtered (low-value paths, external domains, etc.). The remaining ranked candidates are **useful URLs**.

## Behavior

1. **Useful URLs ≤ threshold** — select all useful URLs and scrape all of them (up to the useful count).
2. **Useful URLs > threshold** — select up to `CRAWL_LARGE_SITE_SAMPLE_LIMIT` ranked URLs, then scrape up to `MAX_PAGES_PER_SITE`.

Competitor crawls still use `MAX_PAGES_PER_SITE` / `COMPETITOR_MAX_PAGES` only.

## Reporting

`url_discovery` metadata and Analyze Website progress include:

- `sitemap_urls_discovered` — raw sitemap entries parsed
- `useful_url_count` — candidates after filtering/ranking
- `sitemap_urls_selected` — URLs chosen for crawl
- `urls_crawled` — pages actually scraped
- `urls_skipped_by_cap` — selected but not scraped due to cap
- `skipped_by_cap_examples` — sample paths/URLs (up to 8)
- `crawl_budget` — resolved limits for the run

## UI examples

**Small site (39 useful URLs, threshold 50):**

```text
Sitemap discovery — Found 39 useful URL(s) from 120 discovered.
Website crawl — Scraped 39 of 39 pages.
```

**Large site (80 useful, cap 30):**

```text
Sitemap discovery — Selected 80 of 80 useful URL(s) (500 discovered).
Website crawl — Scraped 30 of 80 selected pages. 50 skipped due to page limit.
```

Details panels list `skipped_by_cap_examples` when present.

## Concurrent fetching

Selected pages are scraped with bounded per-domain concurrency (default 4). See [CONCURRENT_CRAWLING.md](CONCURRENT_CRAWLING.md). `url_discovery.crawl_timing` reports duration, failures, and concurrency metrics without changing crawl caps.
