from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.catalog.products import build_catalog_products, product_name_from_url
from app.config import Settings
from app.sitemap_discovery import FetchedResource, SitemapDiscoveryService, normalize_url

_PRODUCT_PATH_MARKERS = frozenset({"product", "products"})


def products_from_sitemap_urls(urls: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for url in urls:
        name = product_name_from_url(url)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _product_sitemap_urls(urls: list[str]) -> list[str]:
    product_urls: list[str] = []
    for url in urls:
        segments = [segment for segment in urlparse(url).path.strip("/").split("/") if segment]
        if len(segments) >= 2 and segments[-2].lower() in _PRODUCT_PATH_MARKERS:
            product_urls.append(normalize_url(url))
    return product_urls


def _urls_from_url_discovery_artifact(content: dict[str, Any] | None) -> list[str]:
    if not isinstance(content, dict):
        return []
    website = content.get("website") if isinstance(content.get("website"), dict) else content
    urls: list[str] = []
    for key in ("selected_urls", "skipped_by_cap_examples"):
        rows = website.get(key) or []
        for row in rows:
            if isinstance(row, dict):
                url = str(row.get("url") or "").strip()
            else:
                url = str(row).strip()
            if url:
                urls.append(url)
    return urls


async def _httpx_fetch(url: str) -> FetchedResource | None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            return None
        return FetchedResource(
            url=str(response.url),
            content=response.content,
            content_type=response.headers.get("content-type", ""),
        )


async def discover_sitemap_catalog_products(
    website_url: str,
    *,
    settings: Settings,
    url_discovery_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Product names from sitemap product URLs (live fetch, with artifact fallback)."""
    artifact_urls = _product_sitemap_urls(_urls_from_url_discovery_artifact(url_discovery_artifact))
    live_urls: list[str] = []
    meta: dict[str, Any] = {
        "source": "artifact_only" if artifact_urls else "none",
        "sitemap_urls_discovered": 0,
        "product_urls_found": len(artifact_urls),
    }

    if settings.sitemap_discovery_enabled and website_url:
        service = SitemapDiscoveryService(
            enabled=True,
            max_urls_to_parse=5000,
            max_sitemaps_to_parse=20,
            fetch_resource=_httpx_fetch,
        )
        result = await service.discover(
            website_url,
            max_pages=500,
            selection_limit=500,
        )
        live_urls = _product_sitemap_urls([item.url for item in result.selected_urls])
        meta.update(
            {
                "source": "live_sitemap",
                "sitemap_urls_discovered": result.sitemap_urls_discovered,
                "sitemap_urls_selected": result.sitemap_urls_selected,
                "product_urls_found": len(live_urls),
            }
        )

    merged_urls = list(dict.fromkeys([*live_urls, *artifact_urls]))
    raw_names = products_from_sitemap_urls(merged_urls)
    catalog = build_catalog_products(
        sitemap_products=raw_names,
        product_urls=merged_urls,
    )
    return {
        **meta,
        "product_urls": merged_urls,
        "product_names": catalog,
    }
