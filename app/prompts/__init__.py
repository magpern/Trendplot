import json
from dataclasses import dataclass
from typing import Any

from app.prompts.prompt_registry import get_default_prompt_registry
from app.prompts.prompt_renderer import PromptText


@dataclass(slots=True)
class ArticlePromptInput:
    title: str
    target_keyword: str
    product_name: str
    product_url: str
    min_word_count: int = 1800
    max_word_count: int = 3000
    opportunity_context_json: str = ""

    @property
    def target_word_count_mid(self) -> int:
        return (self.min_word_count + self.max_word_count) // 2


def render_prompt(prompt_id: str, variables: dict[str, Any]) -> PromptText:
    return get_default_prompt_registry().render(prompt_id, variables).text


def build_article_prompt(input_data: ArticlePromptInput) -> PromptText:
    return render_prompt(
        "article_generation",
        {
            "title": input_data.title,
            "target_keyword": input_data.target_keyword,
            "product_name": input_data.product_name,
            "product_url": input_data.product_url,
            "min_word_count": input_data.min_word_count,
            "max_word_count": input_data.max_word_count,
            "target_word_count_mid": input_data.target_word_count_mid,
            "opportunity_context_json": input_data.opportunity_context_json or "",
        },
    )


def build_image_prompt_generation_prompt(
    article_title: str,
    target_keyword: str,
    product_name: str,
    research_context: str,
    limitations_and_safety: str,
    brand_style_notes: str,
) -> PromptText:
    return render_prompt(
        "image_prompt_generation",
        {
            "article_title": article_title,
            "target_keyword": target_keyword,
            "product_name": product_name,
            "research_context": research_context,
            "limitations_and_safety": limitations_and_safety,
            "brand_style_notes": brand_style_notes,
        },
    )


def build_seo_metadata_prompt(article_markdown: str, target_keyword: str) -> PromptText:
    return build_seo_package_prompt(
        article_title="",
        article_content=article_markdown,
        target_keyword=target_keyword,
        product_name="",
        meta_description="",
        related_products=None,
        article_type="article",
    )


def build_seo_package_prompt(
    *,
    article_title: str,
    article_content: str,
    target_keyword: str,
    product_name: str = "",
    meta_description: str = "",
    related_products: list[str] | None = None,
    article_type: str = "article",
) -> PromptText:
    import json

    return render_prompt(
        "seo_package",
        {
            "article_title": article_title,
            "article_content": article_content,
            "target_keyword": target_keyword,
            "product_name": product_name or "n/a",
            "meta_description": meta_description or "n/a",
            "related_products_json": json.dumps(related_products or [], ensure_ascii=False),
            "article_type": article_type or "article",
        },
    )


def build_article_repair_prompt(
    original_prompt: str,
    structured_article_json: str,
    quality_errors: list[str],
) -> PromptText:
    return render_prompt(
        "article_repair",
        {
            "original_prompt": original_prompt,
            "structured_article_json": structured_article_json,
            "quality_errors_json": json.dumps(quality_errors, ensure_ascii=False, indent=2),
            "quality_warnings_json": "[]",
            "target_min_word_count": "1800",
            "target_word_count": "2200",
            "pass_number": "1",
            "request_data_json": "{}",
            "biomedical_instruction": "Preserve factual caution and avoid unsupported claims.",
            "product_url": "",
        },
    )


def build_social_prompt(
    platform: str,
    article_markdown: str,
    title: str,
    product_name: str,
    product_url: str,
) -> PromptText:
    return render_prompt(
        "social_posts",
        {
            "platform": platform,
            "article_markdown": article_markdown,
            "title": title,
            "product_name": product_name,
            "product_url": product_url,
        },
    )


def build_youtube_evaluation_prompt(
    article_title: str,
    target_keyword: str,
    product_name: str,
    article_outline: str,
    candidates: list[dict[str, str]],
) -> PromptText:
    return render_prompt(
        "youtube_evaluation",
        {
            "article_title": article_title,
            "target_keyword": target_keyword,
            "product_name": product_name,
            "article_outline": article_outline,
            "candidates_json": json.dumps(candidates, ensure_ascii=False),
        },
    )
