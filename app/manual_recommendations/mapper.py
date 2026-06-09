from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context
from app.catalog.filters import normalize_topic_label
from app.recommendations.classification import annotate_recommendation_classification
from app.recommendations.source_audit import annotate_recommendation_sources

MANUAL_SOURCE_TYPE = "manual_recommendation"


def manual_recommendation_to_row(
    manual: dict[str, Any],
    *,
    analysis_job_id: str | None = None,
) -> dict[str, Any]:
    headline = str(manual.get("enhanced_headline") or manual.get("raw_headline") or "").strip()
    abstract = str(manual.get("abstract") or "").strip()
    raw_notes = str(manual.get("raw_notes") or "").strip()
    topic = normalize_topic_label(headline)
    rec_type = str(manual.get("recommendation_type") or "create").lower()
    action = rec_type if rec_type in {"create", "refresh", "expand", "monitor", "ignore"} else "create"
    priority_reason = str(manual.get("priority_reason") or abstract).strip()

    article_brief = enrich_article_opportunity_context(
        {
            "headline": headline,
            "abstract": abstract,
            "search_intent": str(manual.get("search_intent") or ""),
            "content_type": str(manual.get("content_type") or ""),
            "recommendation_type": rec_type,
            "related_products": list(manual.get("related_products") or []),
            "related_topics": list(manual.get("related_topics") or []),
            "target_audience": str(manual.get("target_audience") or ""),
            "priority_reason": priority_reason,
            "safety_notes": list(manual.get("safety_notes") or []),
            "raw_notes": raw_notes,
            "source": "manual_recommendation",
            "manual_recommendation_id": manual.get("id"),
        }
    )

    metadata = {
        "manual_recommendation_id": manual.get("id"),
        "raw_headline": manual.get("raw_headline"),
        "raw_notes": raw_notes,
        "abstract": abstract,
        "search_intent": str(manual.get("search_intent") or ""),
        "content_type": str(manual.get("content_type") or ""),
        "recommendation_type": rec_type,
        "related_products": list(manual.get("related_products") or []),
        "related_topics": list(manual.get("related_topics") or []),
        "target_audience": str(manual.get("target_audience") or ""),
        "priority_reason": priority_reason,
        "safety_notes": list(manual.get("safety_notes") or []),
        "rationale": priority_reason,
        "source_label": "Manual · AI-enhanced",
        "manual_source": True,
        "ai_enhanced": True,
        "science_focus": bool(article_brief.get("science_focus")),
        "article_brief": article_brief,
        "duplicate_warnings": list(manual.get("duplicate_warnings") or []),
    }

    row = {
        "id": str(manual.get("recommendation_id") or uuid4()),
        "title": headline,
        "topic": topic,
        "target_keyword": topic,
        "action": action,
        "priority": "high" if action == "create" else "medium",
        "confidence": 0.9,
        "score": 0.92,
        "source_type": MANUAL_SOURCE_TYPE,
        "source_id": str(manual.get("id") or ""),
        "analysis_job_id": analysis_job_id,
        "business_relevance": 0.9,
        "niche_relevance": 0.9,
        "trend_relevance": 0.0,
        "coverage_gap": 0.95,
        "freshness": 0.9,
        "audience_relevance": 0.85,
        "competitor_gap": 0.0,
        "cannibalization_risk": 0.05,
        "demand_score": 0.0,
        "velocity_score": 0.0,
        "source_diversity": 0.0,
        "evidence_confidence": 0.9,
        "has_external_evidence": False,
        "demand_summary": abstract,
        "explanation": priority_reason or abstract,
        "reasons": ["manual_recommendation"],
        "evidence": [{"type": "manual_recommendation", "summary": priority_reason or abstract}],
        "metadata": metadata,
        "status": "active",
    }
    annotated = annotate_recommendation_classification(row)
    return annotate_recommendation_sources([annotated])[0]
