#!/usr/bin/env python3
"""Validate comparison matrix distinction quality for sample comparison articles."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context
from app.article_schema import normalize_article
from app.config import Settings
from app.prompts import ArticlePromptInput, build_article_prompt
from app.providers.registry import build_provider_registry
from app.providers.model_router import ModelTask
from app.review.comparison_matrix import build_comparison_matrix, matrix_cells_are_distinct, matrix_cell_word_limit
from app.services.jobs import _opportunity_context_json

CASES = [
    {
        "slug": "cjc-1295",
        "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
        "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
        "product_name": "CJC-1295 No DAC + IPA",
        "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        "related_products": ["CJC-1295 No DAC + IPA", "CJC-1295"],
        "related_topics": ["GHRH signaling", "pulse kinetics", "exposure profile", "nomenclature"],
    },
    {
        "slug": "retatrutide-tirzepatide",
        "title": "Retatrutide vs Tirzepatide: receptor coverage in metabolic literature",
        "target_keyword": "retatrutide vs tirzepatide",
        "product_name": "Retatrutide",
        "product_url": "https://example.com/product/retatrutide/",
        "related_products": ["Retatrutide", "Tirzepatide"],
        "related_topics": ["GLP-1 signaling", "GIP pathway", "glucagon receptor", "metabolic endpoints"],
    },
]


async def _generate_matrix(case: dict) -> dict:
    settings = Settings()
    registry = build_provider_registry(settings)
    provider = registry.content_generation
    context = enrich_article_opportunity_context(
        {
            "content_type": "comparison",
            "search_intent": "comparison",
            "headline": case["title"],
            "title": case["title"],
            "related_products": case["related_products"],
            "related_topics": case["related_topics"],
        }
    )
    defaults = {
        "title": case["title"],
        "target_keyword": case["target_keyword"],
        "product_name": case["product_name"],
        "product_url": case["product_url"],
    }
    prompt = build_article_prompt(
        ArticlePromptInput(
            title=case["title"],
            target_keyword=case["target_keyword"],
            product_name=case["product_name"],
            product_url=case["product_url"],
            min_word_count=900,
            max_word_count=1400,
            opportunity_context_json=_opportunity_context_json(context),
        )
    )
    generated = await provider.generate_article(prompt, task_type=ModelTask.ARTICLE_GENERATION)
    payload = generated.content_json or {}
    article_json = payload.get("article") if isinstance(payload.get("article"), dict) else payload
    article = normalize_article(article_json, defaults=defaults).model_dump()
    matrix = build_comparison_matrix(article, defaults=defaults, opportunity_context=context)
    return {
        "slug": case["slug"],
        "title": case["title"],
        "model": generated.model,
        "matrix": matrix,
        "cells_distinct": matrix_cells_are_distinct(matrix) if matrix else False,
        "within_word_limit": matrix_cell_word_limit(matrix) if matrix else False,
        "article": article,
    }


async def main() -> None:
    results = []
    for case in CASES:
        print(f"Generating {case['slug']} comparison...", flush=True)
        results.append(await _generate_matrix(case))
    report = {"generated_at": datetime.now(UTC).isoformat(), "results": results}
    output = ROOT / "docs" / "validation" / "COMPARISON_MATRIX_VERIFICATION.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in results:
        print(
            f"- {item['slug']}: distinct={item['cells_distinct']} "
            f"word_limit={item['within_word_limit']} rows={len((item.get('matrix') or {}).get('rows') or [])}"
        )
    print(f"Wrote {output}")


if __name__ == "__main__":
    asyncio.run(main())
