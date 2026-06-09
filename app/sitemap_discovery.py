from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import httpx

logger = logging.getLogger("trendplot.sitemap_discovery")

if TYPE_CHECKING:
    from app.concurrent_crawl import CrawlHttpClient

COMMON_SITEMAP_PATHS = (
    "/sitemap_index.xml",
    "/sitemap.xml",
    "/wp-sitemap.xml",
    "/page-sitemap.xml",
    "/post-sitemap.xml",
    "/product-sitemap.xml",
)

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "msclkid",
}

PATH_SKIP_PATTERNS: tuple[tuple[str, str], ...] = (
    ("wp-admin", "admin"),
    ("wp-login", "account_login"),
    ("login", "account_login"),
    ("account", "account_login"),
    ("cart", "commerce_utility"),
    ("basket", "commerce_utility"),
    ("checkout", "commerce_utility"),
    ("feed", "feed"),
    ("/tag/", "tag_archive"),
    ("/tags/", "tag_archive"),
    ("/search", "search_page"),
    ("?s=", "search_page"),
    ("privacy", "legal_utility"),
    ("cookie", "legal_utility"),
    ("terms", "legal_utility"),
    ("/page/", "paginated_archive"),
)

FetchResource = Callable[[str], Awaitable["FetchedResource | None"]]
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class FetchedResource:
    url: str
    content: bytes
    content_type: str = ""


@dataclass(slots=True)
class SitemapEntry:
    url: str
    lastmod: str = ""


@dataclass(slots=True)
class SelectedSitemapUrl:
    url: str
    reason: str
    lastmod: str = ""
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "reason": self.reason,
            "lastmod": self.lastmod,
            "score": round(self.score, 3),
        }


@dataclass(slots=True)
class SitemapDiscoveryResult:
    sitemap_discovery_enabled: bool
    robots_txt_checked: bool = False
    sitemap_urls_found: int = 0
    sitemap_files_parsed: int = 0
    sitemap_urls_discovered: int = 0
    sitemap_urls_selected: int = 0
    useful_url_count: int = 0
    crawl_fallback_used: bool = False
    crawl_budget: dict[str, Any] = field(default_factory=dict)
    skipped_url_counts_by_reason: dict[str, int] = field(default_factory=dict)
    selected_urls: list[SelectedSitemapUrl] = field(default_factory=list)
    sitemap_files: list[str] = field(default_factory=list)

    def metrics(self) -> dict[str, Any]:
        return {
            "sitemap_discovery_enabled": self.sitemap_discovery_enabled,
            "robots_txt_checked": self.robots_txt_checked,
            "sitemap_urls_found": self.sitemap_urls_found,
            "sitemap_files_parsed": self.sitemap_files_parsed,
            "sitemap_urls_discovered": self.sitemap_urls_discovered,
            "sitemap_urls_selected": self.sitemap_urls_selected,
            "useful_url_count": self.useful_url_count,
            "crawl_fallback_used": self.crawl_fallback_used,
            "crawl_budget": dict(self.crawl_budget),
            "skipped_url_counts_by_reason": dict(self.skipped_url_counts_by_reason),
            "selected_urls": [item.as_dict() for item in self.selected_urls],
        }


