from app.opportunities.verticals.base import VerticalProfile


FASHION_PROFILE = VerticalProfile(
    id="fashion",
    name="Fashion / Bags",
    description="Fashion, bags, styling, material, and trend intelligence.",
    domain_keywords={"fashion", "bag", "bags", "luxury", "designer", "runway", "style", "wardrobe"},
    known_entities={"leather", "canvas", "tote", "crossbody", "clutch", "luxury", "runway", "capsule wardrobe", "paris fashion week", "seasonal trends"},
    concept_hints={"styling", "fashion week", "designer comparisons", "sustainability", "materials", "capsule wardrobe", "seasonal trends"},
    entity_expansion_map={
        "leather": ["material care", "grain types", "patina", "sustainability", "occasion styling"],
        "tote": ["work bags", "commuter style", "capacity", "material comparisons"],
        "crossbody": ["hands-free styling", "travel outfits", "strap design", "day-to-night use"],
        "runway": ["seasonal trends", "luxury aesthetics", "designer inspiration", "street style"],
    },
    product_family_map={
        "bags": {"tote", "crossbody", "clutch", "shoulder-bag", "bucket-bag"},
        "apparel": {"dress", "dresses", "blazer", "coat", "knitwear"},
    },
    adjacent_niche_map={
        "fashion": ["styling", "fashion week", "designer comparisons", "sustainability", "materials"],
        "bag": ["occasion styling", "material guides", "care guides", "capsule wardrobes"],
        "luxury": ["runway culture", "investment pieces", "craftsmanship"],
    },
    compliance_profile={
        "rules": ["Avoid fake designer, origin, sustainability, or material claims not present in crawl data."],
        "risk": "medium",
    },
    opportunity_type_weights={"style_guide": 1.2, "trend_article": 1.1, "comparison_article": 1.0, "care_maintenance": 0.9},
    title_style_guidance=["Use editorial styling and trend language grounded in the crawl data."],
    image_allowed_types=[
        "editorial_fashion_image",
        "styling_flat_lay",
        "outfit_pairing_visual",
        "material_comparison_visual",
        "seasonal_trend_collage",
    ],
    image_avoid_rules=[
        "Avoid fake luxury logos.",
        "Avoid counterfeit implication.",
        "Avoid copyrighted runway imitation or specific designer style copying.",
    ],
    image_style_guidance=["Use brand-safe editorial styling visuals without logo imitation."],
    featured_image_preferences=["Editorial fashion or styling visual grounded in the article topic."],
    inline_image_preferences=["Use outfit pairing, material comparison, or seasonal trend visuals where helpful."],
    unsafe_visual_concepts=["fake luxury logo", "counterfeit", "designer imitation", "copyrighted runway"],
    preferred_visual_contexts=["styling", "materials", "seasonal trends", "outfit pairing"],
)
