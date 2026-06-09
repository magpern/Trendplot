from app.opportunities.verticals.base import VerticalProfile


SHOES_PROFILE = VerticalProfile(
    id="shoes",
    name="Shoes",
    description="Footwear, fit, materials, care, styling, and activity-specific shoe intelligence.",
    domain_keywords={"shoe", "shoes", "sneaker", "sneakers", "boots", "loafers", "sandals", "footwear"},
    known_entities={"sneakers", "running shoes", "boots", "loafers", "sandals", "leather", "suede", "cushioning", "arch support", "outsole", "midsole", "fit", "sizing"},
    concept_hints={"sizing", "fit", "care", "materials", "occasion styling", "running", "streetwear", "hiking", "foot comfort"},
    entity_expansion_map={
        "running-shoes": ["cushioning", "arch support", "outsole", "midsole", "training surfaces", "injury prevention language"],
        "boots": ["leather care", "weatherproofing", "outsole traction", "seasonal styling"],
        "loafers": ["office style", "smart casual", "leather care", "fit"],
        "suede": ["material care", "water protection", "seasonal styling"],
    },
    product_family_map={
        "athletic shoes": {"running-shoes", "trainers", "sneakers"},
        "dress shoes": {"loafers", "oxfords", "derbies"},
        "boots": {"boots", "chelsea-boots", "hiking-boots"},
        "sandals": {"sandals", "slides"},
    },
    adjacent_niche_map={
        "shoes": ["foot comfort", "seasonal fashion", "care guides", "occasion styling"],
        "sneakers": ["streetwear", "running", "trend analysis", "fit guides"],
        "boots": ["hiking", "weather care", "seasonal fashion"],
    },
    compliance_profile={
        "rules": ["Avoid unsupported comfort, orthopedic, material, waterproof, or durability claims."],
        "risk": "low",
    },
    opportunity_type_weights={"care_maintenance": 1.1, "style_guide": 1.1, "comparison_article": 1.0, "category_guide": 1.0},
    title_style_guidance=["Use practical fit, material, care, and occasion-based framing."],
    image_allowed_types=[
        "lifestyle_outfit_image",
        "product_context_image",
        "material_comparison_visual",
        "care_maintenance_workflow",
        "fit_sizing_guide_visual",
    ],
    image_avoid_rules=[
        "Avoid fake branded logos.",
        "Avoid unsupported orthopedic or medical claims.",
        "Avoid misleading performance, waterproof, or durability claims.",
    ],
    image_style_guidance=["Use practical footwear context, material, fit, and care visuals."],
    featured_image_preferences=["Lifestyle or product-context footwear visual without fake branding."],
    inline_image_preferences=["Use sizing, material comparison, or care workflow visuals where helpful."],
    unsafe_visual_concepts=["fake logo", "orthopedic claim", "medical claim", "guaranteed performance"],
    preferred_visual_contexts=["fit", "sizing", "materials", "care", "occasion styling"],
)
