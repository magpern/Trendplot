from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai_opportunity_ideation.models import AIOpportunity
from app.ai_opportunity_ideation.parser import (
    brief_cache_key,
    loads_ideation_payload,
    merge_opportunity_lists,
    parse_opportunities_response,
    salvage_opportunities_payload,
)
from app.ai_opportunity_ideation.service import AIOpportunityIdeationService
from app.catalog.products import build_catalog_products, product_name_from_url, product_name_from_page_title
from app.config import Settings
from app.prompts import ArticlePromptInput, build_article_prompt
from app.prompts.prompt_registry import get_default_prompt_registry
from app.services.jobs import _opportunity_context_json


def test_catalog_extracts_products_from_urls_and_titles() -> None:
    assert product_name_from_url("https://shop.example/product/tb-500/") == "TB-500"
    assert product_name_from_url("https://shop.example/product/tirzepatide/") == "Tirzepatide"
    assert product_name_from_url("https://shop.example/product/cjc-1295-no-dac-ipa/") == "CJC-1295 No DAC + IPA"
    assert product_name_from_page_title("TB-500 | Example Lab") == "TB-500"

    catalog = build_catalog_products(
        sitemap_products=["BPC-157"],
        product_urls=[
            "https://shop.example/product/tb-500/",
            "https://shop.example/product/tirzepatide/",
            "https://shop.example/product/cjc-1295-no-dac-ipa/",
        ],
        inventory=[
            {"title": "Retatrutide Research Grade", "url": "https://shop.example/product/retatrutide/", "content_type": "product"},
        ],
    )
    assert "TB-500" in catalog
    assert "Tirzepatide" in catalog
    assert "CJC-1295 No DAC + IPA" in catalog
    assert "Retatrutide Research Grade" in catalog or "Retatrutide" in catalog


def test_prompt_contains_safety_constraints() -> None:
    rendered = get_default_prompt_registry().render(
        "ai_opportunity_ideation",
        {
            "opportunity_ideation_brief_json": "{}",
            "min_ideas": "40",
            "max_ideas": "75",
        },
    )
    text = str(rendered.text).lower()
    assert "no medical claims" in text
    assert "recommendation_type" in text
    assert "create" in text
    assert rendered.version == 4
    assert "science-first" in text
    assert "supplier listings" in text or "catalog pages" in text
    assert "theme_mix_targets" in text
    assert "4–5" not in text and "4-5" not in text
    assert "comparison or product-relationship" in text or "comparison or relationship" in text
    assert "mechanism" in text
    assert "product_relationship" in text
    assert "headlines vs ruo" in text or ("ruo" in text and "headline" in text and "labeling" in text)


def test_parser_warns_on_ruo_in_non_compliance_headline() -> None:
    payload = {
        "opportunities": [
            {
                "headline": "BPC-157 research overview (RUO)",
                "abstract": "Research-use-only overview for laboratory readers.",
                "search_intent": "research_overview",
                "content_type": "research_overview",
            },
            {
                "headline": "RUO labeling on peptide product pages: what labs should verify",
                "abstract": "Explains RUO labeling and documentation checks for procurement.",
                "search_intent": "informational",
                "content_type": "guide",
            },
        ]
    }
    parsed, warnings = parse_opportunities_response(payload, min_ideas=1, max_ideas=75)
    assert len(parsed) == 2
    assert any("ruo_in_headline:BPC-157" in w for w in warnings)
    assert not any("ruo_in_headline:RUO labeling" in w for w in warnings)


def test_parser_accepts_mechanism_and_relationship_intents() -> None:
    payload = {
        "opportunities": [
            {
                "headline": "AMPK signaling explained for peptide research readers",
                "abstract": "Background on AMPK pathways relevant to MOTS-C and AICAR research context.",
                "search_intent": "mechanism",
                "content_type": "mechanism_explainer",
                "recommendation_type": "create",
                "related_products": ["MOTS-C"],
                "related_topics": ["AMPK signaling"],
                "target_audience": "Laboratory researchers",
                "priority_reason": "Fills mechanism explainer gap.",
                "safety_notes": ["Research use only"],
            },
            {
                "headline": "BPC-157 and TB-500: why they are often discussed together",
                "abstract": "Explains co-mention in research discourse without combined-use advice.",
                "search_intent": "product_relationship",
                "content_type": "relationship",
                "recommendation_type": "create",
                "related_products": ["BPC-157", "TB-500"],
                "related_topics": ["paired peptide research"],
                "target_audience": "Laboratory researchers",
                "priority_reason": "Relationship article for catalog coverage.",
                "safety_notes": ["Research use only"],
            },
        ]
    }
    parsed, warnings = parse_opportunities_response(payload, min_ideas=1, max_ideas=75)
    assert len(parsed) == 2
    assert parsed[0].search_intent == "mechanism"
    assert parsed[1].content_type == "relationship"
    assert not any("invalid" in w for w in warnings)


