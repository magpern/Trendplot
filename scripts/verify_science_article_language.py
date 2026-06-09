#!/usr/bin/env python3
"""Generate comparison + mechanism articles and verify commerce language is filtered."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context
from app.article_schema import article_to_markdown, normalize_article
from app.config import Settings
from app.prompts import ArticlePromptInput, build_article_prompt
from app.providers.registry import build_provider_registry
from app.providers.model_router import ModelTask
from app.rendering.article_renderer import render_article
from app.rendering.render_surface import ArticleRenderSurface
from app.review.compliance_redundancy import apply_editorial_post_processing
from app.services.jobs import _opportunity_context_json

_COMMERCE_RE = re.compile(
    r"\b(buyers?|shoppers?|purchasing|purchase(?:rs?|ing)?|supplier evaluation|catalog selection|shopping|procurement)\b",
    re.I,
)
_SCHEMA_LABEL_RE = re.compile(r"\*\*(?:Heading|Content Markdown|Summary|Points)\*\*", re.I)


async def _generate_one(
    *,
    content_type: str,
    title: str,
    target_keyword: str,
    product_name: str,
    product_url: str,
) -> dict:
    settings = Settings()
    registry = build_provider_registry(settings)
    provider = registry.content_generation
    context = enrich_article_opportunity_context(
        {
            "content_type": content_type,
            "search_intent": content_type,
            "headline": title,
            "title": title,
            "related_products": [product_name, "Ipamorelin"],
            "related_topics": ["GHRH signaling", "growth hormone secretagogue pathways", "receptor engagement"],
        }
    )
    prompt = build_article_prompt(
        ArticlePromptInput(
            title=title,
            target_keyword=target_keyword,
            product_name=product_name,
            product_url=product_url,
            min_word_count=900,
            max_word_count=1400,
            opportunity_context_json=_opportunity_context_json(context),
        )
    )
    generated = await provider.generate_article(prompt, task_type=ModelTask.ARTICLE_GENERATION)
    payload = generated.content_json or {}
    article_json = payload.get("article") if isinstance(payload.get("article"), dict) else payload
    defaults = {
        "title": title,
        "target_keyword": target_keyword,
        "product_name": product_name,
        "product_url": product_url,
    }
    article = normalize_article(article_json, defaults=defaults)
    article = apply_editorial_post_processing(article, defaults=defaults, opportunity_context=context)
    publishable_md = article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE)
    html = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html
    blob = f"{publishable_md}\n{html}"
    commerce_hits = sorted({match.group(0).lower() for match in _COMMERCE_RE.finditer(blob)})
    schema_hits = sorted({match.group(0) for match in _SCHEMA_LABEL_RE.finditer(blob)})
    return {
        "content_type": content_type,
        "title": title,
        "model": generated.model,
        "commerce_language_hits": commerce_hits,
        "schema_label_hits": schema_hits,
        "passed": not commerce_hits and not schema_hits,
        "research_context": article.research_context,
        "limitations_and_safety": article.limitations_and_safety,
        "article": article.model_dump(),
        "publishable_markdown": publishable_md,
    }


async def main() -> None:
    cases = [
        {
            "content_type": "comparison",
            "title": "CJC-1295 No DAC + IPA vs Ipamorelin: Research Literature Comparison",
            "target_keyword": "cjc-1295 no dac ipa vs ipamorelin",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
        {
            "content_type": "mechanism",
            "title": "How CJC-1295 No DAC and Ipamorelin Engage GHRH Signaling Pathways",
            "target_keyword": "cjc-1295 no dac ipa mechanism",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    ]
    results = []
    for case in cases:
        print(f"Generating {case['content_type']} article...", flush=True)
        results.append(await _generate_one(**case))
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "all_passed": all(item["passed"] for item in results),
        "results": results,
    }
    output = ROOT / "docs" / "validation" / "SCIENCE_ARTICLE_LANGUAGE_VERIFICATION.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    for item in results:
        print(
            f"- {item['content_type']}: passed={item['passed']} "
            f"commerce={item['commerce_language_hits']} schema={item['schema_label_hits']}"
        )
    print(f"Wrote {output}")


if __name__ == "__main__":
    asyncio.run(main())
