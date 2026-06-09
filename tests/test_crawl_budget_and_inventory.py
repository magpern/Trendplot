from __future__ import annotations

from app.analyze_flow import (
    _sitemap_message,
    _website_crawl_message,
    _website_crawl_progress_label,
)
from app.config import Settings
from app.content_inventory import (
    find_inventory_match,
    inventory_item_from_page,
    inventory_item_from_trendplot_publish,
    is_editorial_inventory_item,
    topic_fingerprint,
)
from app.crawl_budget import resolve_crawl_budget
from app.sitemap_discovery import rank_sitemap_urls, select_sitemap_urls, SitemapEntry


def test_small_site_crawl_budget_selects_all_useful_urls() -> None:
    settings = Settings(MAX_PAGES_PER_SITE=30, CRAWL_SMALL_SITE_FULL_THRESHOLD=50)
    budget = resolve_crawl_budget(useful_url_count=39, max_pages=30, settings=settings)
    assert budget.small_site_full_crawl is True
    assert budget.selection_limit == 39
    assert budget.crawl_limit == 39


def test_large_site_crawl_budget_caps_crawl() -> None:
    settings = Settings(
        MAX_PAGES_PER_SITE=30,
        CRAWL_SMALL_SITE_FULL_THRESHOLD=50,
        CRAWL_LARGE_SITE_SAMPLE_LIMIT=100,
    )
    budget = resolve_crawl_budget(useful_url_count=80, max_pages=30, settings=settings)
    assert budget.small_site_full_crawl is False
    assert budget.selection_limit == 80
    assert budget.crawl_limit == 30


def test_select_sitemap_urls_respects_selection_limit() -> None:
    entries = [SitemapEntry(f"https://example.com/page-{index}/") for index in range(60)]
    ranked = rank_sitemap_urls("https://example.com/", entries)
    assert len(ranked) >= 60
    capped = ranked[:30]
    assert len(capped) == 30


def test_crawl_ui_messages_show_skipped_by_cap() -> None:
    discovery = {
        "sitemap_urls_selected": 39,
        "urls_crawled": 30,
        "urls_skipped_by_cap": 9,
        "useful_url_count": 39,
    }
    assert "9 skipped" in _website_crawl_message(discovery, 30)
    assert "30 of 39" in _website_crawl_progress_label(discovery, 30)


def test_sitemap_message_useful_urls() -> None:
    discovery = {"useful_url_count": 39, "sitemap_urls_selected": 39, "sitemap_urls_discovered": 120}
    assert "Found 39 useful URL" in _sitemap_message(discovery)


def test_inventory_item_from_crawled_page() -> None:
    page = {
        "url": "https://example.com/peptide-guide/",
        "canonical_url": "https://example.com/peptide-guide/",
        "title": "Peptide Reconstitution Guide",
        "content_type": "article",
        "entities": [{"name": "BPC-157"}],
    }
    item = inventory_item_from_page(page, workspace_id="ws-1")
    assert item["workspace_id"] == "ws-1"
    assert item["slug"] == "peptide-guide"
    assert item["topic_fingerprint"]
    assert "BPC-157" in item["coverage_topics"]


def test_trendplot_generated_inventory_item() -> None:
    item = inventory_item_from_trendplot_publish(
        workspace_id="ws-1",
        job_id="job-1",
        title="Peptide Reconstitution Guide",
        url="https://example.com/peptide-reconstitution-guide/",
        wordpress_post_id="42",
    )
    assert item["created_by_trendplot"] is True
    assert item["source"] == "trendplot_generated"
    assert item["generated_job_id"] == "job-1"


def test_duplicate_topic_detected_in_inventory() -> None:
    inventory = [
        inventory_item_from_trendplot_publish(
            workspace_id="ws-1",
            job_id="job-1",
            title="Peptide Reconstitution Guide",
            url="https://example.com/peptide-reconstitution-guide/",
            wordpress_post_id="42",
        )
    ]
    match = find_inventory_match(
        topic="Peptide Reconstitution Guide",
        title="Peptide Reconstitution Guide",
        target_keyword="peptide reconstitution guide",
        inventory=inventory,
    )
    assert match.kind == "duplicate"


def test_related_follow_up_allowed() -> None:
    inventory = [
        inventory_item_from_page(
            {
                "url": "https://example.com/peptide-guide/",
                "title": "Peptide Reconstitution Guide",
                "content_type": "article",
            },
            workspace_id="ws-1",
        )
    ]
    match = find_inventory_match(
        topic="Peptide Storage Best Practices",
        title="How to Store Peptides After Reconstitution",
        target_keyword="peptide storage",
        inventory=inventory,
    )
    assert match.kind in {"none", "related"}


def test_product_page_does_not_block_editorial_create() -> None:
    inventory = [
        inventory_item_from_page(
            {
                "url": "https://example.com/products/peptide-kit/",
                "title": "Peptide Research Kit",
                "content_type": "product",
            },
            workspace_id="ws-1",
        )
    ]
    assert is_editorial_inventory_item(inventory[0]) is False
    match = find_inventory_match(
        topic="Peptide Reconstitution Guide",
        title="Peptide Reconstitution Guide",
        target_keyword="peptide reconstitution",
        inventory=inventory,
    )
    assert match.kind == "none"


def test_topic_fingerprint_stable() -> None:
    first = topic_fingerprint(title="Peptide Guide", url="https://example.com/peptide-guide/")
    second = topic_fingerprint(title="Peptide Guide", url="https://example.com/peptide-guide/")
    assert first == second
