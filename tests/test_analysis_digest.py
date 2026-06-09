from __future__ import annotations

import json

from app.analysis_digest import build_website_analysis_digest
from app.analysis_prompts import build_website_analysis_prompt


def _sample_page(url: str, title: str, *, content_type: str = "product") -> dict:
    return {
        "url": url,
        "status": "ok",
        "title": title,
        "content_type": content_type,
        "h1": [title],
        "h2": ["Mechanism", "Research context", "Quality standards"],
        "entities": ["BPC-157", "TB-500", "Peptides"],
        "questions": ["How is BPC-157 used in research?"],
        "navigation_links": [{"text": "Cart", "url": url}],
        "commercial_links": [],
    }


def test_build_website_analysis_digest_is_smaller_than_full_crawl():
    fat_page = _sample_page("https://www.example.com/shop/bpc-157/", "BPC-157 Research Peptide")
    fat_page["navigation_links"] = [{"text": f"Link {i}", "url": f"https://www.example.com/p/{i}"} for i in range(40)]
    fat_page["text_sample"] = "word " * 3000
    fat_page["headings"] = [{"level": "h2", "text": f"Heading {i}"} for i in range(20)]
    website = {
        "url": "https://www.example.com/",
        "pages": [
            fat_page,
            _sample_page("https://www.example.com/faq/", "FAQ", content_type="faq"),
            _sample_page("https://www.example.com/cart/", "Cart", content_type="utility"),
        ],
    }
    full_size = len(json.dumps({"website": website, "competitors": []}))
    digest = build_website_analysis_digest(website, [])
    digest_size = len(json.dumps(digest))
    assert digest_size < full_size * 0.35
    assert digest["website"]["pages_analyzed"] == 2
    assert "BPC-157" in digest["website"]["rollup"]["top_entities"]


def test_build_website_analysis_prompt_is_extraction_phase():
    website = {"url": "https://example.com/", "pages": [_sample_page("https://example.com/p", "BPC-157")]}
    prompt = build_website_analysis_prompt(website, [])
    assert "What kind of site" in prompt or "what kind of site" in prompt.lower()
    assert "Do NOT generate article ideas" in prompt
    assert "navigation_links" not in prompt
