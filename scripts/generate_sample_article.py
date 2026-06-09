#!/usr/bin/env python3
"""Generate one sample article via the current article_generation prompt (for manual comparison)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.article_schema import article_to_markdown, normalize_article
from app.config import Settings
from app.prompts import ArticlePromptInput, build_article_prompt
from app.providers.registry import build_provider_registry
from app.providers.model_router import ModelTask
from app.quality_checks import run_article_quality_checks


async def _generate(
    *,
    title: str,
    target_keyword: str,
    product_name: str,
    product_url: str,
    min_words: int,
    max_words: int,
    output: Path,
) -> None:
    settings = Settings()
    registry = build_provider_registry(settings)
    provider = registry.content_generation
    prompt = build_article_prompt(
        ArticlePromptInput(
            title=title,
            target_keyword=target_keyword,
            product_name=product_name,
            product_url=product_url,
            min_word_count=min_words,
            max_word_count=max_words,
        )
    )
    generated = await provider.generate_article(prompt, task_type=ModelTask.ARTICLE_GENERATION)
    payload = generated.content_json or {}
    article_json = payload.get("article") if isinstance(payload.get("article"), dict) else payload
    article = normalize_article(
        article_json,
        defaults={
            "title": title,
            "target_keyword": target_keyword,
            "product_name": product_name,
            "product_url": product_url,
        },
    )
    markdown = article_to_markdown(article)
    quality = run_article_quality_checks(
        article=article.model_dump(),
        markdown=markdown,
        product_url=product_url,
        youtube_video=None,
        min_word_count=min_words,
        required_disclaimer=settings.biomedical_ruo_disclaimer,
    )
    usage = generated.usage
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "title": title,
        "target_keyword": target_keyword,
        "model": generated.model,
        "usage": {
            "token_input": usage.token_input if usage else None,
            "token_output": usage.token_output if usage else None,
            "estimated_cost": usage.estimated_cost if usage else None,
        },
        "word_count": quality.word_count,
        "quality_passed": quality.passed,
        "quality_errors": quality.errors,
        "quality_warnings": quality.warnings,
        "section_count": len(article.sections),
        "internal_link_count": len(article.internal_links),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "report": report,
                "article": article.model_dump(),
                "publishable_markdown": markdown,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one sample article for prompt comparison.")
    parser.add_argument("--title", default="How to Store Bacteriostatic Water for Laboratory Use")
    parser.add_argument("--keyword", default="bacteriostatic water storage")
    parser.add_argument("--product-name", default="Bacteriostatic Water")
    parser.add_argument("--product-url", default="https://example.com/bacteriostatic-water/")
    parser.add_argument("--min-words", type=int, default=1800)
    parser.add_argument("--max-words", type=int, default=3000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "validation" / "sample_article_generation_v2.json",
    )
    args = parser.parse_args()
    asyncio.run(
        _generate(
            title=args.title,
            target_keyword=args.keyword,
            product_name=args.product_name,
            product_url=args.product_url,
            min_words=args.min_words,
            max_words=args.max_words,
            output=args.output,
        )
    )


if __name__ == "__main__":
    main()
