from collections import Counter, defaultdict
from re import findall
from typing import Any
from urllib.parse import urlparse

from app.opportunities.verticals import VerticalProfile, detect_vertical
from app.opportunities.verticals.base import display_entity_name, normalize_entity_name
from app.opportunities.verticals.generic import GENERIC_PROFILE


STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "best",
    "can",
    "for",
    "from",
    "how",
    "into",
    "learn",
    "more",
    "our",
    "product",
    "products",
    "shipping",
    "shop",
    "terms",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "with",
    "your",
}

QUESTION_STARTERS = ("what", "how", "why", "when", "where", "which", "can", "does", "is", "are")

BOILERPLATE_HINTS = {
    "account",
    "affiliate",
    "billing",
    "cart",
    "checkout",
    "contact",
    "delivery",
    "disclaimer",
    "footer",
    "guarantee",
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

PRODUCT_PATH_HINTS = {"product", "products", "collection", "collections", "category", "shop", "store"}
EDUCATIONAL_HINTS = {"blog", "learn", "guide", "research", "science", "resources", "faq", "glossary"}

CORE_ENTITY_HINTS = {"comparison", "care", "maintenance", "materials", "sizing", "security", "integration", "routine"}


def build_signal_inventory(
    website: dict[str, Any],
    competitors: list[dict[str, Any]],
    vertical: str = "auto",
) -> dict[str, Any]:
    active_profile, detection_report = detect_vertical(website=website, competitors=competitors, override=vertical)
    website_pages = website.get("pages", [])
    competitor_pages = [page for competitor in competitors for page in competitor.get("pages", [])]
    all_pages = website_pages + competitor_pages

    terms = _top_terms(all_pages, active_profile)
    primary_terms = _top_terms(website_pages, active_profile, 120)
    competitor_terms = _top_terms(competitor_pages, active_profile, 120)
    questions = _questions(all_pages, active_profile)
    extracted_entities = _strong_entity_extraction(all_pages, terms, active_profile)
    entities = list(dict.fromkeys([*_entities(all_pages, terms), *extracted_entities["extracted_entities"]]))
    navigation = _navigation(website_pages)
    competitor_overlap = _competitor_overlap(website_pages, competitor_pages, active_profile)
    product_candidates = _product_candidates(website_pages, website.get("url", ""), active_profile)
    product_intelligence = _product_intelligence(product_candidates, terms, entities, extracted_entities, active_profile)
    niche_intelligence = _niche_intelligence(terms, entities, product_intelligence, active_profile, detection_report)
    semantic_expansion = _semantic_expansion(niche_intelligence, product_intelligence, entities, active_profile)
    competitor_intelligence = _competitor_intelligence(primary_terms, competitor_terms, semantic_expansion)

    return {
        "terms": terms,
        "primary_terms": primary_terms,
        "competitor_terms": competitor_terms,
        "questions": questions,
        "entities": entities,
        "extracted_entities": extracted_entities["extracted_entities"],
        "extracted_products": product_intelligence["extracted_products"],
        "extracted_mechanisms": extracted_entities["extracted_mechanisms"],
        "extracted_concepts": extracted_entities["extracted_concepts"],
        "navigation": navigation,
        "competitor_overlap": competitor_overlap,
        "competitor_intelligence": competitor_intelligence,
        "niche_intelligence": niche_intelligence,
        "semantic_expansion": semantic_expansion,
        "product_intelligence": product_intelligence,
        "vertical_intelligence": {
            "detected_vertical": detection_report["detected_vertical"],
            "detected_vertical_confidence": detection_report["detected_vertical_confidence"],
            "vertical_detection_report": detection_report,
            "vertical_profile_summary": active_profile.summary(),
            "vertical_entity_expansions": active_profile.entity_expansion_map,
            "vertical_audience_examples": active_profile.audience_examples,
            "vertical_adjacent_niches": active_profile.adjacent_niche_map,
            "compliance_profile": active_profile.compliance_profile,
        },
        "detected_vertical": detection_report["detected_vertical"],
        "detected_vertical_confidence": detection_report["detected_vertical_confidence"],
        "vertical_detection_report": detection_report,
        "boilerplate_terms": sorted(_profile_set(active_profile, "boilerplate_hints")),
        "website_page_count": len(website_pages),
        "competitor_page_count": len(competitor_pages),
        "product_candidates": product_candidates,
    }


def _top_terms(pages: list[dict[str, Any]], profile: VerticalProfile, limit: int = 80) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for page in pages:
        page_weight = _page_weight(page, profile)
        text = " ".join(
            [
                str(page.get("title", "")),
                str(page.get("meta_description", "")),
                " ".join(str(heading.get("text", "")) for heading in page.get("headings", [])),
                str(page.get("text_sample", ""))[:2000],
            ]
        ).lower()
        for word in findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text):
            if word not in (STOPWORDS | profile.stopwords) and len(word) > 2 and not _is_boilerplate_term(word, profile):
                boost = 2.2 if word in _profile_set(profile, "known_entities") | _profile_set(profile, "mechanism_hints") | CORE_ENTITY_HINTS else 1.0
                counter[word] += max(1, int(page_weight * boost * 10))
    return [{"term": term, "count": count} for term, count in counter.most_common(limit)]


