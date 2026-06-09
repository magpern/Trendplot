from __future__ import annotations

import itertools
import re
from typing import Any

from app.catalog.filters import is_entity_quality_junk, normalize_topic_label
from app.opportunity_intelligence.models import OpportunityCandidate

_INTENT_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("comparison", "{a} vs {b}", "{a} vs {b}"),
    ("faq", "{product} FAQ", "{product} frequently asked questions"),
    ("how_to", "How to Reconstitute {product}", "how to reconstitute {product}"),
    ("how_to", "How to Store {product}", "how to store {product}"),
    ("storage", "{product} Storage Guide", "{product} storage guide"),
    ("handling", "{product} Handling Guide", "{product} handling guide"),
    ("troubleshooting", "{product} Troubleshooting Guide", "{product} troubleshooting"),
    ("calculator", "{product} Dosage Calculator Guide", "{product} calculator guide"),
    ("how_to", "{category} Buyer's Guide", "{category} buyer guide"),
    ("comparison", "Best {category} Options Compared", "best {category} compared"),
)


def _products(profile: dict[str, Any] | None) -> list[str]:
    profile = profile or {}
    items: list[str] = []
    for key in ("known_products", "known_entities"):
        for row in profile.get(key) or []:
            text = normalize_topic_label(str(row if not isinstance(row, dict) else row.get("name") or row.get("title") or ""))
            if not text or len(text) < 3:
                continue
            if key == "known_entities" and is_entity_quality_junk(text):
                continue
            items.append(text)
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= 20:
            break
    return out


def _categories(profile: dict[str, Any] | None) -> list[str]:
    profile = profile or {}
    out: list[str] = []
    for row in profile.get("known_categories") or []:
        text = normalize_topic_label(str(row))
        if text and not is_entity_quality_junk(text):
            out.append(text)
        if len(out) >= 10:
            break
    return out


def demand_intent_candidates(
    niche_profile: dict[str, Any] | None,
    *,
    max_candidates: int = 40,
) -> list[OpportunityCandidate]:
    """Deterministic search-intent expansions from catalog products/categories."""
    products = _products(niche_profile)
    categories = _categories(niche_profile)
    if not products and not categories:
        return []

    candidates: list[OpportunityCandidate] = []
    seen: set[str] = set()

    def add(intent_type: str, title: str, topic: str, keyword: str, entity: str = "") -> None:
        key = topic.lower()
        if key in seen:
            return
        if intent_type != "comparison" and is_entity_quality_junk(topic):
            return
        seen.add(key)
        candidates.append(
            OpportunityCandidate(
                topic=topic,
                title=title,
                source_type="demand_intent",
                target_keyword=keyword,
                business_relevance=0.72,
                niche_relevance=0.7,
                coverage_gap=0.78,
                confidence=0.62,
                trend_relevance=0.45,
                audience_relevance=0.68,
                competitor_gap=0.35,
                reasons=[f"Demand-intent pattern: {intent_type}"],
                metadata={
                    "demand_intent_type": intent_type,
                    "demand_intent_entity": entity or topic,
                    "action_hint": "create",
                },
            )
        )

    for a, b in itertools.combinations(products[:8], 2):
        title = f"{a} vs {b}"
        topic = normalize_topic_label(f"{a.lower()} vs {b.lower()}")
        add("comparison", title, topic, topic, entity=a)
        if len(candidates) >= max_candidates:
            return candidates

    for product in products:
        slug = product
        for intent_type, title_t, kw_t in _INTENT_PATTERNS:
            if intent_type == "comparison":
                continue
            if "{category}" in title_t and not categories:
                continue
            title = title_t.format(product=slug, category=categories[0] if categories else slug, a=slug, b="")
            topic = normalize_topic_label(kw_t.format(product=slug.lower(), category=(categories[0] if categories else slug).lower(), a=slug, b=""))
            add(intent_type, title, topic, topic, entity=slug)
            if len(candidates) >= max_candidates:
                return candidates

    for category in categories:
        for intent_type, title_t, kw_t in _INTENT_PATTERNS:
            if intent_type == "comparison" or "{product}" in title_t:
                continue
            title = title_t.format(category=category, product=category, a=category, b="")
            topic = normalize_topic_label(kw_t.format(category=category.lower(), product=category.lower(), a=category, b=""))
            add(intent_type, title, topic, topic, entity=category)
            if len(candidates) >= max_candidates:
                return candidates

    return candidates[:max_candidates]
