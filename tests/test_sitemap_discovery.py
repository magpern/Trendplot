from __future__ import annotations

import asyncio
import gzip
from types import SimpleNamespace
from typing import Any

from app.config import Settings
from app.sitemap_discovery import (
    FetchedResource,
    SitemapDiscoveryResult,
    SitemapDiscoveryService,
    SitemapEntry,
    SelectedSitemapUrl,
    normalize_content_url,
    parse_sitemap_resource,
    select_sitemap_urls,
)
from app.website_analysis import WebsiteAnalysisService


def _resource(url: str, content: str | bytes, content_type: str = "application/xml") -> FetchedResource:
    body = content if isinstance(content, bytes) else content.encode("utf-8")
    return FetchedResource(url=url, content=body, content_type=content_type)


def _fetcher(resources: dict[str, FetchedResource | None], seen: list[str] | None = None):
    async def fetch(url: str) -> FetchedResource | None:
        if seen is not None:
            seen.append(url)
        return resources.get(url)

    return fetch


def _discover(resources: dict[str, FetchedResource | None], start_url: str = "https://example.com/"):
    service = SitemapDiscoveryService(fetch_resource=_fetcher(resources))
    return asyncio.run(service.discover(start_url, max_pages=10))


def test_robots_txt_sitemap_discovery():
    result = _discover(
        {
            "https://example.com/robots.txt": _resource(
                "https://example.com/robots.txt",
                "User-agent: *\nSitemap: https://example.com/sitemap.xml\n",
                "text/plain",
            ),
            "https://example.com/sitemap.xml": _resource(
                "https://example.com/sitemap.xml",
                '<urlset><url><loc>https://example.com/about/</loc></url></urlset>',
            ),
        }
    )
    assert result.robots_txt_checked is True
    assert result.sitemap_urls_found == 1
    assert any(item.url == "https://example.com/about/" for item in result.selected_urls)


def test_common_sitemap_fallback_discovery():
    seen: list[str] = []
    service = SitemapDiscoveryService(
        fetch_resource=_fetcher(
            {
                "https://example.com/robots.txt": _resource("https://example.com/robots.txt", "User-agent: *", "text/plain"),
                "https://example.com/sitemap.xml": _resource(
                    "https://example.com/sitemap.xml",
                    '<urlset><url><loc>https://example.com/services/</loc></url></urlset>',
                ),
            },
            seen,
        )
    )
    result = asyncio.run(service.discover("https://example.com/", max_pages=10))
    assert "https://example.com/sitemap.xml" in seen
    assert any(item.url == "https://example.com/services/" for item in result.selected_urls)


def test_sitemap_index_parsing_recurses():
    result = _discover(
        {
            "https://example.com/robots.txt": _resource(
                "https://example.com/robots.txt",
                "Sitemap: https://example.com/sitemap_index.xml",
                "text/plain",
            ),
            "https://example.com/sitemap_index.xml": _resource(
                "https://example.com/sitemap_index.xml",
                "<sitemapindex><sitemap><loc>https://example.com/pages.xml</loc></sitemap></sitemapindex>",
            ),
            "https://example.com/pages.xml": _resource(
                "https://example.com/pages.xml",
                '<urlset><url><loc>https://example.com/company/</loc></url></urlset>',
            ),
        }
    )
    assert result.sitemap_files_parsed == 2
    assert any(item.url == "https://example.com/company/" for item in result.selected_urls)


