from app.opportunities.verticals.base import VerticalProfile


SOFTWARE_PROFILE = VerticalProfile(
    id="software",
    name="Software / SaaS",
    description="Software, SaaS, workflow, integration, implementation, and operations intelligence.",
    domain_keywords={"software", "saas", "platform", "api", "workflow", "automation", "integration"},
    known_entities={"api", "workflow", "automation", "integration", "security", "onboarding", "compliance", "analytics", "dashboard", "webhook"},
    mechanism_hints={"authentication", "data sync", "workflow automation", "role-based access", "reporting", "onboarding"},
    concept_hints={"operations", "productivity", "data governance", "ai workflows", "implementation", "roi", "migration", "security"},
    entity_expansion_map={
        "api": ["integration patterns", "authentication", "webhooks", "developer onboarding"],
        "workflow": ["automation", "handoffs", "approvals", "team operations"],
        "security": ["access control", "audit trails", "data governance", "compliance questions"],
        "analytics": ["reporting", "dashboards", "decision support", "roi"],
    },
    product_family_map={
        "platform features": {"api", "dashboard", "analytics", "automation"},
        "integrations": {"integration", "webhook", "connector"},
        "security features": {"security", "compliance", "audit"},
    },
    adjacent_niche_map={
        "software": ["operations", "productivity", "implementation", "ROI"],
        "api": ["developer experience", "integration guides", "automation workflows"],
        "security": ["data governance", "compliance education", "risk reduction"],
    },
    compliance_profile={
        "rules": ["Avoid unsupported security, compliance, uptime, data protection, or ROI guarantees."],
        "risk": "medium",
    },
    opportunity_type_weights={"use_case": 1.1, "comparison_article": 1.0, "implementation_guide": 1.1, "roi_article": 0.9},
    title_style_guidance=["Use practical implementation, use-case, comparison, and ROI framing."],
    image_allowed_types=[
        "ui_workflow_diagram",
        "abstract_saas_productivity_image",
        "integration_map",
        "process_diagram",
        "concept_map",
    ],
    image_avoid_rules=[
        "Avoid fake screenshots of real platforms.",
        "Avoid unsupported security or compliance seals.",
        "Avoid misleading analytics, ROI, or uptime claims.",
    ],
    image_style_guidance=["Use abstract UI, workflow, and integration visuals without copying real platform screens."],
    featured_image_preferences=["Abstract productivity or workflow visual."],
    inline_image_preferences=["Use workflow diagrams, process diagrams, or integration maps."],
    unsafe_visual_concepts=["fake screenshot", "security seal", "compliance badge", "misleading analytics"],
    preferred_visual_contexts=["workflow", "integration", "process", "security concept", "analytics concept"],
)
