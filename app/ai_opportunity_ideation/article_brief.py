from __future__ import annotations

import re
from typing import Any

SCIENCE_SEARCH_INTENTS = frozenset(
    {"research_overview", "comparison", "mechanism", "product_relationship"}
)
SCIENCE_CONTENT_TYPES = frozenset(
    {"research_overview", "comparison", "mechanism_explainer", "relationship", "mechanism"}
)
BUYER_GUIDE_TYPES = frozenset({"buyer_guide", "buyers_guide", "buyer guide"})

_PATHWAY_TOPIC_RE = re.compile(
    r"\b(signaling|pathway|pathways|receptor|receptors|axis|cascade|transduction|"
    r"ampk|gnrh|mitochondrial|secretagogue|glp-1|gip|ghrh)\b",
    re.I,
)
_CONCEPT_TOPIC_RE = re.compile(
    r"\b(mechanism|biology|peptide|protein|hormone|metabolic|tissue|copper|cellular|"
    r"literature|research theme|overview)\b",
    re.I,
)
_RESEARCH_THEME_RE = re.compile(
    r"\b(research|literature|preclinical|in vitro|signaling|mechanism|biology|pathway|"
    r"receptor|studied|discussed|compared|distinction)\b",
    re.I,
)
_SUPPLIER_TOPIC_RE = re.compile(
    r"\b(supplier|catalog|inventory|documentation quality|shopping|buyer guide|"
    r"product page|procurement|listing|sku rotation|freeze-thaw)\b",
    re.I,
)


def is_buyer_guide_article(context: dict[str, Any] | None) -> bool:
    if not context:
        return False
    for key in ("article_type", "content_type", "recommendation_type", "search_intent"):
        value = str(context.get(key) or "").strip().lower().replace("-", "_").replace(" ", "_")
        if value in BUYER_GUIDE_TYPES or value == "buyer_guide":
            return True
    return False


def is_science_editorial_article(context: dict[str, Any] | None) -> bool:
    if not context:
        return False
    if is_buyer_guide_article(context):
        return False
    if bool(context.get("science_focus")):
        return True
    intent = str(context.get("search_intent") or "").strip().lower()
    ctype = str(context.get("content_type") or context.get("article_type") or "").strip().lower()
    return intent in SCIENCE_SEARCH_INTENTS or ctype in SCIENCE_CONTENT_TYPES


def resolve_article_content_type(context: dict[str, Any] | None) -> str:
    if not context:
        return "research_overview"
    for key in ("content_type", "article_type", "search_intent", "recommendation_type"):
        value = str(context.get(key) or "").strip().lower().replace("-", "_").replace(" ", "_")
        if value:
            if value == "product_relationship":
                return "relationship"
            return value
    return "research_overview"


def is_science_focused_opportunity(
    *,
    search_intent: str = "",
    content_type: str = "",
) -> bool:
    intent = str(search_intent or "").strip().lower()
    ctype = str(content_type or "").strip().lower()
    return intent in SCIENCE_SEARCH_INTENTS or ctype in SCIENCE_CONTENT_TYPES


