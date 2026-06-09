from __future__ import annotations

import re
from typing import Any

from app.ai_opportunity_ideation.article_brief import is_buyer_guide_article, is_science_editorial_article
from app.article_schema import ArticleSchema, normalize_article

_UNCERTAINTY_SENTENCE_RE = re.compile(
    r"(interpretation depends on (?:the )?model(?: design)?|"
    r"evidence remains limited|mechanism remains unsettled|"
    r"mechanism(?:s)? (?:is|are) (?:not fully |still )?(?:settled|understood)|"
    r"readers should (?:be cautious|interpret findings cautiously)|"
    r"findings should be interpreted cautiously|"
    r"results should not be extrapolated|"
    r"preclinical evidence (?:is|remains) limited|"
    r"human relevance (?:is|remains) unclear)",
    re.I,
)

_COMMERCE_PHRASE_RE = re.compile(
    r"\b(supplier listings?|catalog language|shopping implications?|documentation quality checks?|"
    r"product evaluation workflows?|supplier evaluation|catalog selection|interpret(?:ing)? (?:the )?catalog page|"
    r"review(?:ing)? supplier listings?|purchasing decisions?|purchase decisions?)\b",
    re.I,
)

_BUYER_LANGUAGE_SENTENCE_RE = re.compile(
    r"\b(buyers?|shoppers?|purchasing|purchase(?:rs?|ing)?|supplier evaluation|catalog selection|"
    r"shopping|procurement|product page evaluation)\b",
    re.I,
)


def reduce_compliance_repetition(article_json: dict[str, Any]) -> dict[str, Any]:
    """Keep one strong uncertainty/compliance caveat; remove near-duplicate warning sentences."""
    data = dict(article_json or {})
    seen: set[str] = set()
    kept_primary = False

    limitations = str(data.get("limitations_and_safety") or "")
    if limitations:
        data["limitations_and_safety"], kept_primary, seen = _dedupe_uncertainty_sentences(
            limitations,
            prefer_keep=True,
            kept_primary=kept_primary,
            seen=seen,
        )

    research_context = str(data.get("research_context") or "")
    if research_context:
        data["research_context"], kept_primary, seen = _dedupe_uncertainty_sentences(
            research_context,
            prefer_keep=False,
            kept_primary=kept_primary,
            seen=seen,
        )

    sections = data.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section["content_markdown"], kept_primary, seen = _dedupe_uncertainty_sentences(
                str(section.get("content_markdown") or ""),
                prefer_keep=False,
                kept_primary=kept_primary,
                seen=seen,
            )
            for subsection in section.get("subsections") or []:
                if isinstance(subsection, dict):
                    subsection["content_markdown"], kept_primary, seen = _dedupe_uncertainty_sentences(
                        str(subsection.get("content_markdown") or ""),
                        prefer_keep=False,
                        kept_primary=kept_primary,
                        seen=seen,
                    )
    return data


def strip_commerce_language_for_science_articles(
    article_json: dict[str, Any],
    *,
    opportunity_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Remove buyer/supplier/catalog phrasing from science editorial articles."""
    context = opportunity_context or {}
    if not is_science_editorial_article(context) or is_buyer_guide_article(context):
        return article_json

    data = dict(article_json or {})
    prose_fields = ("research_context", "limitations_and_safety", "excerpt")
    for field in prose_fields:
        data[field] = _strip_commerce_language(str(data.get(field) or ""))

    faq = data.get("faq")
    if isinstance(faq, list):
        for item in faq:
            if isinstance(item, dict):
                item["answer"] = _strip_commerce_language(str(item.get("answer") or ""))

    sections = data.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section["content_markdown"] = _strip_commerce_language(str(section.get("content_markdown") or ""))
            for subsection in section.get("subsections") or []:
                if isinstance(subsection, dict):
                    subsection["content_markdown"] = _strip_commerce_language(
                        str(subsection.get("content_markdown") or "")
                    )
    return data


def apply_editorial_post_processing(
    article: ArticleSchema,
    *,
    defaults: dict[str, str],
    opportunity_context: dict[str, Any] | None,
) -> ArticleSchema:
    from app.review.article_composition import apply_article_composition_refinement

    data = article.model_dump()
    data = reduce_compliance_repetition(data)
    data = strip_commerce_language_for_science_articles(data, opportunity_context=opportunity_context)
    data = apply_article_composition_refinement(
        data,
        opportunity_context=opportunity_context,
        defaults=defaults,
    )
    return normalize_article(data, defaults=defaults)


def _dedupe_uncertainty_sentences(
    text: str,
    *,
    prefer_keep: bool,
    kept_primary: bool,
    seen: set[str],
) -> tuple[str, bool, set[str]]:
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        sentences = _split_sentences(paragraph)
        kept: list[str] = []
        for sentence in sentences:
            if _UNCERTAINTY_SENTENCE_RE.search(sentence):
                key = _uncertainty_key(sentence)
                if key in seen:
                    continue
                if prefer_keep or not kept_primary:
                    seen.add(key)
                    kept_primary = True
                    kept.append(sentence)
                continue
            kept.append(sentence)
        if kept:
            paragraphs.append(" ".join(kept).strip())
    return "\n\n".join(paragraphs).strip(), kept_primary, seen


def _strip_commerce_language(text: str) -> str:
    if not text:
        return ""
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        sentences = _split_sentences(paragraph)
        kept = [
            sentence
            for sentence in sentences
            if not _BUYER_LANGUAGE_SENTENCE_RE.search(sentence) and not _COMMERCE_PHRASE_RE.search(sentence)
        ]
        if kept:
            paragraphs.append(" ".join(kept).strip())
    cleaned = "\n\n".join(paragraphs).strip()
    cleaned = _COMMERCE_PHRASE_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", value.strip())
    return [part.strip() for part in parts if part.strip()]


def _uncertainty_key(value: str) -> str:
    lowered = value.lower()
    for pattern in (
        "interpretation depends on",
        "evidence remains limited",
        "mechanism remains unsettled",
        "readers should be cautious",
        "findings should be interpreted cautiously",
        "preclinical evidence",
        "human relevance",
    ):
        if pattern in lowered:
            return pattern
    return re.sub(r"\s+", " ", lowered).strip()[:120]
