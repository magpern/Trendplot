from typing import Any
from uuid import uuid4

from app.opportunities.schemas import OpportunityCluster


def build_clusters(signal_inventory: dict[str, Any], ai_clusters: Any = None) -> list[OpportunityCluster]:
    clusters = [_normalize_ai_cluster(item) for item in ai_clusters or [] if isinstance(item, dict)]
    clusters = [item for item in clusters if item is not None]
    if clusters:
        return clusters[:30]

    terms = [item["term"] for item in signal_inventory.get("terms", [])]
    entities = signal_inventory.get("entities", [])
    semantic_concepts = signal_inventory.get("semantic_expansion", {}).get("concepts", [])
    competitor_gaps = signal_inventory.get("competitor_intelligence", {}).get("missing_topics", [])
    niche = signal_inventory.get("niche_intelligence", {})
    product_topics = signal_inventory.get("product_intelligence", {}).get("related_topics", [])
    buckets = [
        ("Niche Authority", semantic_concepts[:14] or terms[:14], entities[:10], True, "pillar"),
        ("Product And Mechanism Education", product_topics[:14] or terms[4:18], entities[4:18], False, "support"),
        ("Audience Questions And Myths", signal_inventory.get("questions", [])[:12] or semantic_concepts[8:22], semantic_concepts[8:22], False, "support"),
        ("Competitor Semantic Gaps", competitor_gaps[:16], competitor_gaps[:12], False, "gap"),
        ("Adjacent Interest Expansion", niche.get("adjacent_niches", []) + niche.get("secondary_niches", []), semantic_concepts[12:28], False, "support"),
    ]

    return [
        OpportunityCluster(
            id=str(uuid4()),
            name=name,
            description=f"Topic group inferred from crawl signals around {', '.join(source_terms[:4])}.",
            entities=[str(entity) for entity in cluster_entities if entity],
            source_terms=[str(term) for term in source_terms if term],
            confidence=0.65 if source_terms else 0.45,
            authority_value=0.78 if pillar else 0.6,
            seo_value=0.7 if source_terms else 0.45,
            editorial_value=0.72,
            geo_value=0.55,
            pillar_candidate=pillar,
            semantic_authority_role=role,
        )
        for name, source_terms, cluster_entities, pillar, role in buckets
        if source_terms
    ]


def _normalize_ai_cluster(item: dict[str, Any]) -> OpportunityCluster | None:
    name = str(item.get("name") or item.get("cluster") or "").strip()
    if not name:
        return None
    return OpportunityCluster(
        id=str(item.get("id") or uuid4()),
        name=name,
        description=str(item.get("description") or ""),
        parent_cluster_id=item.get("parent_cluster_id"),
        entities=_list(item.get("entities")),
        source_terms=_list(item.get("source_terms") or item.get("keywords")),
        confidence=_score(item.get("confidence"), 0.65),
        authority_value=_score(item.get("authority_value"), 0.5),
        seo_value=_score(item.get("seo_value"), 0.5),
        editorial_value=_score(item.get("editorial_value"), 0.5),
        geo_value=_score(item.get("geo_value"), 0.5),
        primary_audiences=_list(item.get("primary_audiences")),
        audience_overlap=_list(item.get("audience_overlap")),
        pillar_candidate=bool(item.get("pillar_candidate") or item.get("content_role") == "pillar"),
        semantic_authority_role=str(item.get("semantic_authority_role") or item.get("role") or "support"),
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
