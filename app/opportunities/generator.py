from typing import Any
from uuid import uuid4

from app.opportunities.schemas import AudienceProfile, Opportunity, OpportunityCluster
from app.opportunities.scoring import score_opportunity


OPPORTUNITY_TYPES = (
    "pillar_page",
    "semantic_support_article",
    "comparison_article",
    "question_article",
    "definition_article",
    "competitor_gap_article",
    "buyer_guide",
    "mechanism_explainer",
    "myth_vs_fact",
    "glossary",
    "industry_trend",
    "laboratory_practice",
    "geo_search",
    "product_deep_dive",
    "faq_cluster",
    "evergreen_authority",
)

NOISE_TERMS = {
    "account",
    "cart",
    "checkout",
    "contact",
    "delivery",
    "disclaimer",
    "login",
    "policy",
    "privacy",
    "refund",
    "returns",
    "shipping",
    "terms",
    "track",
    "why choose",
    "why us",
}


def generate_opportunities(
    *,
    signal_inventory: dict[str, Any],
    audiences: list[AudienceProfile],
    clusters: list[OpportunityCluster],
    ai_opportunities: Any = None,
    fallback_url: str = "",
) -> list[Opportunity]:
    ai_items = [_normalize_ai_opportunity(item, audiences, clusters, fallback_url) for item in ai_opportunities or [] if isinstance(item, dict)]
    opportunities = [item for item in ai_items if item is not None]
    opportunities.extend(_fallback_opportunities(signal_inventory, audiences, clusters, fallback_url))
    opportunities = _quality_filter(opportunities)
    opportunities = _enforce_diversity(opportunities)
    return _dedupe_opportunities(opportunities)[:500]


def _fallback_opportunities(
    signal_inventory: dict[str, Any],
    audiences: list[AudienceProfile],
    clusters: list[OpportunityCluster],
    fallback_url: str,
) -> list[Opportunity]:
    products = signal_inventory.get("product_candidates", []) or [{"name": "Website", "url": fallback_url}]
    questions = signal_inventory.get("questions", [])
    product_intelligence = signal_inventory.get("product_intelligence", {})
    semantic_expansion = signal_inventory.get("semantic_expansion", {})
    semantic_concepts = signal_inventory.get("semantic_expansion", {}).get("concepts", [])
    competitor_gaps = signal_inventory.get("competitor_intelligence", {}).get("missing_topics", [])
    adjacent_topics = signal_inventory.get("niche_intelligence", {}).get("adjacent_niches", [])
    audience_interests = signal_inventory.get("niche_intelligence", {}).get("audience_interests", [])
    external_research = signal_inventory.get("external_research", {})
    external_summary = external_research.get("summary", {}) if isinstance(external_research, dict) else {}
    extracted_products = product_intelligence.get("extracted_products", [])
    related_mechanisms = product_intelligence.get("related_mechanisms", [])
    concept_pool = _clean_terms(
        [
            *semantic_concepts,
            *related_mechanisms,
            *adjacent_topics,
            *audience_interests,
            *external_summary.get("recurring_topics", []),
            *external_summary.get("rising_themes", []),
            *signal_inventory.get("entities", []),
            *(item.get("term", "") for item in signal_inventory.get("terms", [])[:60]),
        ]
    )
    opportunities: list[Opportunity] = []

    for cluster in clusters:
        primary_audience = audiences[0] if audiences else None
        product = products[0]
        base = {
            "cluster_id": cluster.id,
            "product_name": product.get("name", ""),
            "product_url": product.get("url", fallback_url),
            "primary_audience_id": primary_audience.id if primary_audience else None,
            "audience_rationale": "Inferred from the strongest audience and topical cluster overlap.",
        }
        seed_terms = _clean_terms([*cluster.source_terms, *cluster.entities, *concept_pool])[:24]
        if not seed_terms:
            continue
        opportunities.extend(_opportunities_for_cluster(base, cluster, primary_audience, seed_terms, questions, competitor_gaps))

    for product_name in extracted_products[:40]:
        cluster = clusters[0] if clusters else None
        audience = audiences[0] if audiences else None
        product_record = next((item for item in products if item.get("name") == product_name), products[0])
        opportunities.extend(
            _product_entity_opportunities(
                product_name=product_name,
                product_url=product_record.get("url", fallback_url),
                concept_pool=concept_pool,
                expansions=_entity_expansion_for(product_name, semantic_expansion),
                cluster=cluster,
                audience=audience,
            )
        )

    opportunities.extend(
        _product_family_opportunities(
            product_intelligence.get("product_families", []),
            clusters[0] if clusters else None,
            audiences[0] if audiences else None,
            fallback_url,
        )
    )
    opportunities.extend(
        _external_research_opportunities(
            external_research,
            clusters[0] if clusters else None,
            audiences[0] if audiences else None,
            products[0],
            fallback_url,
        )
    )

    while len(opportunities) < min(90, max(35, len(concept_pool) * 2)) and concept_pool:
        term = concept_pool[len(opportunities) % len(concept_pool)]
        cluster = clusters[len(opportunities) % len(clusters)] if clusters else None
        audience = audiences[len(opportunities) % len(audiences)] if audiences else None
        opportunity_type = OPPORTUNITY_TYPES[len(opportunities) % len(OPPORTUNITY_TYPES)]
        product = products[len(opportunities) % len(products)]
        payload = {
            "cluster_id": cluster.id if cluster else None,
            "product_name": product.get("name", ""),
            "product_url": product.get("url", fallback_url),
            "primary_audience_id": audience.id if audience else None,
            "audience_rationale": "Generated to satisfy editorial ecosystem diversity and semantic authority coverage.",
            "title": _title(opportunity_type, term),
            "target_keyword": str(term),
            "opportunity_type": opportunity_type,
            "content_role": "pillar_page" if opportunity_type == "pillar_page" else "supporting_article",
            "search_intent": "informational" if opportunity_type != "comparison_article" else "comparison",
            "funnel_stage": "awareness",
            "rationale": "Fills a semantic support slot around the inferred niche ecosystem.",
            "related_entities": concept_pool[:10],
            "suggested_structure": _structure_for(opportunity_type, term),
        }
        opportunities.append(_make_opportunity(payload, cluster, audience, competitor_gap=0.55))
    return opportunities


