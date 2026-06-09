from dataclasses import dataclass, field
from typing import Any

from app.opportunities.schemas import AudienceProfile


@dataclass(frozen=True)
class VerticalProfile:
    id: str
    name: str
    description: str
    domain_keywords: set[str] = field(default_factory=set)
    stopwords: set[str] = field(default_factory=set)
    boilerplate_hints: set[str] = field(default_factory=set)
    product_path_hints: set[str] = field(default_factory=set)
    educational_hints: set[str] = field(default_factory=set)
    known_entities: set[str] = field(default_factory=set)
    mechanism_hints: set[str] = field(default_factory=set)
    concept_hints: set[str] = field(default_factory=set)
    entity_expansion_map: dict[str, list[str]] = field(default_factory=dict)
    product_family_map: dict[str, set[str]] = field(default_factory=dict)
    adjacent_niche_map: dict[str, list[str]] = field(default_factory=dict)
    audience_examples: list[dict[str, Any]] = field(default_factory=list)
    compliance_profile: dict[str, Any] = field(default_factory=dict)
    opportunity_type_weights: dict[str, float] = field(default_factory=dict)
    title_style_guidance: list[str] = field(default_factory=list)
    image_allowed_types: list[str] = field(default_factory=list)
    image_avoid_rules: list[str] = field(default_factory=list)
    image_style_guidance: list[str] = field(default_factory=list)
    featured_image_preferences: list[str] = field(default_factory=list)
    inline_image_preferences: list[str] = field(default_factory=list)
    unsafe_visual_concepts: list[str] = field(default_factory=list)
    preferred_visual_contexts: list[str] = field(default_factory=list)

    def detect_confidence(self, signal_inventory: dict[str, Any]) -> float:
        text = _inventory_text(signal_inventory)
        keywords = {item.lower() for item in self.domain_keywords | self.known_entities}
        if not keywords:
            return 0.0
        matches = sum(1 for keyword in keywords if keyword and keyword in text)
        return min(1.0, matches / max(4, len(keywords) * 0.18))

    def expand_entity(self, entity: str) -> list[str]:
        normalized = normalize_entity_name(entity)
        return self.entity_expansion_map.get(normalized, [])

    def classify_product_family(self, product_name: str) -> str:
        normalized = normalize_entity_name(product_name)
        for family, members in self.product_family_map.items():
            if normalized in members or any(member in normalized for member in members):
                return family
        return "core catalog"

    def infer_adjacent_niches(
        self,
        terms: list[dict[str, Any]],
        entities: list[str],
        products: list[str],
    ) -> list[str]:
        vocabulary = {str(item.get("term", "")).lower() for item in terms}
        vocabulary.update(entity.lower() for entity in entities)
        vocabulary.update(product.lower() for product in products)
        adjacent: list[str] = []
        for keyword, niches in self.adjacent_niche_map.items():
            if keyword.lower() in vocabulary or any(keyword.lower() in item for item in vocabulary):
                adjacent.extend(niches)
        return list(dict.fromkeys(adjacent))[:40]

    def suggest_audiences(self, signal_inventory: dict[str, Any]) -> list[AudienceProfile]:
        audiences = []
        for item in self.audience_examples:
            try:
                audiences.append(AudienceProfile(**item))
            except TypeError:
                continue
        return audiences

    def get_boilerplate_penalty(self, term_or_page: Any) -> float:
        text = str(term_or_page).lower()
        if isinstance(term_or_page, dict):
            text = " ".join(
                [
                    str(term_or_page.get("url", "")),
                    str(term_or_page.get("title", "")),
                    str(term_or_page.get("meta_description", "")),
                    " ".join(str(heading.get("text", "")) for heading in term_or_page.get("headings", [])),
                ]
            ).lower()
        return 1.2 if any(hint in text for hint in self.boilerplate_hints) else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain_keywords": sorted(self.domain_keywords),
            "known_entities": sorted(self.known_entities)[:80],
            "mechanism_hints": sorted(self.mechanism_hints)[:80],
            "concept_hints": sorted(self.concept_hints)[:80],
            "product_families": sorted(self.product_family_map),
            "compliance_profile": self.compliance_profile,
            "opportunity_type_weights": self.opportunity_type_weights,
            "title_style_guidance": self.title_style_guidance,
            "image_allowed_types": self.image_allowed_types,
            "image_avoid_rules": self.image_avoid_rules,
            "image_style_guidance": self.image_style_guidance,
            "featured_image_preferences": self.featured_image_preferences,
            "inline_image_preferences": self.inline_image_preferences,
            "unsafe_visual_concepts": self.unsafe_visual_concepts,
            "preferred_visual_contexts": self.preferred_visual_contexts,
        }


def normalize_entity_name(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-").strip()


def display_entity_name(value: str) -> str:
    normalized = normalize_entity_name(value)
    if normalized in {"api", "sku", "seo", "saas", "ruo"}:
        return normalized.upper()
    return value.upper() if len(value) <= 5 and value.isalpha() else value.title()


def _inventory_text(signal_inventory: dict[str, Any]) -> str:
    chunks = []
    for key in ("website", "competitors"):
        value = signal_inventory.get(key)
        if isinstance(value, dict):
            chunks.append(_site_text(value))
        elif isinstance(value, list):
            chunks.extend(_site_text(site) for site in value if isinstance(site, dict))
    chunks.extend(str(item.get("term", "")) for item in signal_inventory.get("terms", []) if isinstance(item, dict))
    chunks.extend(str(item) for item in signal_inventory.get("entities", []))
    chunks.extend(str(item.get("name", "")) for item in signal_inventory.get("product_candidates", []) if isinstance(item, dict))
    return " ".join(chunks).lower()


def _site_text(site: dict[str, Any]) -> str:
    chunks = [str(site.get("url", "")), str(site.get("domain", ""))]
    for page in site.get("pages", []):
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
    return " ".join(chunks)