def _questions(pages: list[dict[str, Any]], profile: VerticalProfile, limit: int = 60) -> list[str]:
    found: list[str] = []
    for page in pages:
        if _page_weight(page, profile) < 0.35:
            continue
        chunks = [str(page.get("title", "")), str(page.get("meta_description", ""))]
        chunks.extend(str(heading.get("text", "")) for heading in page.get("headings", []))
        for chunk in chunks:
            stripped = chunk.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if stripped.endswith("?") or lower.startswith(QUESTION_STARTERS):
                found.append(stripped[:160])
    return list(dict.fromkeys(found))[:limit]


def _entities(pages: list[dict[str, Any]], terms: list[dict[str, Any]], limit: int = 80) -> list[str]:
    candidates = [str(item["term"]) for item in terms[:40]]
    for page in pages:
        title_words = findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", str(page.get("title", "")))
        heading_words = findall(
            r"\b[A-Z][A-Za-z0-9-]{2,}\b",
            " ".join(str(heading.get("text", "")) for heading in page.get("headings", [])),
        )
        candidates.extend(title_words + heading_words)
    return list(dict.fromkeys(item.strip() for item in candidates if item.strip()))[:limit]


def _navigation(pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for page in pages:
        for link in page.get("commercial_links", []):
            links.append({"text": str(link.get("text", ""))[:120], "url": str(link.get("url", ""))})
    return [link for link in links if link["url"]]


def _competitor_overlap(website_pages: list[dict[str, Any]], competitor_pages: list[dict[str, Any]], profile: VerticalProfile) -> dict[str, Any]:
    website_terms = {item["term"] for item in _top_terms(website_pages, profile, 120)}
    competitor_terms = {item["term"] for item in _top_terms(competitor_pages, profile, 120)}
    overlap = sorted(website_terms & competitor_terms)
    gaps = sorted(competitor_terms - website_terms)
    return {
        "shared_terms": overlap[:50],
        "competitor_only_terms": gaps[:80],
        "overlap_ratio": round(len(overlap) / max(1, len(website_terms | competitor_terms)), 3),
    }


def _product_candidates(pages: list[dict[str, Any]], fallback_url: str, profile: VerticalProfile) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for page in pages:
        page_url = str(page.get("url") or fallback_url)
        if _page_weight(page, profile) < 0.25:
            continue
        parsed_path = urlparse(page_url).path.strip("/").split("/")[-1].replace("-", " ").title()
        title = str(page.get("title") or parsed_path or "Website")
        if _is_product_like_url(page_url, profile) or _has_product_language(title, profile):
            candidates.append({"name": _clean_product_name(title)[:120], "url": page_url})
        for link in page.get("commercial_links", []):
            text = str(link.get("text") or "Product").strip()
            url = str(link.get("url") or fallback_url)
            if _is_product_like_url(url, profile) and not _is_boilerplate_phrase(text, profile):
                candidates.append({"name": _clean_product_name(text)[:120], "url": url})
    unique: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if candidate["name"] and not _is_boilerplate_phrase(candidate["name"], profile):
            unique.setdefault(candidate["url"], candidate)
    return list(unique.values())[:120]


def _page_weight(page: dict[str, Any], profile: VerticalProfile) -> float:
    url = str(page.get("url", "")).lower()
    path = urlparse(url).path.lower()
    title = str(page.get("title", "")).lower()
    text = " ".join(
        [
            title,
            str(page.get("meta_description", "")).lower(),
            " ".join(str(heading.get("text", "")).lower() for heading in page.get("headings", [])),
        ]
    )
    weight = 1.0
    if any(hint in path for hint in _profile_set(profile, "product_path_hints")):
        weight += 1.4
    educational_hints = _profile_set(profile, "educational_hints")
    if any(hint in path for hint in educational_hints) or any(hint in text for hint in educational_hints):
        weight += 0.8
    if any(hint in text for hint in _profile_set(profile, "known_entities") | _profile_set(profile, "mechanism_hints") | _profile_set(profile, "concept_hints")):
        weight += 1.0
    if any(hint in path or hint in text for hint in _profile_set(profile, "boilerplate_hints")):
        weight -= 1.2
    if page.get("status") == "error":
        weight -= 0.7
    return max(0.1, min(3.0, weight))


def _is_boilerplate_term(term: str, profile: VerticalProfile) -> bool:
    return term.lower() in _profile_set(profile, "boilerplate_hints") or term.lower() in {"order", "orders", "subscribe", "newsletter"}


def _is_boilerplate_phrase(value: str, profile: VerticalProfile) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in _profile_set(profile, "boilerplate_hints"))