def _external_research_opportunities(
    external_research: dict[str, Any],
    cluster: OpportunityCluster | None,
    audience: AudienceProfile | None,
    product: dict[str, Any],
    fallback_url: str,
) -> list[Opportunity]:
    if not external_research or not external_research.get("enabled"):
        return []
    summary = external_research.get("summary", {})
    angles = summary.get("possible_article_angles", []) + summary.get("competitor_independent_opportunities", [])
    opportunities: list[Opportunity] = []
    for angle in angles[:35]:
        if not isinstance(angle, dict):
            continue
        topic = str(angle.get("target_keyword") or angle.get("title") or "").strip()
        if not topic:
            continue
        source_type = _source_type(angle.get("source_type") or "web")
        payload = {
            "cluster_id": cluster.id if cluster else None,
            "product_name": product.get("name", ""),
            "product_url": product.get("url", fallback_url),
            "primary_audience_id": audience.id if audience else None,
            "audience_rationale": "External research signals suggest this topic may deserve editorial validation.",
            "title": str(angle.get("title") or _title("industry_trend", topic)),
            "target_keyword": topic,
            "opportunity_type": "industry_trend" if source_type in {"web", "trend", "youtube", "reddit"} else "research_summary",
            "content_role": "semantic_support_article",
            "search_intent": "informational",
            "funnel_stage": "awareness",
            "rationale": "Generated from external research enrichment. Treat as directional until reviewed.",
            "related_entities": _clean_terms([topic, *summary.get("recurring_topics", [])])[:10],
            "suggested_structure": [
                "Why this topic appears externally",
                "What the sources actually indicate",
                "Questions to verify",
                "How it connects to the site ecosystem",
                "Claims and cautions",
            ],
            "source_type": source_type,
            "evidence_summary": str(angle.get("evidence_summary") or "External research enrichment produced this directional angle."),
            "needs_verification": True,
            "evidence_items": _evidence_items_for_topic(topic, external_research),
        }
        opportunities.append(_make_opportunity(payload, cluster, audience, competitor_gap=0.68))
    return opportunities


