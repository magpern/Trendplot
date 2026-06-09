"""Crawl budget: selection vs scrape limits for sitemap-driven site crawls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass(frozen=True, slots=True)
class CrawlBudget:
    useful_url_count: int
    selection_limit: int
    crawl_limit: int
    small_site_full_crawl: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "useful_url_count": self.useful_url_count,
            "selection_limit": self.selection_limit,
            "crawl_limit": self.crawl_limit,
            "small_site_full_crawl": self.small_site_full_crawl,
        }


def resolve_crawl_budget(
    *,
    useful_url_count: int,
    max_pages: int,
    settings: Settings,
) -> CrawlBudget:
    """Derive how many URLs to select from sitemap ranking vs how many to scrape."""
    cap = max(1, int(max_pages))
    threshold = max(1, int(settings.crawl_small_site_full_threshold))
    sample_limit = max(cap, int(settings.crawl_large_site_sample_limit))
    useful = max(0, int(useful_url_count))

    if useful <= threshold:
        limit = max(useful, 1)
        return CrawlBudget(
            useful_url_count=useful,
            selection_limit=limit,
            crawl_limit=limit if useful else cap,
            small_site_full_crawl=True,
        )

    selection_limit = min(useful, sample_limit) if useful else cap
    return CrawlBudget(
        useful_url_count=useful,
        selection_limit=selection_limit,
        crawl_limit=cap,
        small_site_full_crawl=False,
    )
