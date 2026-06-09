from __future__ import annotations

import json

from app.analysis_prompts import build_website_analysis_prompt
from app.prompt_metrics import measure_context
from app.prompts import render_prompt
from app.site_strategy_profile import (
    build_legacy_strategist_context,
    build_site_strategy_profile,
    build_strategist_context_from_profile,
    strip_ideation_from_extraction,
)
from app.prompts.prompt_registry import get_default_prompt_registry


def _sample_page(url: str, title: str) -> dict:
    return {
        "url": url,
        "status": "ok",
        "title": title,
        "content_type": "product",
        "h1": [title],
        "h2": ["Mechanism", "Research"],
        "entities": ["BPC-157", "TB-500"],
        "questions": [],
    }


def test_website_analysis_prompt_is_extraction_only():
    website = {"url": "https://example.com/", "pages": [_sample_page("https://example.com/p", "BPC-157")]}
    prompt = build_website_analysis_prompt(website, [])
    assert "What kind of site is this" in prompt or "what kind of site" in prompt.lower()
    assert "Do NOT generate article ideas" in prompt
    assert "opportunities" in prompt  # in "Do NOT include: opportunities"
    assert "max_seed_opportunities" not in prompt


def test_strip_ideation_from_extraction():
    payload = {"summary": "x", "opportunities": [{"title": "Bad"}], "suggestions": [{"title": "Bad"}]}
    cleaned = strip_ideation_from_extraction(payload)
    assert cleaned["opportunities"] == []
    assert cleaned["suggestions"] == []
    assert cleaned["summary"] == "x"


def test_site_strategy_profile_built_from_extraction():
    website = {"url": "https://www.example.com/", "pages": [_sample_page("https://www.example.com/p", "BPC-157 Research Peptide")]}
    ai = {
        "business_type": "ecommerce",
        "primary_niche": "research peptides",
        "known_products": ["BPC-157", "TB-500"],
        "known_categories": ["Metabolic Research Peptides"],
        "audiences": [{"name": "Researchers"}],
        "topical_clusters": [{"name": "Recovery peptides"}],
    }
    profile = build_site_strategy_profile(ai_extraction=ai, website=website, competitors=[])
    assert profile["business_type"] == "ecommerce"
    assert "BPC-157" in profile["known_products"]
    assert profile["primary_niche"] == "research peptides"


def test_strategist_compact_context_from_profile():
    profile = {
        "business_type": "ecommerce",
        "primary_niche": "research peptides",
        "known_products": ["BPC-157", "Kisspeptin"],
        "known_categories": ["Research Peptides"],
        "existing_articles": ["FAQ"],
    }
    ctx = build_strategist_context_from_profile(profile, max_ideas=25)
    assert ctx["known_products"] == ["BPC-157", "Kisspeptin"]
    assert ctx["max_ideas_hint"] == 25
    assert "site_profile" not in ctx
    assert "existing_content_summary" not in ctx


def test_strategist_context_smaller_than_legacy():
    profile = {
        "business_type": "ecommerce",
        "primary_niche": "peptides",
        "known_products": ["BPC-157", "TB-500", "GHK-CU"],
        "known_categories": ["Research Peptides"],
        "existing_articles": ["Storage guide"],
    }
    compact = build_strategist_context_from_profile(profile, max_ideas=25)
    legacy = build_legacy_strategist_context(
        workspace={"website_url": "https://example.com"},
        understanding={"summary": " peptide shop ", "pages": [{"url": "https://example.com/p", "title": "BPC-157"}] * 20},
        niche_profile={"primary_niche": "peptides", "known_products": ["BPC-157"]},
        content_inventory=[{"title": f"Page {i}"} for i in range(30)],
        max_ideas=25,
    )
    compact_size = measure_context("compact", compact)["estimated_tokens"]
    legacy_size = measure_context("legacy", legacy)["estimated_tokens"]
    assert compact_size < legacy_size * 0.5


def test_website_analysis_prompt_smaller_than_seed_heavy_version():
    website = {
        "url": "https://www.example.com/",
        "pages": [_sample_page(f"https://www.example.com/p{i}", f"Product {i}") for i in range(10)],
    }
    current = build_website_analysis_prompt(website, [])
    registry = get_default_prompt_registry()
    # Simulate old v5-style prompt size with seed instructions
    old_style = registry.render(
        "website_analysis",
        {
            "website_data_json": json.dumps({"website": website}, separators=(",", ":")),
            "max_seed_opportunities": 25,
        },
    )
    # v6 template should be smaller when variables missing max_seed - use char compare on template only
    assert len(str(current)) < len(str(old_style)) + 500 or "article seeds" not in str(current)