def _product_entity_opportunities(
    *,
    product_name: str,
    product_url: str,
    concept_pool: list[str],
    expansions: list[str],
    cluster: OpportunityCluster | None,
    audience: AudienceProfile | None,
) -> list[Opportunity]:
    related = _clean_terms([*expansions, *concept_pool])[:12]
    base = {
        "cluster_id": cluster.id if cluster else None,
        "product_name": product_name,
        "product_url": product_url,
        "primary_audience_id": audience.id if audience else None,
        "audience_rationale": "This product/entity is treated as a semantic anchor for educational authority, FAQ, comparison, and mechanism coverage.",
    }
    specifications = [
        ("product_deep_dive", f"{product_name} research context", 0.52),
        ("mechanism_explainer", f"{product_name} mechanisms", 0.58),
        ("comparison_article", f"{product_name} comparisons", 0.55),
        ("faq_cluster", f"{product_name} questions", 0.5),
        ("myth_vs_fact", f"{product_name} myths", 0.5),
        ("glossary", f"{product_name} terminology", 0.48),
        ("geo_search", f"{product_name} AI search questions", 0.5),
    ]
    opportunities = []
    for opportunity_type, keyword, competitor_gap in specifications:
        opportunities.append(
            _make_opportunity(
                {
                    **base,
                    "title": _title(opportunity_type, product_name),
                    "target_keyword": keyword,
                    "opportunity_type": opportunity_type,
                    "content_role": "cluster_support",
                    "search_intent": "comparison" if opportunity_type == "comparison_article" else "informational",
                    "funnel_stage": "consideration" if opportunity_type in {"product_deep_dive", "comparison_article"} else "awareness",
                    "rationale": "Generated from explicit product/entity extraction to prevent the strategy from collapsing into generic page-derived ideas.",
                    "related_products": [product_name],
                    "related_entities": related,
                    "suggested_structure": _structure_for(opportunity_type, product_name),
                    "suggested_media": _media_for(opportunity_type),
                    "cta_strategy": "Point readers toward documentation, purity, storage, or category resources while preserving compliant research framing.",
                },
                cluster,
                audience,
                competitor_gap=competitor_gap,
            )
        )
    for expansion in related[:5]:
        opportunities.append(
            _make_opportunity(
                {
                    **base,
                    "title": _relationship_title(product_name, expansion),
                    "target_keyword": f"{product_name} {expansion}",
                    "opportunity_type": "mechanism_explainer",
                    "content_role": "semantic_support_article",
                    "search_intent": "informational",
                    "funnel_stage": "awareness",
                    "rationale": "Connects a product/entity to adjacent scientific concepts that shape broader niche conversations.",
                    "related_products": [product_name],
                    "related_entities": related,
                    "suggested_structure": _structure_for("mechanism_explainer", expansion),
                },
                cluster,
                audience,
                competitor_gap=0.56,
            )
        )
    return opportunities


