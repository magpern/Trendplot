from __future__ import annotations

from app.seo.focus_keywords import (
    format_focus_keywords,
    normalize_seo_focus_keywords,
    parse_focus_keywords,
    phrase_contains_entity,
    primary_focus_keyword,
    secondary_focus_keywords,
)
from app.seo.optimization_pass import run_seo_optimization_pass
from app.seo.text_utils import collect_body_markdown, count_keyword_occurrences
from app.wordpress_connector.seo import apply_focus_keyword_strategy, validate_seo_fields


def test_parse_and_format_max_two_keywords() -> None:
    assert parse_focus_keywords("TB-500 vs BPC-157, BPC-157") == ["TB-500 vs BPC-157", "BPC-157"]
    assert format_focus_keywords(["TB-500 vs BPC-157", "BPC-157", "TB-500"]) == "TB-500 vs BPC-157, BPC-157"


def test_normalize_adds_product_secondary_when_missing() -> None:
    normalized = normalize_seo_focus_keywords(
        "TB-500 vs BPC-157",
        primary_fallback="TB-500 vs BPC-157",
        product_name="BPC-157",
        related_products=["TB-500"],
    )
    assert normalized == "TB-500 vs BPC-157, BPC-157"


def test_normalize_keeps_existing_dual_keywords() -> None:
    normalized = normalize_seo_focus_keywords(
        "TB-500 vs BPC-157, TB-500",
        product_name="BPC-157",
    )
    assert normalized == "TB-500 vs BPC-157, TB-500"


def test_apply_focus_keyword_strategy_on_llm_payload() -> None:
    fields = apply_focus_keyword_strategy(
        {"seo_focus_keyword": "peptide comparison overview"},
        primary_fallback="TB-500 vs BPC-157",
        product_name="BPC-157",
        related_products=["TB-500"],
    )
    assert "BPC-157" in fields["seo_focus_keyword"]
    assert primary_focus_keyword(fields["seo_focus_keyword"]) == "peptide comparison overview"


def test_validate_allows_two_keyword_phrases() -> None:
    errors = validate_seo_fields(
        {
            "seo_title": "Title",
            "seo_description": "Description",
            "seo_focus_keyword": "TB-500 vs BPC-157, BPC-157",
        }
    )
    assert not errors


def test_validate_rejects_more_than_two_keywords() -> None:
    errors = validate_seo_fields(
        {
            "seo_title": "Title",
            "seo_description": "Description",
            "seo_focus_keyword": "one, two, three",
        }
    )
    assert any("at most 2" in error for error in errors)


def test_optimization_prioritizes_primary_and_adds_secondary_once() -> None:
    article = {
        "title": "TB-500 vs BPC-157",
        "primary_keyword": "TB-500 vs BPC-157",
        "sections": [
            {"heading": "Background", "content_markdown": "Peptide research context for laboratory use."},
            {
                "heading": "Mechanisms",
                "content_markdown": "Researchers compare signaling pathways in laboratory models.",
            },
        ],
    }
    updated, seo, report = run_seo_optimization_pass(
        article,
        {"seo_focus_keyword": "TB-500 vs BPC-157"},
        product_name="BPC-157",
        related_products=["TB-500"],
        respect_manual_seo=False,
    )
    body = collect_body_markdown(updated)
    assert seo["seo_focus_keyword"] == "TB-500 vs BPC-157, BPC-157"
    assert count_keyword_occurrences(body, "TB-500 vs BPC-157") >= 1
    assert count_keyword_occurrences(body, "BPC-157") <= 3
    assert report.secondary_keyword_added or "BPC-157" in body
    assert secondary_focus_keywords(seo["seo_focus_keyword"]) == ["BPC-157"]


def test_phrase_contains_entity() -> None:
    assert phrase_contains_entity("TB-500 vs BPC-157", ["BPC-157"])
    assert not phrase_contains_entity("peptide overview", ["BPC-157"])