class SitemapDiscoveryService:
    def __init__(
        self,
        *,
        enabled: bool = True,
        max_urls_to_parse: int = 5000,
        max_sitemaps_to_parse: int = 50,
        allow_external_domains: bool = False,
        fetch_resource: FetchResource | None = None,
        progress_callback: ProgressCallback | None = None,
        crawl_client: CrawlHttpClient | None = None,
    ) -> None:
        self.enabled = enabled
        self.max_urls_to_parse = max(1, max_urls_to_parse)
        self.max_sitemaps_to_parse = max(1, max_sitemaps_to_parse)
        self.allow_external_domains = allow_external_domains
        self._fetch_resource = fetch_resource
        self._progress_callback = progress_callback
        self._crawl_client = crawl_client
        self._sitemap_concurrency = (
            max(1, crawl_client.settings.concurrency_per_domain) if crawl_client is not None else 1
        )

    async def discover(self, start_url: str, *, max_pages: int, selection_limit: int | None = None) -> SitemapDiscoveryResult:
        normalized_start = normalize_url(start_url)
        result = SitemapDiscoveryResult(sitemap_discovery_enabled=self.enabled)
        if not self.enabled:
            return result

        await self._emit(
            {
                "step": "sitemap_discovery",
                "message": "Checking robots.txt",
                "details": {"robots_txt_checked": False},
            }
        )
        sitemap_candidates = await self._discover_sitemap_files(normalized_start, result)
        await self._emit(
            {
                "step": "sitemap_discovery",
                "message": f"Found {len(sitemap_candidates)} sitemap URL(s)",
                "progress_current": len(sitemap_candidates),
                "details": {
                    "robots_txt_checked": result.robots_txt_checked,
                    "sitemap_urls_found": len(sitemap_candidates),
                },
            }
        )
        result.sitemap_files = sitemap_candidates[: self.max_sitemaps_to_parse]
        entries = await self._parse_sitemap_files(normalized_start, sitemap_candidates, result)
        ranked = rank_sitemap_urls(
            normalized_start,
            entries,
            skipped_url_counts=result.skipped_url_counts_by_reason,
            allow_external_domains=self.allow_external_domains,
        )
        result.useful_url_count = len(ranked)
        limit = selection_limit if selection_limit is not None else max_pages
        selected = ranked[: max(1, limit)]
        result.selected_urls = selected
        result.sitemap_urls_selected = len(selected)
        await self._emit(
            {
                "step": "sitemap_discovery",
                "status": "succeeded" if len(selected) else "warning",
                "message": _sitemap_selection_message(
                    useful_count=result.useful_url_count,
                    selected_count=len(selected),
                    discovered_count=result.sitemap_urls_discovered,
                ),
                "progress_current": len(selected),
                "progress_total": result.sitemap_urls_discovered,
                "progress_label": f"Selected {len(selected)} of {result.sitemap_urls_discovered}",
                "details": {
                    "robots_txt_checked": result.robots_txt_checked,
                    "sitemap_urls_found": result.sitemap_urls_found,
                    "sitemap_files_parsed": result.sitemap_files_parsed,
                    "sitemap_urls_discovered": result.sitemap_urls_discovered,
                    "sitemap_urls_selected": result.sitemap_urls_selected,
                    "crawl_fallback_used": result.crawl_fallback_used,
                    "skipped_url_counts_by_reason": dict(result.skipped_url_counts_by_reason),
                },
            }
        )
        return result

    async def _discover_sitemap_files(
        self,
        start_url: str,
        result: SitemapDiscoveryResult,
    ) -> list[str]:
        robots_url = urljoin(origin_for(start_url), "/robots.txt")
        result.robots_txt_checked = True
        sitemap_urls: list[str] = []
        robots = await self._fetch(robots_url)
        if robots is not None:
            sitemap_urls.extend(parse_robots_sitemaps(decode_content(robots)))

        if not sitemap_urls:
            sitemap_urls.extend(urljoin(origin_for(start_url), path) for path in COMMON_SITEMAP_PATHS)

        normalized: list[str] = []
        seen: set[str] = set()
        for url in sitemap_urls:
            normalized_url = normalize_url(url)
            if not self.allow_external_domains and not same_domain(normalized_url, start_url):
                _increment(result.skipped_url_counts_by_reason, "external_sitemap")
                continue
            if normalized_url in seen:
                continue
            seen.add(normalized_url)
            normalized.append(normalized_url)
        return normalized

    async def _parse_sitemap_files(
        self,
        start_url: str,
        sitemap_urls: list[str],
        result: SitemapDiscoveryResult,
    ) -> list[SitemapEntry]:
        queue = list(sitemap_urls)
        visited: set[str] = set()
        entries: list[SitemapEntry] = []

        while queue and len(visited) < self.max_sitemaps_to_parse and len(entries) < self.max_urls_to_parse:
            batch: list[str] = []
            while (
                queue
                and len(batch) < self._sitemap_concurrency
                and len(visited) + len(batch) < self.max_sitemaps_to_parse
            ):
                candidate = queue.pop(0)
                if candidate in visited:
                    continue
                batch.append(candidate)

            if not batch:
                break

            await self._emit(
                {
                    "step": "sitemap_discovery",
                    "message": f"Fetching {len(batch)} sitemap file(s)",
                    "progress_current": len(visited),
                    "progress_total": min(len(sitemap_urls), self.max_sitemaps_to_parse),
                    "progress_label": f"Fetching {len(batch)} sitemap(s)",
                    "details": {"sitemap_batch_size": len(batch), "sitemap_files_parsed": result.sitemap_files_parsed},
                }
            )

            if self._crawl_client is not None:
                fetch_results = await self._crawl_client.fetch_sitemap_resources_ordered(batch)
                resources = [
                    (
                        url,
                        FetchedResource(
                            url=fetch.url,
                            content=fetch.content,
                            content_type=fetch.content_type,
                        )
                        if fetch is not None and fetch.content is not None
                        else None,
                    )
                    for url, fetch in zip(batch, fetch_results)
                ]
            else:
                resources = [(url, await self._fetch(url)) for url in batch]

            for sitemap_url, resource in resources:
                if sitemap_url in visited:
                    continue
                visited.add(sitemap_url)
                await self._emit(
                    {
                        "step": "sitemap_discovery",
                        "message": f"Parsing {urlparse(sitemap_url).path or sitemap_url}",
                        "progress_current": len(visited),
                        "progress_total": min(len(sitemap_urls), self.max_sitemaps_to_parse),
                        "progress_label": f"Parsing sitemap {len(visited)}",
                        "details": {
                            "current_sitemap_url": sitemap_url,
                            "sitemap_files_parsed": result.sitemap_files_parsed,
                        },
                    }
                )
                if resource is None:
                    _increment(result.skipped_url_counts_by_reason, "sitemap_fetch_failed")
                    continue
                result.sitemap_urls_found += 1
                parsed = parse_sitemap_resource(resource)
                if parsed is None:
                    _increment(result.skipped_url_counts_by_reason, "malformed_sitemap")
                    continue
                result.sitemap_files_parsed += 1
                await self._emit(
                    {
                        "step": "sitemap_discovery",
                        "message": f"Parsed {urlparse(sitemap_url).path or sitemap_url}",
                        "progress_current": result.sitemap_files_parsed,
                        "progress_total": min(len(sitemap_urls), self.max_sitemaps_to_parse),
                        "details": {
                            "current_sitemap_url": sitemap_url,
                            "sitemap_files_parsed": result.sitemap_files_parsed,
                            "sitemap_urls_discovered": len(entries) + len(parsed["urls"]),
                        },
                    }
                )

                child_candidates: list[str] = []
                for child_sitemap in parsed["sitemaps"]:
                    normalized_child = normalize_url(child_sitemap.url)
                    if normalized_child in visited or normalized_child in queue or normalized_child in child_candidates:
                        continue
                    if not self.allow_external_domains and not same_domain(normalized_child, start_url):
                        _increment(result.skipped_url_counts_by_reason, "external_sitemap")
                        continue
                    if len(visited) + len(queue) + len(child_candidates) < self.max_sitemaps_to_parse:
                        child_candidates.append(normalized_child)
                queue.extend(sorted(child_candidates))

                for page in parsed["urls"]:
                    if len(entries) >= self.max_urls_to_parse:
                        break
                    entries.append(page)

        result.sitemap_urls_discovered = len(entries)
        return entries

    async def _emit(self, event: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        try:
            await self._progress_callback(event)
        except Exception:  # noqa: BLE001 - progress reporting must never affect discovery.
            logger.debug("sitemap_progress_callback_failed", exc_info=True)

    async def _fetch(self, url: str) -> FetchedResource | None:
        try:
            if self._fetch_resource is not None:
                return await self._fetch_resource(url)
            if self._crawl_client is not None:
                fetch = await self._crawl_client.fetch_http(url, context="sitemap")
                if fetch.content is None:
                    return None
                return FetchedResource(
                    url=fetch.url,
                    content=fetch.content,
                    content_type=fetch.content_type,
                )
            from app.concurrent_crawl import CRAWL_USER_AGENT

            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": CRAWL_USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return FetchedResource(
                    url=str(response.url),
                    content=response.content,
                    content_type=response.headers.get("content-type", ""),
                )
        except Exception as exc:  # noqa: BLE001 - sitemap discovery must fail back to crawl.
            logger.debug("sitemap_fetch_failed", extra={"url": url, "error_type": type(exc).__name__})
            return None