def _product_family_opportunities(
    families: list[dict[str, Any]],
    cluster: OpportunityCluster | None,
    audience: AudienceProfile | None,
    fallback_url: str,
) -> list[Opportunity]:
    opportunities = []
    for family in families[:12]:
        family_name = str(family.get("family") or "")
        products = _clean_terms(family.get("products", []))
        if not family_name or len(products) < 2:
            continue
        base = {
            "cluster_id": cluster.id if cluster else None,
            "product_name": family_name,
            "product_url": fallback_url,
            "primary_audience_id": audience.id if audience else None,
            "audience_rationale": "Product family grouping reveals comparison and ecosystem opportunities beyond single product pages.",
            "related_products": products,
            "related_entities": products,
        }
        for opportunity_type in ("comparison_article", "evergreen_authority", "faq_cluster"):
            opportunities.append(
                _make_opportunity(
                    {
                        **base,
                        "title": _title(opportunity_type, family_name),
                        "target_keyword": f"{family_name} {'comparison' if opportunity_type == 'comparison_article' else 'research'}",
                        "opportunity_type": opportunity_type,
                        "content_role": "pillar_page" if opportunity_type == "evergreen_authority" else "cluster_support",
                        "search_intent": "comparison" if opportunity_type == "comparison_article" else "informational",
                        "funnel_stage": "consideration",
                        "rationale": "Family-level opportunity based on extracted product relationships.",
                        "suggested_structure": _structure_for(opportunity_type, family_name),
                    },
                    cluster,
                    audience,
                    competitor_gap=0.6,
                )
            )
    return opportunities


