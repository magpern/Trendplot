import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.article_schema import ArticleSchema, normalize_article
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask
from app.review.article_repair import sanitize_article_safety


AI_PHRASES = (
    "rapidly evolving field",
    "pivotal area",
    "delves into",
    "fascinating",
    "unlocking potential",
    "game-changer",
    "exciting prospects",
    "in today's",
    "it is important to note",
    "as discussed above",
    "plays a crucial role",
    "shed light on",
)


SMART_PUNCTUATION = {
    "\u2014": ", ",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
}


@dataclass(slots=True)
class HumanizationResult:
    article: ArticleSchema
    prompt: str
    summary: dict[str, Any] = field(default_factory=dict)
    generated: GeneratedContent | None = None


class ArticleHumanizer:
    async def humanize(
        self,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        required_disclaimer: str,
        target_min_word_count: int,
    ) -> HumanizationResult:
        prompt = build_humanization_prompt(
            article=article,
            request_data=request_data,
            required_disclaimer=required_disclaimer,
            target_min_word_count=target_min_word_count,
        )
        generated = await content_provider.generate_article(prompt, task_type=ModelTask.HUMANIZATION)
        payload = generated.content_json or {}
        article_json = payload.get("article") if isinstance(payload.get("article"), dict) else payload
        cleaned = cleanup_article_json(article_json or article.model_dump(), required_disclaimer)
        humanized = normalize_article(
            cleaned,
            defaults={
                "title": str(request_data.get("title") or article.title),
                "target_keyword": str(request_data.get("target_keyword") or article.primary_keyword),
                "product_name": str(request_data.get("product_name") or ""),
                "product_url": str(request_data.get("product_url") or ""),
            },
        )
        summary = payload.get("humanization_summary") if isinstance(payload.get("humanization_summary"), dict) else {}
        if not summary:
            summary = {
                "attempted": True,
                "notes": "Humanization completed and deterministic cleanup was applied.",
            }
        return HumanizationResult(
            article=humanized,
            prompt=prompt,
            summary=summary,
            generated=generated,
        )


def build_humanization_prompt(
    article: ArticleSchema,
    request_data: dict[str, Any],
    required_disclaimer: str,
    target_min_word_count: int,
) -> str:
    return render_prompt(
        "humanization",
        {
            "request_data_json": json.dumps(request_data, ensure_ascii=False, indent=2),
            "article_json": article.model_dump_json(indent=2),
            "required_disclaimer": required_disclaimer,
            "target_min_word_count": target_min_word_count,
            "ai_phrases": ", ".join(AI_PHRASES),
        },
    )


def cleanup_article_json(article_json: dict[str, Any], required_disclaimer: str) -> dict[str, Any]:
    cleaned = sanitize_article_safety(_cleanup_value(article_json))
    cleaned = _dedupe_required_disclaimer(cleaned, required_disclaimer)
    text = json.dumps(cleaned)
    if required_disclaimer and required_disclaimer not in text:
        limitations = str(cleaned.get("limitations_and_safety") or "")
        cleaned["limitations_and_safety"] = f"{limitations.rstrip()}\n\n{required_disclaimer}".strip()
    return cleaned


def cleanup_text(value: str) -> str:
    cleaned = value
    for source, replacement in SMART_PUNCTUATION.items():
        cleaned = cleaned.replace(source, replacement)
    for phrase in AI_PHRASES:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    cleaned = _reduce_repetitive_sentence_openers(cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *, *([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _reduce_repetitive_sentence_openers(value: str) -> str:
    replacements = {
        r"\bResearchers should also\b": "It is also useful to",
        r"\bResearchers should\b": "Research teams should",
        r"\bThis article\b": "The discussion",
        r"\bThis section\b": "This part",
    }
    cleaned = value
    for pattern, replacement in replacements.items():
        matches = list(re.finditer(pattern, cleaned, flags=re.IGNORECASE))
        for match in matches[1:]:
            cleaned = f"{cleaned[:match.start()]}{replacement}{cleaned[match.end():]}"
    return cleaned


def _dedupe_required_disclaimer(article_json: dict[str, Any], required_disclaimer: str) -> dict[str, Any]:
    if not required_disclaimer:
        return article_json
    seen = False

    def visit(value: Any) -> Any:
        nonlocal seen
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            if required_disclaimer not in value:
                return value
            if not seen:
                seen = True
                return value
            return value.replace(required_disclaimer, "").strip()
        return value

    return visit(article_json)


def _cleanup_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _cleanup_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cleanup_value(item) for item in value]
    if isinstance(value, str):
        return cleanup_text(value)
    return value
