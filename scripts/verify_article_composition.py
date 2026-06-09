#!/usr/bin/env python3
"""Generate science articles and compare composition metrics before vs after refinement."""

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
from app.review.article_composition import (
    apply_article_composition_refinement,
    count_concept_repetitions,
    prose_word_count,
)
from app.review.compliance_redundancy import reduce_compliance_repetition, strip_commerce_language_for_science_articles
from app.services.jobs import _opportunity_context_json

CASES = [
    {
        "content_type": "comparison",
        "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
        "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
        "product_name": "CJC-1295 No DAC + IPA",
        "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        "related_topics": ["GHRH signaling", "exposure profile", "pulse kinetics", "nomenclature"],
    },
    {
        "content_type": "research_overview",
        "title": "CJC-1295 No DAC + IPA in growth hormone secretagogue literature",
        "target_keyword": "cjc-1295 no dac ipa research overview",
        "product_name": "CJC-1295 No DAC + IPA",
        "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        "related_topics": ["secretagogue biology", "receptor engagement", "preclinical models"],
    },
    {
        "content_type": "relationship",
        "title": "CJC-1295 No DAC + IPA and Ipamorelin: how the literature pairs them",
        "target_keyword": "cjc-1295 no dac ipa ipamorelin relationship",
        "product_name": "CJC-1295 No DAC + IPA",
        "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        "related_topics": ["dual-pathway stimulation", "GHSR-1a", "pulse coordination"],
    },
]


def _baseline_refine(data: dict, *, context: dict) -> dict:
    data = reduce_compliance_repetition(dict(data))
    return strip_commerce_language_for_science_articles(data, opportunity_context=context)


def _metrics(data: dict) -> dict:
    return {
        "word_count": prose_word_count(data),
        "section_count": len(data.get("sections") or []),
        "comparison_table_count": len(data.get("comparison_tables") or []),
        "callout_count": len(data.get("callout_boxes") or []),
        "definition_box_count": len(data.get("definition_boxes") or []),
        "concept_repetitions": count_concept_repetitions(data),
        "concept_repetition_total": sum(count_concept_repetitions(data).values()),
    }


async def _generate_case(case: dict) -> dict:
    settings = Settings()
    registry = build_provider_registry(settings)
    provider = registry.content_generation
    context = enrich_article_opportunity_context(
        {
            "content_type": case["content_type"],
            "search_intent": case["content_type"],
            "headline": case["title"],
            "title": case["title"],
            "related_products": [case["product_name"], "Ipamorelin"],
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
    before_data = _baseline_refine(article, context=context)
    after_data = apply_article_composition_refinement(before_data, opportunity_context=context, defaults=defaults)
    before = _metrics(before_data)
    after = _metrics(after_data)
    return {
        "content_type": case["content_type"],
        "title": case["title"],
        "model": generated.model,
        "before": before,
        "after": after,
        "structured_elements_added": {
            "comparison_tables": max(0, after["comparison_table_count"] - before["comparison_table_count"]),
            "callouts": max(0, after["callout_count"] - before["callout_count"]),
            "definition_boxes": max(0, after["definition_box_count"] - before["definition_box_count"]),
        },
        "word_count_reduction_pct": round(
            (before["word_count"] - after["word_count"]) / before["word_count"] * 100,
            1,
        )
        if before["word_count"]
        else 0.0,
        "article_before": before_data,
        "article_after": after_data,
    }


def _replay_from_json(json_path: Path) -> list[dict]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    results = []
    for item in payload.get("results") or []:
        if not item.get("article_before"):
            continue
        case = next((c for c in CASES if c["content_type"] == item.get("content_type")), None)
        if not case:
            continue
        context = enrich_article_opportunity_context(
            {
                "content_type": case["content_type"],
                "search_intent": case["content_type"],
                "headline": case["title"],
                "title": case["title"],
                "related_products": [case["product_name"]],
                "related_topics": case["related_topics"],
            }
        )
        defaults = {
            "title": case["title"],
            "target_keyword": case["target_keyword"],
            "product_name": case["product_name"],
            "product_url": case["product_url"],
        }
        before_data = dict(item["article_before"])
        after_data = apply_article_composition_refinement(before_data, opportunity_context=context, defaults=defaults)
        before = _metrics(before_data)
        after = _metrics(after_data)
        results.append(
            {
                "content_type": case["content_type"],
                "title": case["title"],
                "model": item.get("model"),
                "before": before,
                "after": after,
                "structured_elements_added": {
                    "comparison_tables": max(0, after["comparison_table_count"] - before["comparison_table_count"]),
                    "callouts": max(0, after["callout_count"] - before["callout_count"]),
                    "definition_boxes": max(0, after["definition_box_count"] - before["definition_box_count"]),
                },
                "word_count_reduction_pct": round(
                    (before["word_count"] - after["word_count"]) / before["word_count"] * 100,
                    1,
                )
                if before["word_count"]
                else 0.0,
                "article_before": before_data,
                "article_after": after_data,
                "replayed": True,
            }
        )
    return results


async def main() -> None:
    json_path = ROOT / "docs" / "validation" / "ARTICLE_COMPOSITION_VERIFICATION.json"
    if len(sys.argv) > 1 and sys.argv[1] == "--replay" and json_path.exists():
        results = _replay_from_json(json_path)
    else:
        results = []
        for case in CASES:
            print(f"Generating {case['content_type']} article...", flush=True)
            results.append(await _generate_case(case))
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": results,
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"generated_at": report["generated_at"], "cases": len(results)}, indent=2))
    for item in results:
        print(
            f"- {item['content_type']}: words {item['before']['word_count']} -> {item['after']['word_count']} "
            f"({item['word_count_reduction_pct']}%), concept reps "
            f"{item['before']['concept_repetition_total']} -> {item['after']['concept_repetition_total']}"
        )
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
