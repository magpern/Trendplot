"""Bounded per-domain HTTP fetching for sitemap and page crawls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings

logger = logging.getLogger("trendplot.concurrent_crawl")

CRAWL_USER_AGENT = "seo-content-worker/0.1"
RATE_LIMIT_STATUS_CODES = frozenset({429, 403, 503})


@dataclass(frozen=True, slots=True)
class CrawlHttpSettings:
    concurrency_per_domain: int = 4
    timeout_seconds: float = 15.0
    retry_count: int = 1
    retry_backoff_seconds: float = 2.0
    politeness_delay_ms: int = 250

    @classmethod
    def from_settings(cls, settings: Settings) -> CrawlHttpSettings:
        return cls(
            concurrency_per_domain=max(1, int(settings.crawl_concurrency_per_domain)),
            timeout_seconds=max(1.0, float(settings.crawl_request_timeout_seconds)),
            retry_count=max(0, int(settings.crawl_retry_count)),
            retry_backoff_seconds=max(0.0, float(settings.crawl_retry_backoff_seconds)),
            politeness_delay_ms=max(0, int(settings.crawl_politeness_delay_ms)),
        )


@dataclass(slots=True)
class CrawlTimingMetrics:
    crawl_concurrency: int = 4
    pages_requested: int = 0
    pages_completed: int = 0
    pages_failed: int = 0
    pages_in_flight: int = 0
    crawl_duration_seconds: float = 0.0
    avg_page_latency_seconds: float = 0.0
    sitemap_fetch_duration_seconds: float = 0.0
    page_crawl_duration_seconds: float = 0.0
    sitemap_files_fetched: int = 0
    sitemap_fetch_failed: int = 0
    rate_limit_events: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "crawl_concurrency": self.crawl_concurrency,
            "pages_requested": self.pages_requested,
            "pages_completed": self.pages_completed,
            "pages_failed": self.pages_failed,
            "pages_in_flight": self.pages_in_flight,
            "crawl_duration_seconds": round(self.crawl_duration_seconds, 3),
            "avg_page_latency_seconds": round(self.avg_page_latency_seconds, 3),
            "sitemap_fetch_duration_seconds": round(self.sitemap_fetch_duration_seconds, 3),
            "page_crawl_duration_seconds": round(self.page_crawl_duration_seconds, 3),
            "sitemap_files_fetched": self.sitemap_files_fetched,
            "sitemap_fetch_failed": self.sitemap_fetch_failed,
            "rate_limit_events": self.rate_limit_events,
            "warnings": list(self.warnings),
        }


class _PerDomainLimiter:
    def __init__(self, limit: int, politeness_delay_seconds: float) -> None:
        self._limit = max(1, limit)
        self._delay = max(0.0, politeness_delay_seconds)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._reduced: dict[str, int] = {}

    def _effective_limit(self, netloc: str) -> int:
        reduced = self._reduced.get(netloc, 0)
        if reduced <= 0:
            return self._limit
        return max(1, self._limit - reduced)

    def note_rate_limit(self, url: str) -> None:
        netloc = urlparse(url).netloc.lower()
        self._reduced[netloc] = min(self._limit - 1, self._reduced.get(netloc, 0) + 1)

    def _semaphore(self, url: str) -> asyncio.Semaphore:
        netloc = urlparse(url).netloc.lower() or "default"
        if netloc not in self._semaphores:
            self._semaphores[netloc] = asyncio.Semaphore(self._effective_limit(netloc))
        return self._semaphores[netloc]

    @asynccontextmanager
    async def acquire(self, url: str):
        netloc = urlparse(url).netloc.lower() or "default"
        sem = self._semaphore(url)
        async with sem:
            if self._delay:
                await asyncio.sleep(self._delay)
            yield


@dataclass(slots=True)
class HttpFetchResult:
    url: str
    status_code: int | None
    content: bytes | None
    content_type: str
    error: str | None = None


class CrawlHttpClient:
    """Shared bounded HTTP client for sitemap and HTML page fetches."""

    def __init__(self, settings: CrawlHttpSettings) -> None:
        self.settings = settings
        self.metrics = CrawlTimingMetrics(crawl_concurrency=settings.concurrency_per_domain)
        self._limiter = _PerDomainLimiter(
            settings.concurrency_per_domain,
            settings.politeness_delay_ms / 1000.0,
        )
        self._client: httpx.AsyncClient | None = None
        self._latency_total = 0.0
        self._latency_count = 0
        self._metrics_lock = asyncio.Lock()
        self._page_crawl_started_at: float | None = None

    async def __aenter__(self) -> CrawlHttpClient:
        self._client = httpx.AsyncClient(
            timeout=self.settings.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": CRAWL_USER_AGENT},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @classmethod
    def from_app_settings(cls, settings: Settings) -> CrawlHttpClient:
        return cls(CrawlHttpSettings.from_settings(settings))

    async def _adjust_in_flight(self, delta: int) -> int:
        async with self._metrics_lock:
            self.metrics.pages_in_flight = max(0, self.metrics.pages_in_flight + delta)
            return self.metrics.pages_in_flight

    def _record_latency(self, seconds: float) -> None:
        self._latency_total += seconds
        self._latency_count += 1
        if self._latency_count:
            self.metrics.avg_page_latency_seconds = self._latency_total / self._latency_count

    async def fetch_http(self, url: str, *, context: str = "page") -> HttpFetchResult:
        client = self._client
        if client is None:
            raise RuntimeError("CrawlHttpClient is not open.")

        attempts = self.settings.retry_count + 1
        last_error: str | None = None
        for attempt in range(attempts):
            await self._adjust_in_flight(1)
            started = perf_counter()
            try:
                async with self._limiter.acquire(url):
                    response = await client.get(url)
                    if response.status_code in RATE_LIMIT_STATUS_CODES:
                        self.metrics.rate_limit_events += 1
                        self._limiter.note_rate_limit(url)
                        warning = f"{context} fetch rate-limited ({response.status_code}) for {urlparse(url).path or url}"
                        if warning not in self.metrics.warnings:
                            self.metrics.warnings.append(warning)
                        if attempt + 1 < attempts:
                            await asyncio.sleep(self.settings.retry_backoff_seconds * (attempt + 1))
                            continue
                        return HttpFetchResult(
                            url=url,
                            status_code=response.status_code,
                            content=None,
                            content_type=response.headers.get("content-type", ""),
                            error=f"HTTP {response.status_code}",
                        )
                    response.raise_for_status()
                    elapsed = perf_counter() - started
                    self._record_latency(elapsed)
                    return HttpFetchResult(
                        url=str(response.url),
                        status_code=response.status_code,
                        content=response.content,
                        content_type=response.headers.get("content-type", ""),
                    )
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last_error = f"HTTP {status}"
                if status in RATE_LIMIT_STATUS_CODES:
                    self.metrics.rate_limit_events += 1
                    self._limiter.note_rate_limit(url)
            except httpx.HTTPError as exc:
                last_error = str(exc)
            finally:
                await self._adjust_in_flight(-1)

            if attempt + 1 < attempts:
                await asyncio.sleep(self.settings.retry_backoff_seconds * (attempt + 1))

        return HttpFetchResult(url=url, status_code=None, content=None, content_type="", error=last_error or "fetch failed")

    async def fetch_sitemap_resources_ordered(self, urls: list[str]) -> list[HttpFetchResult | None]:
        if not urls:
            return []
        batch_started = perf_counter()

        async def _one(url: str) -> HttpFetchResult | None:
            result = await self.fetch_http(url, context="sitemap")
            if result.content is None:
                self.metrics.sitemap_fetch_failed += 1
                return None
            self.metrics.sitemap_files_fetched += 1
            return result

        results = list(await asyncio.gather(*[_one(url) for url in urls]))
        self.metrics.sitemap_fetch_duration_seconds += perf_counter() - batch_started
        return results

    async def fetch_pages_ordered(
        self,
        items: list[tuple[str, str]],
        build_page: Callable[[str, HttpFetchResult], dict[str, Any]],
        *,
        on_progress: Callable[[int, int, int], Awaitable[None]] | None = None,
    ) -> list[dict[str, Any]]:
        if not items:
            return []

        self.metrics.pages_requested = len(items)
        if self._page_crawl_started_at is None:
            self._page_crawl_started_at = perf_counter()

        results: list[dict[str, Any] | None] = [None] * len(items)
        completed = 0
        progress_lock = asyncio.Lock()

        async def _fetch_indexed(index: int, url: str, discovery_reason: str) -> None:
            nonlocal completed
            fetch = await self.fetch_http(url, context="page")
            try:
                page = build_page(url, fetch)
            except Exception as exc:  # noqa: BLE001 - single page must not fail run
                logger.debug("page_parse_failed", extra={"url": url, "error": str(exc)})
                page = build_page(url, HttpFetchResult(url=url, status_code=None, content=None, content_type="", error=str(exc)))
            page["discovery_reason"] = discovery_reason
            results[index] = page
            async with progress_lock:
                if page.get("status") == "error":
                    self.metrics.pages_failed += 1
                else:
                    self.metrics.pages_completed += 1
                completed += 1
                active = self.metrics.pages_in_flight
                if on_progress is not None:
                    await on_progress(completed, len(items), active)

        await asyncio.gather(*[_fetch_indexed(i, url, reason) for i, (url, reason) in enumerate(items)])

        if self._page_crawl_started_at is not None:
            self.metrics.page_crawl_duration_seconds += perf_counter() - self._page_crawl_started_at
            self._page_crawl_started_at = None

        self.metrics.crawl_duration_seconds = (
            self.metrics.sitemap_fetch_duration_seconds + self.metrics.page_crawl_duration_seconds
        )
        return [page for page in results if page is not None]
