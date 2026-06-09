from app.opportunities.verticals.base import VerticalProfile


SUPPLEMENTS_PROFILE = VerticalProfile(
    id="supplements",
    name="Supplements",
    description="Supplement ecommerce and wellness education with conservative health-claim boundaries.",
    domain_keywords={"supplement", "supplements", "vitamin", "protein", "wellness", "nutrition"},
    known_entities={"ingredients", "formulation", "purity", "third-party testing", "label transparency", "routine", "wellness", "protein", "vitamin", "magnesium"},
    mechanism_hints={"absorption", "bioavailability", "formulation", "quality testing", "label transparency"},
    concept_hints={"ingredient science", "routine", "wellness", "fitness", "nutrition", "sleep", "recovery", "testing transparency"},
    entity_expansion_map={
        "magnesium": ["forms comparison", "routine building", "label transparency", "sleep wellness context"],
        "protein": ["amino acid profile", "fitness routines", "sourcing", "flavor comparison"],
        "vitamin": ["formulation", "routine context", "testing transparency", "label literacy"],
    },
    product_family_map={
        "vitamins": {"vitamin", "vitamin-d", "vitamin-d3", "vitamin-d3-k2"},
        "minerals": {"magnesium", "zinc", "iron"},
        "protein products": {"protein", "whey", "collagen"},
    },
    adjacent_niche_map={
        "supplement": ["wellness", "fitness", "nutrition", "sleep", "recovery"],
        "protein": ["fitness", "routine guides", "ingredient comparisons"],
        "vitamin": ["label literacy", "routine building", "testing transparency"],
    },
    compliance_profile={
        "rules": [
            "Do not make disease treatment, cure, diagnostic, or guaranteed health outcome claims.",
            "Avoid unsupported structure/function claims.",
        ],
        "risk": "high",
    },
    opportunity_type_weights={"mechanism_explainer": 1.0, "comparison_article": 1.1, "faq_cluster": 1.0, "sourcing_guide": 1.0},
    title_style_guidance=["Use careful wellness, ingredient, and label-literacy framing."],
    image_allowed_types=[
        "ingredient_education_visual",
        "lifestyle_neutral_image",
        "formulation_concept_graphic",
        "label_reading_infographic",
        "concept_map",
    ],
    image_avoid_rules=[
        "Avoid disease cure implication.",
        "Avoid before/after body imagery.",
        "Avoid medical treatment scenes.",
        "Avoid exaggerated health-result visuals.",
    ],
    image_style_guidance=["Use neutral wellness and ingredient education visuals without outcome claims."],
    featured_image_preferences=["Lifestyle-neutral or ingredient-education visual."],
    inline_image_preferences=["Use label-reading, formulation, or comparison infographics where helpful."],
    unsafe_visual_concepts=["disease cure", "before and after", "medical treatment", "guaranteed health result"],
    preferred_visual_contexts=["ingredient education", "label literacy", "routine context", "formulation"],
)
