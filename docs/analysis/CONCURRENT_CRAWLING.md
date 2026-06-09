# Concurrent crawling

## Before (sequential)

```text
robots.txt → sitemap A → sitemap B → sitemap C → page 1 → page 2 → … → page N
```

Each HTTP request waited for the previous one to finish. For ~30 pages at ~2–3s each, wall-clock crawl time approached **60–90+ seconds** even when the target site could accept more connections.

### Prior bottlenecks

| Stage | Behavior |
|-------|----------|
| Sitemap index children | Parsed one sitemap file at a time |
| Page crawl | `_fetch_page` in a `for` loop |
| Timeouts | Fixed 15s per request, new `httpx` client per page |
| Retries | None at HTTP layer |
| Failures | Page returned `status: error`; run continued |
| Progress | Per-page path only |

## After (bounded concurrent)

```text
                    ┌─ sitemap batch (≤4 concurrent) ─┐
robots.txt ────────►│  page-sitemap.xml              │
                    │  post-sitemap.xml              │──► ranked URLs
                    └─ product-sitemap.xml           ┘
                                        │
                    ┌─ page batch (≤4 per domain) ───┤
                    │  page 1..N (stable order)      │
                    └────────────────────────────────┘
```

`CrawlHttpClient` (`app/concurrent_crawl.py`) provides:

- **Per-domain semaphore** — max `CRAWL_CONCURRENCY_PER_DOMAIN` simultaneous requests to the same host (default **4**).
- **Shared `httpx.AsyncClient`** per analyze/crawl session (connection reuse).
- **Politeness delay** — short pause after acquiring the semaphore (`CRAWL_POLITENESS_DELAY_MS`, default **250ms**).
- **Retries** — `CRAWL_RETRY_COUNT` + `CRAWL_RETRY_BACKOFF_SECONDS` for timeouts and 429/503/403.
- **Stable ordering** — results stored by index; output list matches input URL order.
- **Fail-open** — failed pages become `status: error` rows; crawl and analysis continue.

## Configuration

```env
CRAWL_CONCURRENCY_PER_DOMAIN=4
CRAWL_REQUEST_TIMEOUT_SECONDS=15
CRAWL_RETRY_COUNT=1
CRAWL_RETRY_BACKOFF_SECONDS=2
CRAWL_POLITENESS_DELAY_MS=250
```

Crawl **budget** limits (`MAX_PAGES_PER_SITE`, small-site threshold) are unchanged — concurrency only affects how fast selected pages are fetched.

## Rate limiting

On **429**, **503**, or **403**, the client:

1. Records a warning in `crawl_timing.warnings`
2. Increments `rate_limit_events`
3. Temporarily reduces effective concurrency for that domain (by 1, minimum 1)
4. Retries with backoff when retries remain

## Observability

`url_discovery.crawl_timing` (and Analyze Website step details):

```json
{
  "crawl_concurrency": 4,
  "pages_requested": 39,
  "pages_completed": 38,
  "pages_failed": 1,
  "crawl_duration_seconds": 18.2,
  "avg_page_latency_seconds": 1.3,
  "sitemap_fetch_duration_seconds": 2.1,
  "page_crawl_duration_seconds": 16.1,
  "sitemap_files_fetched": 4,
  "rate_limit_events": 0,
  "warnings": []
}
```

Progress UI (when polling):

```text
Scraped 17 of 39 pages. 4 requests active.
```

## Scope

| In scope | Out of scope |
|----------|----------------|
| Sitemap file fetch batches | OpenAI / LLM parallelization |
| Website + competitor page crawl | WordPress publish writes |
| Analyze Website flow | Unbounded global concurrency |

## User-Agent

Unchanged: `seo-content-worker/0.1` (`CRAWL_USER_AGENT` in code).

## robots.txt

Existing robots/sitemap discovery behavior is preserved; only fetch scheduling changed.
