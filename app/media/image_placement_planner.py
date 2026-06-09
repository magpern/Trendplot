from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.article_schema import ArticleSchema
from app.opportunities.verticals.base import VerticalProfile
from app.opportunities.verticals.generic import GENERIC_PROFILE


BLOCKED_SECTION_HINTS = ("faq", "reference", "safety", "disclaimer", "legal", "limitations")


@dataclass(slots=True)
class ImagePlacementPlanner:
    max_inline_images: int = 2
    enable_vertical_rules: bool = True
    brand_style: str = "clean editorial"

    def plan(
        self,
        *,
        article: ArticleSchema,
        request_data: dict[str, Any],
        active_vertical_profile: VerticalProfile,
        detected_vertical: str,
        safety_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rules = _image_rules(active_vertical_profile, self.enable_vertical_rules)
        sections = [section.heading for section in article.sections if section.heading]
        candidates = [
            section
            for section in article.sections
            if section.heading and not _blocked_heading(section.heading)
        ]
        inline = []
        for section in candidates:
            if len(inline) >= max(0, self.max_inline_images):
                break
            image_type = _image_type_for_section(section.heading, rules["allowed_types"])
            if not image_type:
                continue
            inline.append(
                {
                    "section_heading": section.heading,
                    "placement": _placement_for_section(section.heading),
                    "image_type": image_type,
                    "prompt": _prompt(
                        image_type=image_type,
                        article=article,
                        request_data=request_data,
                        section_heading=section.heading,
                        rules=rules,
                        brand_style=self.brand_style,
                    ),
                    "alt_text": f"{section.heading} visual for {article.title or request_data.get('title') or 'the article'}",
                    "caption": f"Editorial visual support for {section.heading}.",
                    "approval_required": True,
                    "reason": "This section benefits from a visual that clarifies a comparison, process, concept, trend, or product context.",
                    "safety_notes": rules["avoid_rules"],
                }
            )
        should_generate = bool(article.title and (article.sections or article.research_metadata_panel))
        featured_type = _featured_type(rules["allowed_types"])
        return {
            "should_generate_images": should_generate,
            "reason": "Images are suggested only where they add orientation, comparison, process, concept, trend, or product-context value."
            if should_generate
            else "No useful visual placement was inferred from the article structure.",
            "detected_vertical": detected_vertical,
            "image_rules_source": active_vertical_profile.id if self.enable_vertical_rules and active_vertical_profile.id != "generic" else "generic",
            "active_vertical": active_vertical_profile.id,
            "generic_rules": GENERIC_PROFILE.summary(),
            "vertical_rules": active_vertical_profile.summary() if self.enable_vertical_rules else {},
            "safety_context": safety_context or {},
            "featured_image": {
                "recommended": should_generate,
                "image_type": featured_type,
                "placement": "featured",
                "prompt": _prompt(
                    image_type=featured_type,
                    article=article,
                    request_data=request_data,
                    section_heading="featured image",
                    rules=rules,
                    brand_style=self.brand_style,
                ),
                "alt_text": f"Editorial visual for {article.title or request_data.get('title') or request_data.get('target_keyword') or 'article'}",
                "caption": "Editorial image planned for manual review.",
                "approval_required": True,
                "safety_notes": rules["avoid_rules"],
            },
            "inline_images": inline,
            "section_headings": sections,
        }


def _image_rules(profile: VerticalProfile, enable_vertical_rules: bool) -> dict[str, list[str]]:
    allowed_types = list(GENERIC_PROFILE.image_allowed_types)
    avoid_rules = list(GENERIC_PROFILE.image_avoid_rules)
    style_guidance = list(GENERIC_PROFILE.image_style_guidance)
    unsafe = list(GENERIC_PROFILE.unsafe_visual_concepts)
    contexts = list(GENERIC_PROFILE.preferred_visual_contexts)
    if enable_vertical_rules and profile.id != "generic":
        allowed_types = list(dict.fromkeys([*allowed_types, *profile.image_allowed_types]))
        avoid_rules = list(dict.fromkeys([*avoid_rules, *profile.image_avoid_rules]))
        style_guidance = list(dict.fromkeys([*style_guidance, *profile.image_style_guidance]))
        unsafe = list(dict.fromkeys([*unsafe, *profile.unsafe_visual_concepts]))
        contexts = list(dict.fromkeys([*contexts, *profile.preferred_visual_contexts]))
    return {
        "allowed_types": allowed_types,
        "avoid_rules": avoid_rules,
        "style_guidance": style_guidance,
        "unsafe_visual_concepts": unsafe,
        "preferred_visual_contexts": contexts,
    }


def _featured_type(allowed_types: list[str]) -> str:
    for preferred in ("featured_editorial_image", "editorial_fashion_image", "lifestyle_outfit_image", "abstract_saas_productivity_image", "ingredient_education_visual", "abstract_scientific_editorial_image"):
        if preferred in allowed_types:
            return preferred
    return allowed_types[0] if allowed_types else "featured_editorial_image"


def _image_type_for_section(heading: str, allowed_types: list[str]) -> str:
    lower = heading.lower()
    preferences = [
        (("comparison", "compare", "versus", "vs"), ("comparison_visual", "material_comparison_visual")),
        (("workflow", "process", "steps", "how"), ("process_workflow_visual", "ui_workflow_diagram", "care_maintenance_workflow")),
        (("concept", "related", "ecosystem", "map"), ("concept_map",)),
        (("trend", "seasonal", "runway"), ("trend_visual", "seasonal_trend_collage")),
        (("metadata", "research", "mechanism"), ("diagram", "mechanism_diagram", "formulation_concept_graphic")),
        (("checklist", "tips", "care"), ("checklist_graphic", "care_maintenance_workflow")),
        (("product", "category", "material", "fit", "style"), ("product_context_image", "lifestyle_image", "styling_flat_lay")),
    ]
    for hints, types in preferences:
        if any(hint in lower for hint in hints):
            for image_type in types:
                if image_type in allowed_types:
                    return image_type
    return "concept_map" if "concept_map" in allowed_types else (allowed_types[0] if allowed_types else "")


def _placement_for_section(heading: str) -> str:
    lower = heading.lower()
    if any(term in lower for term in ("comparison", "workflow", "process", "mechanism")):
        return "after_section_intro"
    if any(term in lower for term in ("metadata", "related", "trend")):
        return "before_section"
    return "after_section"


def _blocked_heading(heading: str) -> bool:
    lower = heading.lower()
    return any(hint in lower for hint in BLOCKED_SECTION_HINTS)


def _prompt(
    *,
    image_type: str,
    article: ArticleSchema,
    request_data: dict[str, Any],
    section_heading: str,
    rules: dict[str, list[str]],
    brand_style: str,
) -> str:
    title = article.title or str(request_data.get("title") or "")
    keyword = article.primary_keyword or str(request_data.get("target_keyword") or "")
    product = str(request_data.get("product_name") or "")
    style = "; ".join(rules.get("style_guidance", []))
    avoid = "; ".join(rules.get("avoid_rules", []))
    contexts = ", ".join(rules.get("preferred_visual_contexts", [])[:6])
    return (
        f"Create a {brand_style} {image_type.replace('_', ' ')} for the article '{title}'. "
        f"Topic/keyword: {keyword}. Product/category context: {product}. "
        f"Placement context: {section_heading}. Useful visual contexts: {contexts}. "
        f"Style guidance: {style}. Avoid: {avoid}. No text overlay unless the visual is explicitly an infographic."
    )