def parse_robots_sitemaps(content: str) -> list[str]:
    urls: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if sep and key.strip().lower() == "sitemap":
            sitemap_url = value.strip()
            if sitemap_url:
                urls.append(sitemap_url)
    return list(dict.fromkeys(urls))


def parse_sitemap_resource(resource: FetchedResource) -> dict[str, list[SitemapEntry]] | None:
    content = decode_content(resource)
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return None

    root_name = local_name(root.tag)
    sitemaps: list[SitemapEntry] = []
    urls: list[SitemapEntry] = []
    if root_name == "sitemapindex":
        for node in list(root):
            if local_name(node.tag) != "sitemap":
                continue
            loc = child_text(node, "loc")
            if loc:
                sitemaps.append(SitemapEntry(url=loc, lastmod=child_text(node, "lastmod")))
    elif root_name == "urlset":
        for node in list(root):
            if local_name(node.tag) != "url":
                continue
            loc = child_text(node, "loc")
            if loc:
                urls.append(SitemapEntry(url=loc, lastmod=child_text(node, "lastmod")))
    else:
        return None
    return {"sitemaps": sitemaps, "urls": urls}


def _sitemap_selection_message(*, useful_count: int, selected_count: int, discovered_count: int) -> str:
    if useful_count and useful_count == selected_count:
        return f"Found {useful_count} useful URL(s) from {discovered_count} discovered."
    if useful_count:
        return f"Selected {selected_count} of {useful_count} useful URL(s) ({discovered_count} discovered)."
    return f"Selected {selected_count} URLs from {discovered_count} discovered"


