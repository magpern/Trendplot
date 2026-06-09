import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.article_schema import ArticleSchema, normalize_article
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask


FIXABLE_ISSUE_HINTS = (
    "too short",
    "ruo disclaimer is missing",
    "too shallow",
    "faq section is missing",
    "references_to_verify",
    "suggested references are missing",
    "internal links",
    "product url is not included",
)


@dataclass(slots=True)
class ArticleRepairRequest:
    article: ArticleSchema
    request_data: dict[str, Any]
    quality_errors: list[str]
    quality_warnings: list[str]
    target_min_word_count: int
    is_biomedical: bool
    required_disclaimer: str
    pass_number: int


@dataclass(slots=True)
class ArticleRepairResult:
    repaired_article_json: dict[str, Any]
    repair_summary: dict[str, Any]
    repaired_fields: list[str] = field(default_factory=list)
    repaired_sections: list[str] = field(default_factory=list)
    prompt: str = ""
    generated: GeneratedContent | None = None


class ArticleRepairService:
    async def repair(
        self,
        content_provider: Any,
        request: ArticleRepairRequest,
    ) -> ArticleRepairResult:
        prompt = build_article_repair_prompt(request)
        generated = await content_provider.generate_article(prompt, task_type=ModelTask.ARTICLE_REPAIR)
        payload = generated.content_json or {}
        repaired_article_json = payload.get("article") if isinstance(payload.get("article"), dict) else payload
        repaired_article_json = _apply_required_repairs(repaired_article_json, request)
        summary = payload.get("repair_summary") if isinstance(payload.get("repair_summary"), dict) else {}

        repaired_fields = _string_list(summary.get("repaired_fields"))
        repaired_sections = _string_list(summary.get("repaired_sections"))
        if not summary:
            summary = {
                "attempted": True,
                "pass_number": request.pass_number,
                "fixed_issues": request.quality_errors + request.quality_warnings,
                "repaired_fields": repaired_fields,
                "repaired_sections": repaired_sections,
                "notes": "Model returned a canonical article without a repair_summary wrapper.",
            }

        return ArticleRepairResult(
            repaired_article_json=repaired_article_json,
            repair_summary=summary,
            repaired_fields=repaired_fields,
            repaired_sections=repaired_sections,
            prompt=prompt,
            generated=generated,
        )


def apply_deterministic_quality_fixes(
    article: ArticleSchema,
    *,
    request_data: dict[str, Any],
    is_biomedical: bool,
    required_disclaimer: str,
    defaults: dict[str, str],
    target_min_word_count: int = 1800,
) -> ArticleSchema:
    """Inject RUO disclaimer, product links, FAQ stubs, and safety sanitization without an LLM call."""
    request = ArticleRepairRequest(
        article=article,
        request_data=request_data,
        quality_errors=[],
        quality_warnings=[],
        target_min_word_count=target_min_word_count,
        is_biomedical=is_biomedical,
        required_disclaimer=required_disclaimer,
        pass_number=0,
    )
    fixed = _apply_required_repairs(article.model_dump(), request)
    return normalize_article(fixed, defaults=defaults)


def has_fixable_quality_issues(errors: list[str], warnings: list[str]) -> bool:
    issue_text = " | ".join(errors + warnings).lower()
    return any(hint in issue_text for hint in FIXABLE_ISSUE_HINTS)


def build_article_repair_prompt(request: ArticleRepairRequest) -> str:
    biomedical_instruction = (
        f'The exact disclaimer "{request.required_disclaimer}" must appear in limitations_and_safety '
        "or a dedicated safety/CTA section."
        if request.is_biomedical
        else "Do not add biomedical disclaimers unless they are relevant to the topic."
    )
    target_word_count = max(request.target_min_word_count + 400, request.target_min_word_count)

    return render_prompt(
        "article_repair",
        {
            "request_data_json": json.dumps(request.request_data, ensure_ascii=False, indent=2),
            "quality_errors_json": json.dumps(request.quality_errors, ensure_ascii=False, indent=2),
            "quality_warnings_json": json.dumps(request.quality_warnings, ensure_ascii=False, indent=2),
            "target_min_word_count": request.target_min_word_count,
            "target_word_count": target_word_count,
            "pass_number": request.pass_number,
            "structured_article_json": request.article.model_dump_json(indent=2),
            "biomedical_instruction": biomedical_instruction,
            "product_url": request.request_data.get("product_url", ""),
        },
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _apply_required_repairs(article_json: dict[str, Any], request: ArticleRepairRequest) -> dict[str, Any]:
    article = dict(article_json or {})
    product_name = str(request.request_data.get("product_name") or "research material")
    product_url = str(request.request_data.get("product_url") or "")
    target_keyword = str(request.request_data.get("target_keyword") or "the research topic")

    if request.is_biomedical:
        limitations = str(article.get("limitations_and_safety") or "")
        if request.required_disclaimer not in limitations:
            article["limitations_and_safety"] = (
                f"{limitations.rstrip()}\n\n{request.required_disclaimer}".strip()
            )

    links = article.get("internal_links")
    if not isinstance(links, list):
        links = []
    if product_url and not any(isinstance(link, dict) and link.get("url") == product_url for link in links):
        links.append(
            {
                "anchor_text": product_name,
                "url": product_url,
                "reason": "Primary product or category page for research-use context.",
            }
        )
    article["internal_links"] = links

    faq = article.get("faq")
    if not isinstance(faq, list) or not faq:
        article["faq"] = [
            {
                "question": f"What is the research context for {product_name}?",
                "answer": (
                    f"{product_name} is discussed in relation to {target_keyword}, with emphasis on "
                    "laboratory research context, study design, and cautious interpretation of findings."
                ),
            },
            {
                "question": "Why should researchers verify references before using this article?",
                "answer": (
                    "The references listed are leads for human verification, not confirmed citations. "
                    "Researchers should check primary literature, methods, and publication details before relying on them."
                ),
            },
            {
                "question": "What safety framing is required for this topic?",
                "answer": (
                    "Regulated or biomedical research topics should use the required research-use disclaimer and must not "
                    "include human-use, treatment, diagnostic, or dosing recommendations."
                ),
            },
            {
                "question": "How should internal product links be used?",
                "answer": (
                    "Internal links should guide readers to product or category documentation for specifications and "
                    "research-use information without implying therapeutic suitability."
                ),
            },
        ]

    return sanitize_article_safety(article)


def sanitize_article_safety(article_json: dict[str, Any]) -> dict[str, Any]:
    replacements = {
        "safe for": "intended for",
        "treats": "has been studied in relation to",
        "cures": "is not presented as curing",
        "recommended dose": "study design amount",
        "patients should": "research protocols should",
    }
    return _sanitize_value(article_json, replacements)


def _sanitize_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_value(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item, replacements) for item in value]
    if isinstance(value, str):
        sanitized = value
        for forbidden, replacement in replacements.items():
            sanitized = re.sub(re.escape(forbidden), replacement, sanitized, flags=re.IGNORECASE)
        return sanitized
    return value