def test_urlset_parsing_extracts_loc_and_lastmod():
    parsed = parse_sitemap_resource(
        _resource(
            "https://example.com/sitemap.xml",
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://example.com/blog/a/</loc><lastmod>2026-05-01</lastmod></url>
            </urlset>
            """,
        )
    )
    assert parsed is not None
    assert parsed["urls"][0].url == "https://example.com/blog/a/"
    assert parsed["urls"][0].lastmod == "2026-05-01"


def test_gzip_sitemap_parsing():
    content = gzip.compress(b'<urlset><url><loc>https://example.com/blog/gzip/</loc></url></urlset>')
    parsed = parse_sitemap_resource(_resource("https://example.com/sitemap.xml.gz", content, "application/x-gzip"))
    assert parsed is not None
    assert parsed["urls"][0].url == "https://example.com/blog/gzip/"


def test_malformed_xml_fails_gracefully():
    result = _discover(
        {
            "https://example.com/robots.txt": _resource("https://example.com/robots.txt", "Sitemap: https://example.com/sitemap.xml"),
            "https://example.com/sitemap.xml": _resource("https://example.com/sitemap.xml", "<urlset><url>"),
        }
    )
    assert result.sitemap_files_parsed == 0
    assert result.skipped_url_counts_by_reason["malformed_sitemap"] == 1


def test_duplicate_url_handling():
    result = _discover(
        {
            "https://example.com/robots.txt": _resource("https://example.com/robots.txt", "Sitemap: https://example.com/sitemap.xml"),
            "https://example.com/sitemap.xml": _resource(
                "https://example.com/sitemap.xml",
                """
                <urlset>
                  <url><loc>https://example.com/products/widget/?utm_source=x</loc></url>
                  <url><loc>https://example.com/products/widget/</loc></url>
                </urlset>
                """,
            ),
        }
    )
    urls = [item.url for item in result.selected_urls]
    assert urls.count("https://example.com/products/widget/") == 1


def test_url_filtering_skips_non_content_urls():
    skipped: dict[str, int] = {}
    selected = select_sitemap_urls(
        "https://example.com/",
        [
            SitemapEntry("https://other.example.com/about/"),
            SitemapEntry("https://example.com/cart/"),
            SitemapEntry("https://example.com/wp-admin/edit.php"),
            SitemapEntry("https://example.com/tag/news/"),
            SitemapEntry("https://example.com/?s=shoes"),
            SitemapEntry("https://example.com/about/?utm_source=newsletter"),
        ],
        max_pages=10,
        skipped_url_counts=skipped,
    )
    assert "https://example.com/about/" in [item.url for item in selected]
    assert skipped["external_domain"] == 1
    assert skipped["commerce_utility"] == 1
    assert skipped["admin"] == 1
    assert skipped["tag_archive"] == 1
    assert skipped["search_page"] == 1
    assert normalize_content_url("https://example.com/feed/", "https://example.com/")[1] == "feed"


def test_selection_ranking_prefers_representative_pages():
    selected = select_sitemap_urls(
        "https://example.com/",
        [
            SitemapEntry("https://example.com/privacy-policy/"),
            SitemapEntry("https://example.com/blog/old-post/", "2020-01-01"),
            SitemapEntry("https://example.com/products/widget/"),
            SitemapEntry("https://example.com/support/"),
            SitemapEntry("https://example.com/about/"),
        ],
        max_pages=5,
        skipped_url_counts={},
    )
    urls = [item.url for item in selected]
    assert urls[:4] == [
        "https://example.com/",
        "https://example.com/about/",
        "https://example.com/support/",
        "https://example.com/products/widget/",
    ]
    assert all("privacy" not in url for url in urls)


def test_fallback_to_crawl_if_no_sitemap_found():
    class _Service(WebsiteAnalysisService):
        async def _discover_sitemap_urls(self, normalized_start: str, max_pages: int, **kwargs: Any) -> SitemapDiscoveryResult:
            return SitemapDiscoveryResult(sitemap_discovery_enabled=True)

        def _build_page_from_fetch(self, url: str, fetch: Any) -> dict[str, Any]:
            if url == "https://example.com/":
                return {
                    "url": url,
                    "status": "ok",
                    "title": "Home",
                    "meta_description": "",
                    "canonical_url": "",
                    "headings": [],
                    "commercial_links": [{"text": "Services", "url": "https://example.com/services/"}],
                    "navigation_links": [],
                    "questions": [],
                    "entities": [],
                    "text_sample": "",
                }
            return {
                "url": url,
                "status": "ok",
                "title": "Services",
                "meta_description": "",
                "canonical_url": "",
                "headings": [],
                "commercial_links": [],
                "navigation_links": [],
                "questions": [],
                "entities": [],
                "text_sample": "",
            }

    service = _Service(content_provider=object(), settings=Settings(CRAWL_FALLBACK_ENABLED=True, SITEMAP_DISCOVERY_ENABLED=True))
    site = asyncio.run(service._fetch_site("https://example.com", 3))
    assert site["url_discovery"]["crawl_fallback_used"] is True
    assert [page["url"] for page in site["pages"]] == ["https://example.com/", "https://example.com/services/"]


def test_wordpress_sitemap_path_is_tried():
    seen: list[str] = []
    service = SitemapDiscoveryService(
        fetch_resource=_fetcher(
            {
                "https://example.com/robots.txt": _resource("https://example.com/robots.txt", "User-agent: *", "text/plain"),
                "https://example.com/wp-sitemap.xml": _resource(
                    "https://example.com/wp-sitemap.xml",
                    '<urlset><url><loc>https://example.com/blog/wp-post/</loc></url></urlset>',
                ),
            },
            seen,
        )
    )
    result = asyncio.run(service.discover("https://example.com/", max_pages=10))
    assert "https://example.com/wp-sitemap.xml" in seen
    assert any(item.url == "https://example.com/blog/wp-post/" for item in result.selected_urls)
