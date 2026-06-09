from typing import Any

from app.opportunities.schemas import OpportunityScore


def score_opportunity(
    *,
    opportunity: dict[str, Any],
    cluster_authority: float = 0.5,
    audience_fit: float = 0.5,
    competitor_gap: float = 0.5,
) -> OpportunityScore:
    content_role = str(opportunity.get("content_role") or "").lower()
    intent = str(opportunity.get("search_intent") or "").lower()
    funnel = str(opportunity.get("funnel_stage") or "").lower()
    compliance = 0.65 if _contains_sensitive_terms(opportunity) else 0.35
    editorial_effort = 0.72 if content_role in {"pillar", "pillar_page"} else 0.45
    business_value = 0.75 if funnel in {"consideration", "conversion"} else 0.55
    novelty = 0.7 if competitor_gap > 0.55 else 0.48
    semantic_gap = 0.65 if content_role in {"supporting_article", "cluster_support"} else 0.55
    saturation = 0.35 if novelty > 0.6 else 0.55
    authority_fit = max(cluster_authority, 0.55 if content_role.startswith("pillar") else 0.48)
    intent_boost = 0.08 if intent in {"commercial", "comparison", "transactional"} else 0

    overall = (
        audience_fit * 0.18
        + authority_fit * 0.18
        + semantic_gap * 0.16
        + competitor_gap * 0.14
        + novelty * 0.1
        + business_value * 0.14
        + (1 - editorial_effort) * 0.05
        + (1 - compliance) * 0.05
        + intent_boost
    )

    return OpportunityScore(
        overall=_clamp(overall),
        audience_fit=_clamp(audience_fit),
        authority_fit=_clamp(authority_fit),
        semantic_gap=_clamp(semantic_gap),
        competitor_gap=_clamp(competitor_gap),
        novelty=_clamp(novelty),
        saturation=_clamp(saturation),
        business_value=_clamp(business_value),
        editorial_effort=_clamp(editorial_effort),
        compliance_sensitivity=_clamp(compliance),
    )


def _contains_sensitive_terms(opportunity: dict[str, Any]) -> bool:
    text = " ".join(
        str(opportunity.get(key) or "")
        for key in ("title", "target_keyword", "rationale", "product_name")
    ).lower()
    return any(term in text for term in ("medical", "dose", "dosage", "treat", "therapy", "disease", "cure", "diagnose"))


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