def _is_product_like_url(url: str, profile: VerticalProfile) -> bool:
    path = urlparse(url).path.lower()
    return any(f"/{hint}" in path for hint in _profile_set(profile, "product_path_hints"))


def _has_product_language(value: str, profile: VerticalProfile) -> bool:
    lowered = value.lower()
    profile_terms = _profile_set(profile, "known_entities") | _profile_set(profile, "domain_keywords")
    return any(term in lowered for term in profile_terms) or bool(findall(r"\b[A-Z]{2,}[A-Z0-9-]*\b", value))


def _clean_product_name(value: str) -> str:
    cleaned = " ".join(value.replace("|", " ").replace(" - ", " ").split())
    for suffix in ("Buy ", "Shop ", "For Sale"):
        cleaned = cleaned.replace(suffix, "")
    return cleaned.strip()


def _product_intelligence(
    products: list[dict[str, str]],
    terms: list[dict[str, Any]],
    entities: list[str],
    extracted_entities: dict[str, list[str]],
    profile: VerticalProfile,
) -> dict[str, Any]:
    names = [_clean_product_name(product.get("name", "")) for product in products if product.get("name")]
    names.extend(extracted_entities.get("extracted_products", []))
    names = list(dict.fromkeys(name for name in names if name and not _is_boilerplate_phrase(name, profile)))
    families: dict[str, list[str]] = defaultdict(list)
    for name in names:
        family = _product_family(name, profile)
        families[family].append(name)
    entity_terms = list(dict.fromkeys([*entities, *(item["term"] for item in terms[:60]), *extracted_entities.get("extracted_entities", [])]))
    mechanisms = list(dict.fromkeys([*extracted_entities.get("extracted_mechanisms", []), *[term for term in entity_terms if term.lower() in _profile_set(profile, "mechanism_hints")]]))
    return {
        "extracted_products": names[:120],
        "extracted_entities": entity_terms[:140],
        "extracted_mechanisms": mechanisms[:100],
        "extracted_concepts": extracted_entities.get("extracted_concepts", [])[:100],
        "product_families": [{"family": family, "products": list(dict.fromkeys(items))[:30]} for family, items in families.items()],
        "product_entities": entity_terms[:100],
        "related_mechanisms": list(dict.fromkeys(mechanisms))[:80],
        "related_topics": _related_topics_for_terms([*entity_terms, *extracted_entities.get("extracted_concepts", [])], profile),
    }


def _product_family(name: str, profile: VerticalProfile) -> str:
    return profile.classify_product_family(name)


def _niche_intelligence(
    terms: list[dict[str, Any]],
    entities: list[str],
    product_intelligence: dict[str, Any],
    profile: VerticalProfile,
    detection_report: dict[str, Any],
) -> dict[str, Any]:
    top_terms = [item["term"] for item in terms[:8]]
    products = product_intelligence.get("extracted_products", [])
    adjacent = profile.infer_adjacent_niches(terms, entities, products)
    return {
        "primary_niche": f"{profile.name.lower()} opportunity ecosystem" if profile.id != "generic" else "topical ecommerce and education",
        "secondary_niches": list(dict.fromkeys([*top_terms[:4], *products[:3]])),
        "adjacent_niches": adjacent or top_terms[4:8],
        "audience_interests": list(dict.fromkeys([*sorted(profile.concept_hints)[:8], "comparisons", "education", "trust building"])),
        "confidence": max(0.55, float(detection_report.get("detected_vertical_confidence") or 0.0)),
        "detected_vertical": detection_report.get("detected_vertical"),
    }


