from __future__ import annotations

import asyncio

from app.concurrent_crawl import CrawlHttpClient, CrawlHttpSettings, HttpFetchResult
from app.config import Settings


def test_concurrency_limit_per_domain() -> None:
    asyncio.run(_test_concurrency_limit_per_domain())


async def _test_concurrency_limit_per_domain() -> None:
    settings = CrawlHttpSettings(
        concurrency_per_domain=2,
        politeness_delay_ms=0,
        retry_count=0,
        timeout_seconds=5,
    )
    client = CrawlHttpClient(settings)
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def tracked_fetch(url: str, *, context: str = "page") -> HttpFetchResult:
        nonlocal active, peak
        async with client._limiter.acquire(url):
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.03)
            async with lock:
                active -= 1
        return HttpFetchResult(
            url=url,
            status_code=200,
            content=b"<html><title>Test</title></html>",
            content_type="text/html",
        )

    client.fetch_http = tracked_fetch  # type: ignore[method-assign]

    async with client:
        pages = await client.fetch_pages_ordered(
            [(f"https://example.com/page-{index}/", "test") for index in range(6)],
            lambda url, fetch: {"url": url, "status": "ok" if fetch.content else "error"},
        )

    assert len(pages) == 6
    assert peak <= 2


def test_failed_page_does_not_fail_crawl() -> None:
    asyncio.run(_test_failed_page_does_not_fail_crawl())


async def _test_failed_page_does_not_fail_crawl() -> None:
    settings = CrawlHttpSettings(concurrency_per_domain=4, politeness_delay_ms=0, retry_count=0)
    client = CrawlHttpClient(settings)
    calls = 0

    async def flaky_fetch(url: str, *, context: str = "page") -> HttpFetchResult:
        nonlocal calls
        calls += 1
        if "bad" in url:
            return HttpFetchResult(url=url, status_code=None, content=None, content_type="", error="failed")
        return HttpFetchResult(url=url, status_code=200, content=b"<html></html>", content_type="text/html")

    client.fetch_http = flaky_fetch  # type: ignore[method-assign]

    async with client:
        pages = await client.fetch_pages_ordered(
            [
                ("https://example.com/good/", "ok"),
                ("https://example.com/bad/", "bad"),
                ("https://example.com/good-2/", "ok"),
            ],
            lambda url, fetch: {"url": url, "status": "error" if fetch.content is None else "ok"},
        )

    assert len(pages) == 3
    assert client.metrics.pages_failed == 1
    assert client.metrics.pages_completed == 2


def test_output_ordering_stable() -> None:
    asyncio.run(_test_output_ordering_stable())


async def _test_output_ordering_stable() -> None:
    settings = CrawlHttpSettings(concurrency_per_domain=4, politeness_delay_ms=0, retry_count=0)
    client = CrawlHttpClient(settings)
    delay_by_index = {0: 0.05, 1: 0.01, 2: 0.03}

    async def staggered_fetch(url: str, *, context: str = "page") -> HttpFetchResult:
        index = int(url.rstrip("/").split("-")[-1])
        await asyncio.sleep(delay_by_index.get(index, 0))
        return HttpFetchResult(url=url, status_code=200, content=b"<html></html>", content_type="text/html")

    client.fetch_http = staggered_fetch  # type: ignore[method-assign]

    async with client:
        pages = await client.fetch_pages_ordered(
            [(f"https://example.com/p-{index}/", "ordered") for index in range(3)],
            lambda url, fetch: {"url": url, "status": "ok"},
        )

    assert [page["url"] for page in pages] == [
        "https://example.com/p-0/",
        "https://example.com/p-1/",
        "https://example.com/p-2/",
    ]


def test_retry_records_rate_limit_event() -> None:
    asyncio.run(_test_retry_records_rate_limit_event())


async def _test_retry_records_rate_limit_event() -> None:
    from unittest.mock import AsyncMock

    import httpx

    settings = CrawlHttpSettings(
        concurrency_per_domain=1,
        politeness_delay_ms=0,
        retry_count=0,
    )
    client = CrawlHttpClient(settings)

    async with client:
        request = httpx.Request("GET", "https://example.com/one/")
        response_429 = httpx.Response(429, request=request)
        client._client.get = AsyncMock(return_value=response_429)  # type: ignore[method-assign]

        result = await client.fetch_http("https://example.com/one/", context="page")

    assert result.content is None
    assert client.metrics.rate_limit_events >= 1


def test_metrics_populated() -> None:
    asyncio.run(_test_metrics_populated())


async def _test_metrics_populated() -> None:
    settings = CrawlHttpSettings(concurrency_per_domain=2, politeness_delay_ms=0, retry_count=0)
    client = CrawlHttpClient(settings)

    async def ok_fetch(url: str, *, context: str = "page") -> HttpFetchResult:
        await asyncio.sleep(0.01)
        return HttpFetchResult(url=url, status_code=200, content=b"<html></html>", content_type="text/html")

    client.fetch_http = ok_fetch  # type: ignore[method-assign]

    async with client:
        await client.fetch_sitemap_resources_ordered(["https://example.com/sitemap.xml"])
        await client.fetch_pages_ordered(
            [("https://example.com/a/", "a"), ("https://example.com/b/", "b")],
            lambda url, fetch: {"url": url, "status": "ok"},
        )

    payload = client.metrics.as_dict()
    assert payload["crawl_concurrency"] == 2
    assert payload["pages_requested"] == 2
    assert payload["pages_completed"] == 2
    assert payload["sitemap_files_fetched"] == 1
    assert payload["page_crawl_duration_seconds"] > 0


def test_settings_from_app_config() -> None:
    settings = CrawlHttpSettings.from_settings(
        Settings(
            CRAWL_CONCURRENCY_PER_DOMAIN=3,
            CRAWL_REQUEST_TIMEOUT_SECONDS=20,
            CRAWL_RETRY_COUNT=2,
        )
    )
    assert settings.concurrency_per_domain == 3
    assert settings.timeout_seconds == 20
    assert settings.retry_count == 2
