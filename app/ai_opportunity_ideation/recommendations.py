from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context
from app.catalog.filters import normalize_topic_label
from app.recommendations.classification import annotate_recommendation_classification
from app.recommendations.source_audit import annotate_recommendation_sources

IDEATION_ONLY_SOURCE_TYPE = "ai_opportunity_ideation"


def group_recommendations(recommendations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in recommendations:
        grouped[str(item.get("action") or "monitor")].append(item)
    for action in list(grouped):
        grouped[action] = sorted(grouped[action], key=lambda item: item.get("score") or 0, reverse=True)
    return {
        "recommended_now": [
            *grouped.get("create", [])[:12],
            *grouped.get("expand", [])[:5],
        ][:20],
        "refresh_existing": [
            *grouped.get("refresh", [])[:12],
            *grouped.get("merge", [])[:8],
        ][:20],
        "monitor": grouped.get("monitor", [])[:20],
        "ignore": grouped.get("ignore", [])[:50],
        "by_action": dict(grouped),
    }


def recommendation_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = group_recommendations(recommendations)
    return {
        "total": len(recommendations),
        "recommended_now": len(grouped["recommended_now"]),
        "refresh_existing": len(grouped["refresh_existing"]),
        "monitor": len(grouped["monitor"]),
        "ignore": len(grouped["ignore"]),
        "high_priority": len([item for item in recommendations if item.get("priority") == "high"]),
    }

LEGACY_RECOMMENDATION_SOURCE_TYPES = frozenset(
    {
        "niche_profile",
        "existing_opportunity",
        "coverage",
        "published_content",
        "competitor",
        "demand_observation",
        "demand_intent",
        "trend_signal",
        "ai_editorial_strategist",
        "editorial_opportunity",
        "market_intelligence",
        "opportunity_intelligence",
        "inferred",
    }
)


def validate_ideation_only_recommendation_rows(rows: list[dict[str, Any]]) -> None:
    """Raise if any row is not from AI opportunity ideation (product-mode guard)."""
    for index, row in enumerate(rows):
        source = str(row.get("source_type") or "").strip().lower()
        if source != IDEATION_ONLY_SOURCE_TYPE:
            raise ValueError(
                f"Recommendation row {index} has source_type={source!r}; "
                f"expected {IDEATION_ONLY_SOURCE_TYPE!r} in ideation-only mode."
            )
        legacy = LEGACY_RECOMMENDATION_SOURCE_TYPES - {IDEATION_ONLY_SOURCE_TYPE}
        if source in legacy:
            raise ValueError(f"Legacy source_type {source!r} is not allowed in ideation-only mode.")


def assert_ideation_only_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validate_ideation_only_recommendation_rows(rows)
    return rows


def ideation_opportunities_to_recommendation_rows(
    rows: list[dict[str, Any]],
    *,
    analysis_job_id: str | None = None,
) -> list[dict[str, Any]]:
    """Map persisted ideation opportunities directly to recommendation rows (no OI merge/review)."""
    recommendations: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        headline = str(row.get("headline") or "").strip()
        if not headline:
            continue
        topic = normalize_topic_label(headline)
        rec_type = str(row.get("recommendation_type") or "create").lower()
        action = rec_type if rec_type in {"create", "refresh", "expand", "monitor", "ignore"} else "create"
        if rec_type == "follow_up":
            action = "create"
        abstract = str(row.get("abstract") or "").strip()
        priority_reason = str(row.get("priority_reason") or abstract).strip()
        article_brief = enrich_article_opportunity_context(
            {
                "headline": headline,
                "abstract": abstract,
                "search_intent": str(row.get("search_intent") or ""),
                "content_type": str(row.get("content_type") or ""),
                "recommendation_type": rec_type,
                "related_products": list(row.get("related_products") or []),
                "related_topics": list(row.get("related_topics") or []),
                "target_audience": str(row.get("target_audience") or ""),
                "priority_reason": priority_reason,
                "safety_notes": list(row.get("safety_notes") or []),
                "source": "ai_opportunity_ideation",
            }
        )
        metadata = {
            "ideation_opportunity_id": row.get("id"),
            "abstract": abstract,
            "search_intent": str(row.get("search_intent") or ""),
            "content_type": str(row.get("content_type") or ""),
            "recommendation_type": rec_type,
            "related_products": list(row.get("related_products") or []),
            "related_topics": list(row.get("related_topics") or []),
            "target_audience": str(row.get("target_audience") or ""),
            "priority_reason": priority_reason,
            "safety_notes": list(row.get("safety_notes") or []),
            "rationale": priority_reason,
            "source_label": "AI opportunity ideation",
            "site_first": True,
            "direct_from_ideation": True,
            "science_focus": bool(article_brief.get("science_focus")),
            "article_brief": article_brief,
        }
        recommendations.append(
            {
                "id": str(uuid4()),
                "title": headline,
                "topic": topic,
                "target_keyword": topic,
                "action": action,
                "priority": "high" if action == "create" else "medium",
                "confidence": 0.85,
                "score": 0.9 if action == "create" else 0.75,
                "source_type": "ai_opportunity_ideation",
                "source_id": str(row.get("id") or ""),
                "analysis_job_id": analysis_job_id,
                "business_relevance": 0.85,
                "niche_relevance": 0.85,
                "trend_relevance": 0.0,
                "coverage_gap": 0.9,
                "freshness": 0.85,
                "audience_relevance": 0.8,
                "competitor_gap": 0.0,
                "cannibalization_risk": 0.1,
                "demand_score": 0.0,
                "velocity_score": 0.0,
                "source_diversity": 0.0,
                "evidence_confidence": 0.85,
                "has_external_evidence": False,
                "demand_summary": abstract,
                "explanation": priority_reason or abstract,
                "reasons": ["ai_opportunity_ideation"],
                "evidence": [{"type": "ai_opportunity_ideation", "summary": priority_reason or abstract}],
                "metadata": metadata,
                "status": "active",
            }
        )
    annotated: list[dict[str, Any]] = []
    for rec in recommendations:
        item = annotate_recommendation_classification(rec)
        annotated.append(item)
    result = annotate_recommendation_sources(annotated)
    validate_ideation_only_recommendation_rows(result)
    return result
