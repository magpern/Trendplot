from __future__ import annotations

from collections import Counter
from typing import Any

SOURCE_TYPE_TO_BUCKET: dict[str, str] = {
    "niche_profile": "entity",
    "existing_opportunity": "entity",
    "ai_editorial_strategist": "entity",
    "ai_opportunity_ideation": "entity",
    "editorial_opportunity": "research",
    "market_intelligence": "research",
    "coverage": "coverage",
    "published_content": "coverage",
    "competitor": "competitor",
    "demand_observation": "demand",
    "demand_intent": "demand",
    "trend_signal": "trend",
}

BUCKET_LABELS = {
    "entity": "entity",
    "coverage": "coverage",
    "competitor": "competitor",
    "demand": "demand",
    "trend": "trend",
    "research": "research",
}

ORIGIN_DISPLAY: dict[str, str] = {
    "entity": "Entity",
    "coverage": "Coverage Gap",
    "competitor": "Competitor Gap",
    "demand": "Demand Intent",
    "trend": "Trend Signal",
    "research": "Research",
}


def origin_display_label(bucket: str) -> str:
    return ORIGIN_DISPLAY.get(bucket, bucket.replace("_", " ").title())


def recommendation_source_bucket(source_type: str, metadata: dict[str, Any] | None = None) -> str:
    meta = metadata or {}
    if meta.get("demand_intent_type"):
        return "demand"
    if meta.get("competitor_derived") or meta.get("competitor_mapping"):
        return "competitor"
    bucket = SOURCE_TYPE_TO_BUCKET.get(str(source_type or "").strip().lower())
    if bucket:
        return bucket
    if "competitor" in str(source_type or "").lower():
        return "competitor"
    if "demand" in str(source_type or "").lower():
        return "demand"
    if "trend" in str(source_type or "").lower():
        return "trend"
    return "entity"


def annotate_recommendation_source(rec: dict[str, Any]) -> dict[str, Any]:
    return annotate_recommendation_sources([rec])[0]


def annotate_recommendation_sources(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for rec in recommendations:
        item = dict(rec)
        meta = dict(item.get("metadata") or {})
        bucket = recommendation_source_bucket(str(item.get("source_type") or ""), meta)
        meta["recommendation_source_bucket"] = bucket
        meta["recommendation_origin"] = str(item.get("source_type") or "")
        item["metadata"] = meta
        annotated.append(item)
    return annotated


def recommendation_source_composition(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for rec in recommendations:
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        bucket = meta.get("recommendation_source_bucket") or recommendation_source_bucket(
            str(rec.get("source_type") or ""), meta
        )
        counts[bucket] += 1
    total = sum(counts.values())
    return {
        "recommendation_sources": dict(counts),
        "total": total,
        "entity_pct": round(100 * counts.get("entity", 0) / total, 1) if total else 0.0,
        "demand_pct": round(100 * counts.get("demand", 0) / total, 1) if total else 0.0,
        "competitor_pct": round(100 * counts.get("competitor", 0) / total, 1) if total else 0.0,
    }
