"""Classify AI ideation opportunities by editorial category (validation helper)."""

from __future__ import annotations

import re
from typing import Any

_HANDLING_INTENTS = frozenset({"storage", "reconstitution", "product_handling"})
_HANDLING_RE = re.compile(
    r"\b(storage|reconstitut|handling|stability|inventory|traceability|documentation|freeze[- ]thaw|lyophiliz)\b",
    re.I,
)
_COMPARISON_RE = re.compile(r"\b(vs\.?|versus)\b", re.I)
_RELATIONSHIP_RE = re.compile(
    r"\b(and .+ together|often discussed together|related (pathway|research|theme|signaling)|co[- ]discussion)\b",
    re.I,
)
_MECHANISM_RE = re.compile(
    r"\b(mechanism|signaling|pathway|background explainer|explained|primer|overview of .+ signaling)\b",
    re.I,
)
_SCIENCE_RE = re.compile(
    r"\b(what is|research overview|literature|scientific context|research context)\b",
    re.I,
)
_FAQ_RE = re.compile(r"\b(faq|calculator|checklist|resource guide|glossary)\b", re.I)
_SUPPLIER_RE = re.compile(
    r"\b(supplier|catalog page|catalog selection|product page|procurement|shopping|"
    r"inventory|documentation quality|buyer guide|listing|sku)\b",
    re.I,
)


def classify_ideation_opportunity(row: dict[str, Any]) -> str:
    headline = str(row.get("headline") or "")
    abstract = str(row.get("abstract") or "")
    search_intent = str(row.get("search_intent") or "").lower()
    content_type = str(row.get("content_type") or "").lower()
    blob = f"{headline} {abstract}".lower()

    if search_intent == "mechanism" or content_type == "mechanism_explainer":
        return "mechanism/background"
    if search_intent == "product_relationship" or content_type == "relationship":
        return "product relationship"
    if search_intent == "comparison" or content_type == "comparison" or _COMPARISON_RE.search(headline):
        if _HANDLING_RE.search(blob) and not _MECHANISM_RE.search(blob):
            return "handling/storage/reconstitution"
        return "comparison"
    if search_intent in _HANDLING_INTENTS or (
        search_intent == "how_to" and _HANDLING_RE.search(blob)
    ):
        return "handling/storage/reconstitution"
    if _RELATIONSHIP_RE.search(blob):
        return "product relationship"
    if search_intent == "research_overview" or content_type == "research_overview":
        if _HANDLING_RE.search(blob) and not _SCIENCE_RE.search(blob):
            return "handling/storage/reconstitution"
        return "product/science overview"
    if _MECHANISM_RE.search(blob):
        return "mechanism/background"
    if _SCIENCE_RE.search(blob):
        return "product/science overview"
    if search_intent in {"faq", "calculator"} or content_type in {"faq", "calculator_support"} or _FAQ_RE.search(blob):
        return "FAQ/resource/calculator"
    if _HANDLING_RE.search(blob):
        return "handling/storage/reconstitution"
    if _SUPPLIER_RE.search(blob):
        return "supplier/catalog guidance"
    return "other"


def summarize_category_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        category = classify_ideation_opportunity(row)
        counts[category] = counts.get(category, 0) + 1
    total = len(rows) or 1
    pct = {key: round(100 * value / total, 1) for key, value in counts.items()}
    return {"counts": counts, "pct": pct, "total": len(rows)}
