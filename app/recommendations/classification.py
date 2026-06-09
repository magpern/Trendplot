from __future__ import annotations

import re
from typing import Any

CLASSIFICATIONS = frozenset(
    {
        "glossary",
        "faq",
        "comparison",
        "how_to",
        "calculator",
        "commercial",
        "authority",
        "research",
        "refresh",
        "expand",
        "follow_up",
    }
)

_GLOSSARY_RE = re.compile(r"\b(what is|what are|introduction to|overview of|guide to)\b", re.I)
_FAQ_RE = re.compile(r"\b(faq|frequently asked|questions answered)\b", re.I)
_COMPARISON_RE = re.compile(r"\b(vs\.?|versus|compared with|compared to|best .+ compared)\b", re.I)
_HOW_TO_RE = re.compile(r"\b(how to|how do i|step by step|reconstitut|store|storage|handling)\b", re.I)
_CALC_RE = re.compile(r"\b(calculator|estimator|tool)\b", re.I)
_COMMERCIAL_RE = re.compile(r"\b(buyer'?s guide|pricing|cost|where to buy|shop|product page)\b", re.I)
_AUTHORITY_RE = re.compile(r"\b(ultimate guide|complete guide|definitive|handbook)\b", re.I)
_RESEARCH_RE = re.compile(
    r"\b(research overview|research areas|scientific interest|mechanism|study|methodology|reproducibility|experimental design)\b",
    re.I,
)


def classify_recommendation(
    *,
    title: str,
    topic: str = "",
    action: str = "",
    source_type: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    meta = metadata or {}
    if meta.get("demand_intent_type"):
        intent = str(meta["demand_intent_type"])
        if intent in CLASSIFICATIONS:
            return intent
        if intent == "storage":
            return "how_to"
        if intent == "handling":
            return "how_to"
    if meta.get("content_type"):
        ctype = str(meta["content_type"]).lower().replace("-", "_")
        mapping = {
            "product_education": "glossary",
            "research_overview": "research",
            "category_guide": "authority",
            "supporting_cluster": "research",
            "beginner_guide": "glossary",
            "educational_guide": "how_to",
            "glossary_need": "glossary",
            "comparison": "comparison",
            "faq": "faq",
            "how_to": "how_to",
            "refresh_candidate": "refresh",
            "expansion_candidate": "expand",
        }
        if ctype in mapping:
            return mapping[ctype]
        if ctype in CLASSIFICATIONS:
            return ctype
    if str(action or "").lower() == "refresh":
        return "refresh"
    if str(action or "").lower() == "expand":
        return "expand"
    blob = f"{title} {topic}".strip()
    if _COMPARISON_RE.search(blob):
        return "comparison"
    if _FAQ_RE.search(blob):
        return "faq"
    if _HOW_TO_RE.search(blob):
        return "how_to"
    if _CALC_RE.search(blob):
        return "calculator"
    if _COMMERCIAL_RE.search(blob):
        return "commercial"
    if _AUTHORITY_RE.search(blob):
        return "authority"
    if _GLOSSARY_RE.search(blob):
        return "glossary"
    if _RESEARCH_RE.search(blob):
        return "research"
    if str(source_type or "") in {"editorial_opportunity", "market_intelligence"}:
        return "research"
    if str(source_type or "") == "demand_intent":
        return "how_to"
    return "follow_up"


def annotate_recommendation_classification(rec: dict[str, Any]) -> dict[str, Any]:
    item = dict(rec)
    meta = dict(item.get("metadata") or {})
    classification = classify_recommendation(
        title=str(item.get("title") or ""),
        topic=str(item.get("topic") or ""),
        action=str(item.get("action") or ""),
        source_type=str(item.get("source_type") or ""),
        metadata=meta,
    )
    meta["recommendation_classification"] = classification
    item["metadata"] = meta
    return item


def classification_label(classification: str) -> str:
    return classification.replace("_", " ").title()
