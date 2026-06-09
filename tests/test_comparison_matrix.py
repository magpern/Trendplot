from __future__ import annotations

import json
from pathlib import Path

from app.review.comparison_matrix import (
    build_comparison_matrix,
    matrix_cell_word_limit,
    matrix_cells_are_distinct,
)
from app.review.article_composition import apply_article_composition_refinement

ROOT = Path(__file__).resolve().parents[1]
CJC_ARTICLE = ROOT / "docs" / "validation" / "ARTICLE_COMPOSITION_VERIFICATION.json"


def _cjc_comparison_article() -> dict:
    if CJC_ARTICLE.exists():
        payload = json.loads(CJC_ARTICLE.read_text(encoding="utf-8"))
        for item in payload.get("results") or []:
            if item.get("content_type") == "comparison" and item.get("article_after"):
                article = dict(item["article_after"])
                article["comparison_tables"] = []
                return article
    return {
        "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
        "key_takeaways": [
            "CJC-1295 No DAC + IPA is typically framed as a short-acting GHRH analog paired with ipamorelin, while CJC-1295 usually points to the DAC-modified long-acting form unless authors define otherwise.",
            "That shift changes the research question from sustained GHRH-pathway exposure to coordinated pulse generation across GHRH receptor and ghrelin receptor signaling.",
            "Exposure profile matters: a short-acting paired system is usually studied for timing and pulsatility, whereas DAC-containing CJC-1295 is often studied for prolonged signal support.",
        ],
        "sections": [],
    }


def test_comparison_matrix_cells_differ() -> None:
    matrix = build_comparison_matrix(
        _cjc_comparison_article(),
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/",
        },
        opportunity_context={
            "content_type": "comparison",
            "related_products": ["CJC-1295 No DAC + IPA", "CJC-1295"],
        },
    )
    assert matrix is not None
    assert matrix_cells_are_distinct(matrix)
    assert matrix_cell_word_limit(matrix, max_words=18)
    for row in matrix["rows"]:
        assert row[1].lower() != row[2].lower()
        assert len(row[1].split()) <= 18
        assert len(row[2].split()) <= 18


def test_comparison_matrix_uses_concise_distinctions_not_paragraphs() -> None:
    matrix = build_comparison_matrix(
        _cjc_comparison_article(),
        defaults={"title": "CJC-1295 No DAC + IPA vs CJC-1295", "product_name": "CJC-1295 No DAC + IPA", "product_url": ""},
        opportunity_context={"content_type": "comparison", "related_products": ["CJC-1295 No DAC + IPA", "CJC-1295"]},
    )
    assert matrix is not None
    exposure = next(row for row in matrix["rows"] if row[0] == "Exposure profile")
    assert "short-acting" in exposure[1].lower() or "pulse" in exposure[1].lower()
    assert "dac" in exposure[2].lower() or "prolonged" in exposure[2].lower() or "extended" in exposure[2].lower()
    assert len(exposure[1]) < 120
    assert len(exposure[2]) < 120


def test_retatrutide_vs_tirzepatide_matrix_distinctions() -> None:
    article = {
        "title": "Retatrutide vs Tirzepatide: receptor coverage in metabolic literature",
        "key_takeaways": [
            "Retatrutide is discussed as a triple agonist spanning GLP-1, GIP, and glucagon pathways, while tirzepatide is framed as a dual GLP-1/GIP agonist.",
            "Sampling focus differs: retatrutide papers often emphasize broader endocrine and energy-balance readouts, whereas tirzepatide studies usually center on glycemic and weight endpoints.",
        ],
        "excerpt": "The comparison is pathway breadth versus a narrower incretin dual-agonist model.",
        "sections": [
            {
                "heading": "Receptor themes",
                "content_markdown": "Retatrutide adds glucagon-receptor context to the GLP-1/GIP story, while tirzepatide stays within a dual incretin frame.",
            }
        ],
    }
    matrix = build_comparison_matrix(
        article,
        defaults={"title": article["title"], "product_name": "Retatrutide", "product_url": ""},
        opportunity_context={"content_type": "comparison", "related_products": ["Retatrutide", "Tirzepatide"]},
    )
    assert matrix is not None
    assert matrix_cells_are_distinct(matrix)
    receptor_row = next(row for row in matrix["rows"] if row[0] == "Receptor themes")
    assert receptor_row[1].lower() != receptor_row[2].lower()
    assert "glucagon" in receptor_row[1].lower() or "tri" in receptor_row[1].lower()
    assert "dual" in receptor_row[2].lower() or "gip" in receptor_row[2].lower()


def test_composition_refinement_replaces_weak_matrix() -> None:
    article = _cjc_comparison_article()
    article["comparison_tables"] = [
        {
            "title": "Comparison Matrix",
            "headers": ["Topic", "A", "B"],
            "rows": [
                ["Exposure profile", "Same long paragraph about timing.", "Same long paragraph about timing."],
            ],
        }
    ]
    refined = apply_article_composition_refinement(
        article,
        opportunity_context={"content_type": "comparison", "related_products": ["CJC-1295 No DAC + IPA", "CJC-1295"]},
        defaults={"title": article["title"], "product_name": "CJC-1295 No DAC + IPA", "product_url": ""},
    )
    matrix = refined["comparison_tables"][0]
    assert matrix_cells_are_distinct(matrix)