def _opportunities_for_cluster(
    base: dict[str, Any],
    cluster: OpportunityCluster,
    primary_audience: AudienceProfile | None,
    seed_terms: list[str],
    questions: list[str],
    competitor_gaps: list[str],
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    template_types = [
        "pillar_page" if cluster.pillar_candidate else "evergreen_authority",
        "mechanism_explainer",
        "glossary",
        "myth_vs_fact",
        "geo_search",
        "industry_trend",
        "laboratory_practice",
        "comparison_article",
        "faq_cluster",
    ]
    for index, term in enumerate(seed_terms[:18]):
        opportunity_type = template_types[index % len(template_types)]
        opportunities.append(
            _make_opportunity(
                {
                    **base,
                    "title": _title(opportunity_type, term),
                    "target_keyword": str(term),
                    "opportunity_type": opportunity_type,
                    "content_role": "pillar_page" if opportunity_type == "pillar_page" else "cluster_support",
                    "search_intent": "informational" if opportunity_type != "comparison_article" else "comparison",
                    "funnel_stage": "awareness" if opportunity_type not in {"comparison_article", "buyer_guide"} else "consideration",
                    "rationale": "Builds semantic authority from inferred niche entities, not page chrome.",
                    "related_entities": seed_terms[:10],
                    "suggested_structure": _structure_for(opportunity_type, term),
                    "suggested_media": _media_for(opportunity_type),
                    "cta_strategy": "Invite readers to review product/category documentation without making unsupported claims.",
                },
                cluster,
                primary_audience,
                competitor_gap=0.5,
            )
        )
    for question in questions[:6]:
        term = question.rstrip("?")
        opportunities.append(
            _make_opportunity(
                {
                    **base,
                    "title": question if question.endswith("?") else f"{question}?",
                    "target_keyword": term,
                    "opportunity_type": "faq_cluster",
                    "content_role": "semantic_support_article",
                    "search_intent": "informational",
                    "funnel_stage": "awareness",
                    "rationale": "Targets FAQ/GEO answer coverage from recurring audience question language.",
                    "related_entities": seed_terms[:8],
                    "suggested_structure": _structure_for("faq_cluster", term),
                },
                cluster,
                primary_audience,
                competitor_gap=0.45,
            )
        )
    for term in competitor_gaps[:8]:
        opportunities.append(
            _make_opportunity(
                {
                    **base,
                    "title": _title("competitor_gap_article", term),
                    "target_keyword": str(term),
                    "opportunity_type": "competitor_gap_article",
                    "content_role": "cluster_support",
                    "search_intent": "informational",
                    "funnel_stage": "consideration",
                    "rationale": "Competitor and semantic signals suggest this is missing or under-covered authority terrain.",
                    "related_entities": seed_terms[:8],
                    "suggested_structure": _structure_for("competitor_gap_article", term),
                },
                cluster,
                primary_audience,
                competitor_gap=0.78,
            )
        )
    return opportunities


def _normalize_ai_opportunity(
    item: dict[str, Any],
    audiences: list[AudienceProfile],
    clusters: list[OpportunityCluster],
    fallback_url: str,
) -> Opportunity | None:
    title = str(item.get("title") or item.get("article_title") or "").strip()
    if not title:
        return None
    keyword = str(item.get("target_keyword") or item.get("keyword") or title).strip()
    cluster = _match_cluster(item.get("cluster_id") or item.get("cluster"), clusters)
    audience = _match_audience(item.get("primary_audience_id") or item.get("audience"), audiences)
    product = _first(item.get("related_products")) or {}
    payload = {
        "id": str(item.get("id") or uuid4()),
        "cluster_id": cluster.id if cluster else None,
        "title": title,
        "target_keyword": keyword,
        "product_name": str(item.get("product_name") or product.get("name") or ""),
        "product_url": str(item.get("product_url") or product.get("url") or fallback_url),
        "opportunity_type": str(item.get("opportunity_type") or item.get("type") or "semantic_support_article"),
        "search_intent": str(item.get("search_intent") or item.get("intent") or "informational"),
        "funnel_stage": str(item.get("funnel_stage") or "awareness"),
        "content_role": str(item.get("content_role") or "supporting_article"),
        "primary_audience_id": audience.id if audience else None,
        "secondary_audience_ids": _list(item.get("secondary_audience_ids")),
        "audience_rationale": str(item.get("audience_rationale") or ""),
        "expertise_level": str(item.get("expertise_level") or (audience.expertise_level if audience else "mixed")),
        "related_products": _list(item.get("related_products")),
        "related_keywords": _list(item.get("related_keywords") or item.get("keywords")),
        "related_entities": _list(item.get("related_entities") or item.get("entities")),
        "rationale": str(item.get("rationale") or item.get("reason") or ""),
        "source_type": _source_type(item.get("source_type") or "inferred"),
        "evidence_summary": str(item.get("evidence_summary") or ""),
        "needs_verification": bool(item.get("needs_verification", True)),
        "evidence_items": _dict_list(item.get("evidence_items")),
        "competitor_references": _dict_list(item.get("competitor_references")),
        "suggested_article_length": int(item.get("suggested_article_length") or 1800),
        "suggested_structure": _list(item.get("suggested_structure") or item.get("outline")),
        "suggested_media": _list(item.get("suggested_media")),
        "suggested_internal_links": _list(item.get("suggested_internal_links")),
        "cta_strategy": str(item.get("cta_strategy") or ""),
        "confidence": _score(item.get("confidence"), 0.65),
    }
    return _make_opportunity(
        payload,
        cluster,
        audience,
        competitor_gap=_score((item.get("scores") or {}).get("competitor_gap"), 0.5) if isinstance(item.get("scores"), dict) else 0.5,
    )


def _make_opportunity(
    payload: dict[str, Any],
    cluster: OpportunityCluster | None,
    audience: AudienceProfile | None,
    competitor_gap: float,
) -> Opportunity:
    audience_fit = audience.confidence if audience else 0.5
    cluster_authority = cluster.authority_value if cluster else 0.5
    scores = score_opportunity(
        opportunity=payload,
        cluster_authority=cluster_authority,
        audience_fit=audience_fit,
        competitor_gap=competitor_gap,
    )
    return Opportunity(
        id=str(payload.get("id") or uuid4()),
        cluster_id=payload.get("cluster_id"),
        title=str(payload.get("title")),
        target_keyword=str(payload.get("target_keyword")),
        product_name=str(payload.get("product_name") or ""),
        product_url=str(payload.get("product_url") or ""),
        opportunity_type=str(payload.get("opportunity_type") or "semantic_support_article"),
        search_intent=str(payload.get("search_intent") or "informational"),
        funnel_stage=str(payload.get("funnel_stage") or "awareness"),
        content_role=str(payload.get("content_role") or "supporting_article"),
        primary_audience_id=payload.get("primary_audience_id"),
        secondary_audience_ids=_list(payload.get("secondary_audience_ids")),
        audience_rationale=str(payload.get("audience_rationale") or ""),
        expertise_level=str(payload.get("expertise_level") or "mixed"),
        confidence=max(_score(payload.get("confidence"), 0.65), scores.overall),
        scores=scores,
        related_products=_list(payload.get("related_products")),
        related_keywords=_list(payload.get("related_keywords")),
        related_entities=_list(payload.get("related_entities")),
        rationale=str(payload.get("rationale") or ""),
        source_type=_source_type(payload.get("source_type") or "inferred"),
        evidence_summary=str(payload.get("evidence_summary") or ""),
        needs_verification=bool(payload.get("needs_verification", True)),
        evidence_items=_dict_list(payload.get("evidence_items")),
        competitor_references=_dict_list(payload.get("competitor_references")),
        suggested_article_length=int(payload.get("suggested_article_length") or 1800),
        suggested_structure=_list(payload.get("suggested_structure")),
        suggested_media=_list(payload.get("suggested_media")),
        suggested_internal_links=_list(payload.get("suggested_internal_links")),
        cta_strategy=str(payload.get("cta_strategy") or ""),
    )


def _dedupe_opportunities(opportunities: list[Opportunity]) -> list[Opportunity]:
    unique: dict[str, Opportunity] = {}
    for opportunity in opportunities:
        key = f"{opportunity.opportunity_type}:{' '.join(opportunity.target_keyword.lower().split()) or opportunity.title.lower()}"
        current = unique.get(key)
        if current is None or opportunity.scores.overall > current.scores.overall:
            unique[key] = opportunity
    return sorted(unique.values(), key=lambda item: item.scores.overall, reverse=True)


def _quality_filter(opportunities: list[Opportunity]) -> list[Opportunity]:
    filtered = []
    for opportunity in opportunities:
        text = " ".join([opportunity.title, opportunity.target_keyword, opportunity.rationale]).lower()
        if any(term in text for term in NOISE_TERMS) and opportunity.scores.authority_fit < 0.82:
            continue
        if len(opportunity.title.split()) < 3 and opportunity.scores.authority_fit < 0.7:
            continue
        if opportunity.scores.overall < 0.42 and opportunity.scores.authority_fit < 0.6:
            continue
        filtered.append(opportunity)
    return filtered


def _enforce_diversity(opportunities: list[Opportunity]) -> list[Opportunity]:
    buckets: dict[str, list[Opportunity]] = {}
    for opportunity in opportunities:
        buckets.setdefault(opportunity.opportunity_type, []).append(opportunity)
    ordered: list[Opportunity] = []
    priority = [
        "pillar_page",
        "product_deep_dive",
        "mechanism_explainer",
        "glossary",
        "comparison_article",
        "myth_vs_fact",
        "faq_cluster",
        "geo_search",
        "industry_trend",
        "laboratory_practice",
        "competitor_gap_article",
        "evergreen_authority",
        "semantic_support_article",
    ]
    for opportunity_type in priority:
        ordered.extend(sorted(buckets.get(opportunity_type, []), key=lambda item: item.scores.overall, reverse=True)[:35])
    remaining = [item for item in opportunities if item not in ordered]
    ordered.extend(sorted(remaining, key=lambda item: item.scores.overall, reverse=True))
    return ordered


def _clean_terms(values: list[Any]) -> list[str]:
    cleaned = []
    for value in values:
        text = " ".join(str(value).replace("_", " ").split()).strip()
        if len(text) < 3:
            continue
        lowered = text.lower()
        if any(term in lowered for term in NOISE_TERMS):
            continue
        cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def _title(opportunity_type: str, term: str) -> str:
    topic = str(term).strip()
    templates = {
        "pillar_page": f"The Research Landscape Around {topic}",
        "evergreen_authority": f"Where {topic} Fits In The Broader Research Ecosystem",
        "mechanism_explainer": f"The Mechanisms Behind {topic}: A Research-Focused Explainer",
        "glossary": f"{topic} Glossary: Terms, Concepts, And Research Context",
        "myth_vs_fact": f"{topic} Myths, Misreadings, And What The Evidence Can Actually Support",
        "geo_search": f"Best Questions To Ask About {topic} Before Reading Product Claims",
        "industry_trend": f"Why {topic} Keeps Showing Up In Research Discussions",
        "laboratory_practice": f"How Lab Practices Shape The Interpretation Of {topic}",
        "comparison_article": f"{topic} Compared With Adjacent Research Topics",
        "faq_cluster": f"What Researchers Usually Ask About {topic}",
        "competitor_gap_article": f"The Under-Covered Research Context Around {topic}",
        "product_deep_dive": f"What {topic} Signals About The Wider Research Category",
    }
    return templates.get(opportunity_type, f"{topic} In Context: Research, Questions, And Related Concepts")


def _relationship_title(product_name: str, concept: str) -> str:
    return f"How {product_name} Connects To {concept}: Research Context And Open Questions"


def _entity_expansion_for(entity: str, semantic_expansion: dict[str, Any]) -> list[str]:
    expansions = semantic_expansion.get("entity_expansions", {})
    normalized = _normalize(entity)
    for key, values in expansions.items():
        if _normalize(key) == normalized or _normalize(key) in normalized or normalized in _normalize(key):
            return _clean_terms(values)
    concepts = semantic_expansion.get("concepts", [])
    return _clean_terms(concepts)[:10]


def _structure_for(opportunity_type: str, term: str) -> list[str]:
    common = ["Research context", "Key concepts", "What is known vs. unknown", "Practical interpretation", "References to verify"]
    if opportunity_type == "comparison_article":
        return ["Comparison scope", "Shared mechanisms", "Key differences", "Selection context", "Limitations"]
    if opportunity_type == "myth_vs_fact":
        return ["Common claim", "What the evidence can support", "Where claims overreach", "Safer research framing"]
    if opportunity_type == "laboratory_practice":
        return ["Handling context", "Storage considerations", "Documentation", "Reproducibility risks", "Safety boundaries"]
    if opportunity_type == "faq_cluster":
        return ["Short answer", "Research context", "Related questions", "What to verify", "Next reading"]
    return common


def _media_for(opportunity_type: str) -> list[str]:
    if opportunity_type in {"mechanism_explainer", "pillar_page"}:
        return ["concept diagram", "mechanism flow graphic"]
    if opportunity_type == "comparison_article":
        return ["comparison table"]
    if opportunity_type == "glossary":
        return ["definition cards"]
    return ["summary callout"]


def _match_cluster(value: Any, clusters: list[OpportunityCluster]) -> OpportunityCluster | None:
    if not value:
        return clusters[0] if clusters else None
    lookup = str(value).lower()
    return next((cluster for cluster in clusters if cluster.id == value or cluster.name.lower() == lookup), clusters[0] if clusters else None)


def _match_audience(value: Any, audiences: list[AudienceProfile]) -> AudienceProfile | None:
    if not value:
        return audiences[0] if audiences else None
    lookup = str(value).lower()
    return next((audience for audience in audiences if audience.id == value or audience.name.lower() == lookup), audiences[0] if audiences else None)


def _first(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


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
        return [str(item.get("name") if isinstance(item, dict) else item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize(value: Any) -> str:
    return str(value or "").lower().replace(" ", "-").replace("_", "-").strip()


def _source_type(value: Any) -> str:
    source_type = str(value or "inferred").lower()
    allowed = {"site", "competitor", "web", "academic", "youtube", "reddit", "trend", "inferred"}
    return source_type if source_type in allowed else "inferred"


def _evidence_items_for_topic(topic: str, external_research: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    lowered = topic.lower()
    for source_type, results in (external_research.get("source_results") or {}).items():
        for result in results:
            haystack = " ".join([str(result.get("query", "")), str(result.get("title", "")), str(result.get("snippet", ""))]).lower()
            if lowered in haystack or any(part in haystack for part in lowered.split()[:3]):
                matches.append(
                    {
                        "source_type": result.get("source_type") or source_type,
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "query": result.get("query"),
                        "provider": result.get("provider"),
                        "verified": bool(result.get("verified", False)),
                    }
                )
    return matches[:5]