def test_parser_accepts_valid_schema_and_recommendation_type() -> None:
    payload = {
        "opportunities": [
            {
                "headline": "TB-500 Storage Guide for Research Labs",
                "abstract": "Covers lyophilized TB-500 storage conditions for laboratory inventory.",
                "search_intent": "storage",
                "content_type": "guide",
                "recommendation_type": "create",
                "related_products": ["TB-500"],
                "related_topics": ["peptide stability"],
                "target_audience": "Laboratory researchers",
                "priority_reason": "Fills a product-specific handling gap.",
                "safety_notes": ["Research use only"],
            }
        ]
    }
    parsed, warnings = parse_opportunities_response(payload, min_ideas=1, max_ideas=60)
    assert len(parsed) == 1
    assert parsed[0].recommendation_type == "create"
    assert not any("invalid" in w for w in warnings)


def test_parser_rejects_malformed_rows_safely() -> None:
    payload = {
        "opportunities": [
            {"headline": "", "abstract": "Missing headline"},
            {"headline": "Valid Headline", "abstract": "Valid abstract.", "search_intent": "faq", "content_type": "faq"},
            "not-an-object",
        ]
    }
    parsed, warnings = parse_opportunities_response(payload, min_ideas=1, max_ideas=60)
    assert len(parsed) == 1
    assert any("missing_headline" in w or "row_" in w for w in warnings)


def test_parser_dedupes_headlines() -> None:
    payload = {
        "opportunities": [
            {"headline": "TB-500 Storage Guide", "abstract": "First.", "search_intent": "storage", "content_type": "guide"},
            {"headline": "tb-500 storage guide", "abstract": "Duplicate.", "search_intent": "storage", "content_type": "guide"},
        ]
    }
    parsed, warnings = parse_opportunities_response(payload, min_ideas=1, max_ideas=60)
    assert len(parsed) == 1
    assert any("duplicate_headline" in w for w in warnings)


def test_catalog_coverage_check_warns() -> None:
    payload = {
        "opportunities": [
            {
                "headline": "BPC-157 Handling",
                "abstract": "Handling guide.",
                "search_intent": "product_handling",
                "content_type": "guide",
                "related_products": ["BPC-157"],
            }
        ]
    }
    _, warnings = parse_opportunities_response(
        payload,
        min_ideas=1,
        max_ideas=60,
        catalog_products=["BPC-157", "TB-500"],
    )
    assert any("catalog_products_not_fully_covered" in w for w in warnings)


def test_ideation_call_timeout_scales_with_expected_ideas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_OPPORTUNITY_IDEATION_TIMEOUT_SECONDS", "60")
    settings = Settings(_env_file=None)
    service = AIOpportunityIdeationService(settings, MagicMock(), openai_client=MagicMock())
    assert service._call_timeout_seconds(expected_ideas=5) == 60.0
    assert service._call_timeout_seconds(expected_ideas=75) == 300.0


def test_service_fail_open_without_client() -> None:
    settings = Settings(_env_file=None, ai_opportunity_ideation_enabled=True)
    service = AIOpportunityIdeationService(settings, MagicMock(), openai_client=None)

    async def _run() -> dict[str, Any]:
        return await service.generate_for_workspace("ws-1", workspace={"id": "ws-1", "website_url": "https://example.com"})

    result = asyncio.run(_run())
    assert result["opportunities"] == []
    assert result["metrics"]["fallback_count"] == 1


def test_article_generation_receives_opportunity_context() -> None:
    context = {
        "headline": "TB-500 Storage Guide",
        "abstract": "Lab storage overview.",
        "search_intent": "storage",
        "related_products": ["TB-500"],
    }
    prompt = build_article_prompt(
        ArticlePromptInput(
            title="TB-500 Storage Guide",
            target_keyword="tb-500 storage",
            product_name="TB-500",
            product_url="https://example.com/product/tb-500/",
            opportunity_context_json=_opportunity_context_json(context),
        )
    )
    text = str(prompt)
    assert "TB-500 Storage Guide" in text
    assert "Lab storage overview." in text


def test_article_brief_enrichment_sets_science_focus() -> None:
    from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context

    context = {
        "headline": "Retatrutide vs Tirzepatide: receptor biology and category differences",
        "abstract": "Compares GLP-1/GIP receptor biology and research themes discussed in literature.",
        "search_intent": "comparison",
        "content_type": "comparison",
        "related_products": ["Retatrutide", "Tirzepatide"],
        "related_topics": ["GLP-1 signaling", "GIP receptor biology", "metabolic peptides"],
    }
    brief = enrich_article_opportunity_context(context)
    assert brief["science_focus"] is True
    assert brief["related_pathways"]
    assert "supplier" not in json.dumps(brief).lower()
    rendered = _opportunity_context_json(context)
    assert "science_focus" in rendered
    assert "related_research_themes" in rendered
    assert "science_depth_targets" in brief
    assert brief["science_depth_targets"]["major_pathways"]