def _semantic_expansion(
    niche: dict[str, Any],
    product_intelligence: dict[str, Any],
    entities: list[str],
    profile: VerticalProfile,
) -> dict[str, Any]:
    concepts = list(
        dict.fromkeys(
            [
                *entities,
                *product_intelligence.get("extracted_products", []),
                *product_intelligence.get("extracted_mechanisms", []),
                *product_intelligence.get("extracted_concepts", []),
                *product_intelligence.get("related_topics", []),
            ]
        )
    )
    for product in product_intelligence.get("extracted_products", []):
        concepts.extend(profile.expand_entity(product))
    concepts.extend(niche.get("adjacent_niches", []))
    return {
        "concepts": list(dict.fromkeys(str(item) for item in concepts if str(item).strip()))[:140],
        "entity_relationships": _entity_relationships(concepts),
        "entity_expansions": {
            product: profile.expand_entity(product)
            for product in product_intelligence.get("extracted_products", [])
            if profile.expand_entity(product)
        },
    }


def _entity_relationships(concepts: list[str]) -> list[dict[str, str]]:
    relationships = []
    ordered = [str(item) for item in concepts if str(item).strip()]
    for first, second in zip(ordered, ordered[1:]):
        relationships.append({"source": first, "target": second, "relationship": "semantically_reinforces"})
    return relationships[:120]


def _competitor_intelligence(
    primary_terms: list[dict[str, Any]],
    competitor_terms: list[dict[str, Any]],
    semantic_expansion: dict[str, Any],
) -> dict[str, Any]:
    primary = {item["term"] for item in primary_terms}
    competitors = {item["term"] for item in competitor_terms}
    semantic = {str(item).lower() for item in semantic_expansion.get("concepts", [])}
    gaps = sorted((competitors | semantic) - primary)
    return {
        "missing_topics": gaps[:80],
        "missing_educational_coverage": [topic for topic in gaps if topic in semantic][:60],
        "shared_authority_terms": sorted(primary & competitors)[:60],
        "weak_semantic_areas": gaps[:30],
    }


def _related_topics_for_terms(terms: list[str], profile: VerticalProfile) -> list[str]:
    topics = []
    topics.extend(sorted(profile.concept_hints)[:20])
    topics.extend(sorted(profile.mechanism_hints)[:20])
    topics.extend(term for term in terms[:50] if not _is_boilerplate_phrase(term, profile))
    return list(dict.fromkeys(topics))[:80]


def _strong_entity_extraction(pages: list[dict[str, Any]], terms: list[dict[str, Any]], profile: VerticalProfile) -> dict[str, list[str]]:
    chunks = []
    for page in pages:
        if _page_weight(page, profile) < 0.25:
            continue
        chunks.extend(
            [
                str(page.get("url", "")),
                str(page.get("title", "")),
                str(page.get("meta_description", "")),
                " ".join(str(heading.get("text", "")) for heading in page.get("headings", [])),
                str(page.get("text_sample", "")),
                " ".join(str(link.get("text", "")) for link in page.get("commercial_links", [])),
            ]
        )
    text = " ".join(chunks)
    lowered = text.lower()
    product_entities = set()
    scientific_entities = set()
    mechanisms = set()
    concepts = set()

    known_entities = _profile_set(profile, "known_entities")
    mechanism_hints = _profile_set(profile, "mechanism_hints")
    concept_hints = _profile_set(profile, "concept_hints")
    for entity in known_entities:
        if entity in lowered or entity.replace("-", " ") in lowered:
            product_entities.add(display_entity_name(entity))
    for token in findall(r"\b[A-Z]{2,}(?:[-+][A-Z0-9]+|\d+)?(?:-[A-Z0-9]+)?\b", text):
        normalized = normalize_entity_name(token)
        if normalized in known_entities:
            product_entities.add(token)
        elif normalized.lower() in mechanism_hints:
            mechanisms.add(display_entity_name(normalized))
            scientific_entities.add(token)
        elif normalized not in {"faq", "url"} and len(normalized) >= 3:
            scientific_entities.add(token)
    for phrase in mechanism_hints:
        if phrase in lowered:
            mechanisms.add(display_entity_name(phrase))
    for phrase in concept_hints:
        if phrase in lowered:
            concepts.add(display_entity_name(phrase))
    for term in terms[:80]:
        term_value = str(term.get("term", "")).lower()
        if term_value in known_entities:
            product_entities.add(display_entity_name(term_value))
        if term_value in mechanism_hints:
            mechanisms.add(display_entity_name(term_value))
    extracted_products = sorted(product_entities)
    extracted_entities = sorted(product_entities | scientific_entities | mechanisms | concepts)
    return {
        "extracted_products": extracted_products[:120],
        "extracted_entities": extracted_entities[:180],
        "extracted_mechanisms": sorted(mechanisms)[:120],
        "extracted_concepts": sorted(concepts)[:120],
    }


def _profile_set(profile: VerticalProfile, attribute: str) -> set[str]:
    base = getattr(GENERIC_PROFILE, attribute, set())
    specific = getattr(profile, attribute, set())
    return set(base) | set(specific)
