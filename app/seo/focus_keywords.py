from __future__ import annotations

import re
from typing import Iterable

from app.seo.text_utils import keyword_in_text, normalize_keyword

MAX_FOCUS_KEYWORDS = 2
_FOCUS_SPLIT = re.compile(r"[,;]")


def all_focus_keyword_phrases(value: str) -> list[str]:
    keywords: list[str] = []
    for chunk in _FOCUS_SPLIT.split(str(value or "")):
        text = normalize_keyword(chunk)
        if not text:
            continue
        if any(existing.lower() == text.lower() for existing in keywords):
            continue
        keywords.append(text)
    return keywords


def parse_focus_keywords(value: str) -> list[str]:
    return all_focus_keyword_phrases(value)[:MAX_FOCUS_KEYWORDS]


def format_focus_keywords(keywords: Iterable[str]) -> str:
    cleaned: list[str] = []
    for item in keywords:
        text = normalize_keyword(str(item or ""))
        if not text:
            continue
        if any(existing.lower() == text.lower() for existing in cleaned):
            continue
        cleaned.append(text)
        if len(cleaned) >= MAX_FOCUS_KEYWORDS:
            break
    return ", ".join(cleaned)


def product_entity_names(
    *,
    product_name: str = "",
    related_products: Iterable[str] | None = None,
) -> list[str]:
    entities: list[str] = []
    for raw in [product_name, *(related_products or [])]:
        text = normalize_keyword(str(raw or ""))
        if not text:
            continue
        if any(existing.lower() == text.lower() for existing in entities):
            continue
        entities.append(text)
    return entities


def phrase_contains_entity(phrase: str, entities: Iterable[str]) -> bool:
    lowered = str(phrase or "").lower()
    if not lowered:
        return False
    for entity in entities:
        entity_text = normalize_keyword(str(entity or ""))
        if entity_text and entity_text.lower() in lowered:
            return True
    return False


def normalize_seo_focus_keywords(
    raw: str,
    *,
    primary_fallback: str = "",
    product_name: str = "",
    related_products: Iterable[str] | None = None,
) -> str:
    """Normalize Rank Math focus keyword string: max two phrases, product entity when available."""
    keywords = parse_focus_keywords(raw)
    primary_fallback = normalize_keyword(primary_fallback)

    if not keywords and primary_fallback:
        keywords = [primary_fallback]

    if not keywords:
        return ""

    primary = keywords[0]
    secondary = keywords[1] if len(keywords) > 1 else ""

    entities = product_entity_names(product_name=product_name, related_products=related_products)
    if entities:
        has_entity = any(phrase_contains_entity(keyword, entities) for keyword in keywords)
        if not has_entity:
            entity = entities[0]
            if entity.lower() != primary.lower():
                secondary = entity
            elif len(entities) > 1:
                secondary = entities[1]
        if not secondary:
            for entity in entities:
                if entity.lower() != primary.lower():
                    secondary = entity
                    break

    result = [primary]
    if secondary and secondary.lower() != primary.lower():
        result.append(secondary)
    return format_focus_keywords(result)


def primary_focus_keyword(value: str) -> str:
    parts = parse_focus_keywords(value)
    return parts[0] if parts else ""


def secondary_focus_keywords(value: str) -> list[str]:
    parts = parse_focus_keywords(value)
    return parts[1:]


def count_keyword_occurrences_multi(text: str, keywords: Iterable[str]) -> dict[str, int]:
    from app.seo.text_utils import count_keyword_occurrences

    return {keyword: count_keyword_occurrences(text, keyword) for keyword in parse_focus_keywords(format_focus_keywords(keywords))}