def enrich_article_opportunity_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Build generation brief from ideation opportunity; science types get mechanism/pathway focus."""
    if not context:
        return {}

    enriched = {
        key: value
        for key, value in context.items()
        if key
        not in {
            "supplier_guidance",
            "inventory_management",
            "catalog_navigation",
            "shopping_guidance",
        }
    }

    search_intent = str(enriched.get("search_intent") or "").strip().lower()
    content_type = str(enriched.get("content_type") or "").strip().lower()
    if not is_science_focused_opportunity(search_intent=search_intent, content_type=content_type):
        enriched["science_focus"] = False
        return enriched

    related_topics = _clean_string_list(enriched.get("related_topics"))
    related_products = _clean_string_list(enriched.get("related_products"))
    headline = str(enriched.get("headline") or enriched.get("title") or "").strip()
    abstract = str(enriched.get("abstract") or "").strip()

    pathways = [topic for topic in related_topics if _PATHWAY_TOPIC_RE.search(topic)]
    concepts = [
        topic
        for topic in related_topics
        if topic not in pathways and (_CONCEPT_TOPIC_RE.search(topic) or not _SUPPLIER_TOPIC_RE.search(topic))
    ]
    if not concepts:
        concepts = _infer_concepts(headline, abstract, related_products)

    research_themes = [
        topic
        for topic in related_topics
        if _RESEARCH_THEME_RE.search(topic) and not _SUPPLIER_TOPIC_RE.search(topic)
    ]
    if not research_themes:
        research_themes = _infer_research_themes(headline, abstract, related_topics)

    enriched.update(
        {
            "science_focus": True,
            "article_type": content_type or search_intent,
            "editorial_mode": "science",
            "related_biological_concepts": concepts,
            "related_pathways": pathways,
            "related_products": related_products,
            "related_research_themes": research_themes,
            "science_depth_targets": _science_depth_targets(
                headline=headline,
                abstract=abstract,
                pathways=pathways,
                concepts=concepts,
                research_themes=research_themes,
            ),
        }
    )
    return enriched


def _science_depth_targets(
    *,
    headline: str,
    abstract: str,
    pathways: list[str],
    concepts: list[str],
    research_themes: list[str],
) -> dict[str, list[str]]:
    blob = f"{headline} {abstract}".lower()
    experimental_models: list[str] = []
    if any(token in blob for token in ("in vitro", "cell", "tissue", "animal", "rodent")):
        experimental_models.append("in vitro and preclinical model context")
    else:
        experimental_models.append("preclinical and in vitro models discussed in literature")

    controversies: list[str] = []
    if "hypothes" in blob or "debate" in blob or "unsettled" in blob:
        controversies.append("unsettled mechanisms and active research debates")
    if " vs " in blob or " versus " in blob:
        controversies.append("distinctions researchers draw between related compounds or categories")

    evidence_strengths: list[str] = []
    if "signaling" in blob or pathways:
        evidence_strengths.append("pathway-level observations from preclinical studies")
    if "overview" in blob or "literature" in blob:
        evidence_strengths.append("recurring literature themes and nomenclature context")

    evidence_limitations: list[str] = [
        "limited human clinical translation",
        "model-dependent interpretation",
    ]

    return {
        "major_pathways": pathways[:6] or [item for item in concepts if _PATHWAY_TOPIC_RE.search(item)][:6],
        "recurring_literature_themes": research_themes[:6],
        "experimental_models": experimental_models,
        "controversies": controversies[:4],
        "evidence_strengths": evidence_strengths[:4],
        "evidence_limitations": evidence_limitations,
    }


def _clean_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _infer_concepts(headline: str, abstract: str, products: list[str]) -> list[str]:
    blob = f"{headline} {abstract}"
    concepts: list[str] = []
    for product in products:
        if product and product not in concepts:
            concepts.append(product)
    for match in re.finditer(
        r"\b(AMPK|GnRH|mitochondrial peptides?|copper peptides?|growth hormone|secretagogue|"
        r"receptor biology|metabolic signaling|tissue repair|angiogenesis)\b",
        blob,
        re.I,
    ):
        label = " ".join(match.group(0).split())
        if label not in concepts:
            concepts.append(label)
    return concepts[:8]


def _infer_research_themes(headline: str, abstract: str, related_topics: list[str]) -> list[str]:
    themes: list[str] = []
    for topic in related_topics:
        if _RESEARCH_THEME_RE.search(topic) and not _SUPPLIER_TOPIC_RE.search(topic):
            themes.append(topic)
    blob = f"{headline} {abstract}".lower()
    if " vs " in blob or " versus " in blob:
        themes.append("comparison of research themes and distinctions")
    if "signaling" in blob and "signaling" not in themes:
        themes.append("signaling biology discussed in research literature")
    if "mechanism" in blob:
        themes.append("mechanistic background from preclinical literature")
    deduped: list[str] = []
    for theme in themes:
        if theme not in deduped:
            deduped.append(theme)
    return deduped[:8]