def rank_sitemap_urls(
    start_url: str,
    entries: list[SitemapEntry],
    *,
    skipped_url_counts: dict[str, int] | None = None,
    allow_external_domains: bool = False,
) -> list[SelectedSitemapUrl]:
    skipped = skipped_url_counts if skipped_url_counts is not None else {}
    candidates: dict[str, SitemapEntry] = {start_url: SitemapEntry(start_url)}
    for entry in entries:
        normalized, reason = normalize_content_url(
            entry.url,
            start_url,
            allow_external_domains=allow_external_domains,
        )
        if reason:
            _increment(skipped, reason)
            continue
        if normalized and normalized not in candidates:
            candidates[normalized] = SitemapEntry(normalized, entry.lastmod)

    ranked = [rank_url(start_url, entry) for entry in candidates.values()]
    ranked.sort(key=lambda item: (-item.score, item.url))
    return ranked


def select_sitemap_urls(
    start_url: str,
    entries: list[SitemapEntry],
    *,
    max_pages: int,
    skipped_url_counts: dict[str, int] | None = None,
    allow_external_domains: bool = False,
) -> list[SelectedSitemapUrl]:
    ranked = rank_sitemap_urls(
        start_url,
        entries,
        skipped_url_counts=skipped_url_counts,
        allow_external_domains=allow_external_domains,
    )
    return ranked[: max(1, max_pages)]


def rank_url(start_url: str, entry: SitemapEntry) -> SelectedSitemapUrl:
    parsed = urlparse(entry.url)
    path = parsed.path.lower().strip("/")
    segments = [segment for segment in path.split("/") if segment]
    score = 35.0
    reason = "evergreen content page"

    if normalize_url(entry.url) == normalize_url(start_url) or path == "":
        score = 100.0
        reason = "homepage"
    elif any(segment in {"about", "company", "team", "our-story"} for segment in segments):
        score = 90.0
        reason = "about/company page"
    elif any(segment in {"faq", "faqs", "help", "support", "docs", "documentation"} for segment in segments):
        score = 82.0
        reason = "FAQ/help/support page"
    elif any(segment in {"product", "products", "service", "services", "category", "collections", "solutions", "pricing"} for segment in segments):
        score = 74.0
        reason = "product/service/category page"
    elif any(segment in {"blog", "article", "articles", "guide", "guides", "resources", "learn"} for segment in segments):
        score = 64.0
        reason = "blog/article/guide page"
    elif any(segment in {"case-studies", "case-study", "customers", "use-cases"} for segment in segments):
        score = 58.0
        reason = "high-value evergreen page"

    recent_bonus = lastmod_recency_bonus(entry.lastmod)
    if recent_bonus:
        score += recent_bonus
        if reason == "blog/article/guide page":
            reason = "recent blog/article/guide page"
        elif reason == "evergreen content page":
            reason = "recent evergreen content page"

    return SelectedSitemapUrl(url=entry.url, reason=reason, lastmod=entry.lastmod, score=score)


def normalize_content_url(
    url: str,
    start_url: str,
    *,
    allow_external_domains: bool = False,
) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None, "non_http"
    if not parsed.netloc:
        url = urljoin(start_url, url)
        parsed = urlparse(url)
    if not allow_external_domains and not same_domain(url, start_url):
        return None, "external_domain"
    path_and_query = f"{parsed.path.lower()}?{parsed.query.lower()}"
    for pattern, reason in PATH_SKIP_PATTERNS:
        if pattern in path_and_query:
            return None, reason
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key.lower() in {"s", "q", "search"} for key, _value in query_pairs):
        return None, "search_page"
    if query_pairs and not all(key.lower() in TRACKING_QUERY_PARAMS for key, _value in query_pairs):
        return None, "query_string"
    return normalize_url(url), None


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    normalized = parsed._replace(
        scheme=scheme.lower(),
        netloc=netloc.lower(),
        path=path or "/",
        params="",
        query="",
        fragment="",
    )
    return urlunparse(normalized)


def same_domain(first_url: str, second_url: str) -> bool:
    return urlparse(normalize_url(first_url)).netloc == urlparse(normalize_url(second_url)).netloc


def origin_for(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def decode_content(resource: FetchedResource) -> str:
    content = resource.content
    content_type = resource.content_type.lower()
    if resource.url.lower().endswith(".gz") or "gzip" in content_type:
        try:
            content = gzip.decompress(content)
        except OSError:
            pass
    return content.decode("utf-8", errors="replace")


def child_text(node: ElementTree.Element, child_name: str) -> str:
    for child in list(node):
        if local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def lastmod_recency_bonus(value: str) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days
    if age_days <= 30:
        return 18.0
    if age_days <= 180:
        return 10.0
    if age_days <= 365:
        return 4.0
    return 0.0


def _increment(counts: dict[str, int], reason: str) -> None:
    counts[reason] = counts.get(reason, 0) + 1
