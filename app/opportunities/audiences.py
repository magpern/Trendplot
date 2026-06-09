from typing import Any
from uuid import uuid4

from app.opportunities.schemas import AudienceProfile


def infer_audiences(signal_inventory: dict[str, Any], ai_audiences: Any = None) -> list[AudienceProfile]:
    normalized = [_normalize_ai_audience(item) for item in ai_audiences or [] if isinstance(item, dict)]
    normalized = [item for item in normalized if item is not None]
    if normalized:
        return normalized[:12]

    terms = [item["term"] for item in signal_inventory.get("terms", [])[:20]]
    questions = signal_inventory.get("questions", [])[:8]
    entities = signal_inventory.get("entities", [])[:12]

    profiles = [
        AudienceProfile(
            id=str(uuid4()),
            name="Research-oriented readers",
            description="Visitors looking for educational context, definitions, mechanisms, and careful sourcing.",
            audience_type="research",
            expertise_level="intermediate",
            confidence=0.72,
            commercial_intent=0.25,
            research_intent=0.85,
            recurring_questions=questions,
            authority_topics=terms[:8],
            related_entities=entities[:8],
            preferred_content_types=["explainers", "research roundups", "definitions"],
            source_signals={"source": "deterministic", "terms": terms[:10]},
        ),
        AudienceProfile(
            id=str(uuid4()),
            name="Comparison and sourcing visitors",
            description="Visitors evaluating options, product/category fit, trust signals, and practical next steps.",
            audience_type="commercial_research",
            expertise_level="mixed",
            confidence=0.66,
            commercial_intent=0.7,
            research_intent=0.55,
            concerns=["quality", "availability", "handling", "documentation"],
            authority_topics=terms[5:14],
            related_entities=entities[5:14],
            preferred_content_types=["comparisons", "buyer guides", "checklists"],
            source_signals={"source": "deterministic", "product_candidates": signal_inventory.get("product_candidates", [])[:5]},
        ),
    ]
    return profiles


def _normalize_ai_audience(item: dict[str, Any]) -> AudienceProfile | None:
    name = str(item.get("name") or item.get("audience") or "").strip()
    if not name:
        return None
    return AudienceProfile(
        id=str(item.get("id") or uuid4()),
        name=name,
        description=str(item.get("description") or item.get("rationale") or ""),
        audience_type=str(item.get("audience_type") or item.get("type") or "inferred"),
        expertise_level=str(item.get("expertise_level") or "mixed"),
        confidence=_score(item.get("confidence"), 0.65),
        commercial_intent=_score(item.get("commercial_intent"), 0.4),
        research_intent=_score(item.get("research_intent"), 0.6),
        concerns=_list(item.get("concerns")),
        recurring_questions=_list(item.get("recurring_questions") or item.get("questions")),
        preferred_content_types=_list(item.get("preferred_content_types")),
        authority_topics=_list(item.get("authority_topics") or item.get("topics")),
        related_entities=_list(item.get("related_entities") or item.get("entities")),
        related_clusters=_list(item.get("related_clusters")),
        source_signals=item.get("source_signals") if isinstance(item.get("source_signals"), dict) else {"source": "ai"},
    )


def _score(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    if numeric > 1:
        numeric = numeric / 100
    return max(0, min(1, numeric))


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]