def test_ideation_opportunities_to_recommendation_rows_preserves_metadata() -> None:
    from app.ai_opportunity_ideation.recommendations import ideation_opportunities_to_recommendation_rows

    rows = ideation_opportunities_to_recommendation_rows(
        [
            {
                "id": "opp-1",
                "headline": "TB-500 Storage Guide",
                "abstract": "Lab storage overview.",
                "search_intent": "storage",
                "content_type": "guide",
                "recommendation_type": "create",
                "related_products": ["TB-500"],
                "priority_reason": "Product-specific gap.",
            }
        ],
        analysis_job_id="job-1",
    )
    assert len(rows) == 1
    assert rows[0]["source_type"] == "ai_opportunity_ideation"
    assert rows[0]["action"] == "create"
    assert rows[0]["metadata"]["abstract"] == "Lab storage overview."
    assert "article_brief" in rows[0]["metadata"]


def test_ideation_enabled_is_product_mode() -> None:
    settings = Settings(_env_file=None, ai_opportunity_ideation_enabled=True)
    assert settings.is_ai_ideation_only_mode
    brief_a = {"workspace_id": "ws", "analysis_job_id": "j1", "catalog_products": ["BPC-157", "TB-500"], "existing_page_titles": [], "competitor_gap_topics": []}
    brief_b = {"workspace_id": "ws", "analysis_job_id": "j1", "catalog_products": ["TB-500", "BPC-157"], "existing_page_titles": [], "competitor_gap_topics": []}
    assert brief_cache_key(brief_a) == brief_cache_key(brief_b)


def test_merge_opportunity_lists_dedupes_and_caps() -> None:
    existing = [
        AIOpportunity(
            headline="TB-500 Storage Guide",
            abstract="First.",
            search_intent="storage",
            content_type="guide",
            related_products=["TB-500"],
            related_topics=[],
            target_audience="Researchers",
            priority_reason="Gap.",
            safety_notes=[],
            recommendation_type="create",
        )
    ]
    supplemental = [
        AIOpportunity(
            headline="tb-500 storage guide",
            abstract="Duplicate.",
            search_intent="storage",
            content_type="guide",
            related_products=["TB-500"],
            related_topics=[],
            target_audience="Researchers",
            priority_reason="Dup.",
            safety_notes=[],
            recommendation_type="create",
        ),
        AIOpportunity(
            headline="BPC-157 Reconstitution FAQ",
            abstract="Second.",
            search_intent="faq",
            content_type="faq",
            related_products=["BPC-157"],
            related_topics=[],
            target_audience="Researchers",
            priority_reason="Gap.",
            safety_notes=[],
            recommendation_type="create",
        ),
    ]
    merged, warnings = merge_opportunity_lists(existing, supplemental, max_ideas=60)
    assert len(merged) == 2
    assert any("duplicate_headline" in w for w in warnings)


def test_salvage_truncated_ideation_json() -> None:
    valid = {
        "headline": "BPC-157 vs TB-500",
        "abstract": "Comparison for researchers.",
        "search_intent": "comparison",
        "content_type": "comparison",
    }
    truncated = json.dumps({"opportunities": [valid, valid]})[:-40]
    salvaged = salvage_opportunities_payload(truncated)
    assert len(salvaged["opportunities"]) == 1
    payload, warnings = loads_ideation_payload(truncated)
    assert len(payload["opportunities"]) == 1
    assert any("salvaged_truncated_json" in w for w in warnings)


def test_generate_opportunities_top_up_when_below_min() -> None:
    settings = Settings(
        _env_file=None,
        ai_opportunity_ideation_enabled=True,
        ai_opportunity_ideation_min_ideas=40,
        ai_opportunity_ideation_max_ideas=60,
        ai_opportunity_ideation_batch_size=30,
        ai_opportunity_ideation_max_top_up_rounds=1,
    )

    def _opp(i: int) -> dict[str, Any]:
        return {
            "headline": f"Opportunity {i}",
            "abstract": f"Abstract {i}.",
            "search_intent": "informational",
            "content_type": "guide",
            "recommendation_type": "create",
            "related_products": ["TB-500"],
            "related_topics": [],
            "target_audience": "Researchers",
            "priority_reason": "Gap.",
            "safety_notes": [],
        }

    first_payload = {"opportunities": [_opp(i) for i in range(30)]}
    second_payload = {"opportunities": [_opp(i) for i in range(30, 50)]}

    client = MagicMock()
    response_a = MagicMock()
    response_a.choices = [MagicMock(message=MagicMock(content=json.dumps(first_payload)))]
    response_b = MagicMock()
    response_b.choices = [MagicMock(message=MagicMock(content=json.dumps(second_payload)))]
    client.chat.completions.create = AsyncMock(side_effect=[response_a, response_b])

    service = AIOpportunityIdeationService(settings, MagicMock(), openai_client=client)
    brief = {"workspace_id": "ws-1", "catalog_products": ["TB-500"], "existing_page_titles": []}

    async def _run() -> tuple[list[AIOpportunity], list[str]]:
        return await service._generate_opportunities(
            brief,
            min_ideas=40,
            max_ideas=60,
            catalog_products=["TB-500"],
        )

    parsed, warnings = asyncio.run(_run())
    assert client.chat.completions.create.await_count == 2
    assert len(parsed) >= 40
    assert any("top_up_round_1" in w for w in warnings)
