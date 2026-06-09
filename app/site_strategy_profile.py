from __future__ import annotations

import re
from typing import Any

from app.analysis_digest import build_website_analysis_digest
from app.opportunities.signals import build_signal_inventory

_NAV_TITLE = re.compile(
    r"\b(shop|store|contact|cart|checkout|privacy|terms|login|home|about us|cookie)\b",
    re.I,
)


def _string_list(value: Any, *, limit: int = 50) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("name") or item.get("title") or "").strip()
            else:
                text = str(item).strip()
            if text:
                items.append(text)
    else:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if _NAV_TITLE.search(item):
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _audience_names(audiences: list[Any]) -> list[str]:
    names: list[str] = []
    for row in audiences or []:
        if isinstance(row, dict):
            name = str(row.get("name") or row.get("audience_type") or "").strip()
        else:
            name = str(row).strip()
        if name:
            names.append(name)
    return _string_list(names, limit=8)


def _cluster_names(clusters: list[Any]) -> list[str]:
    names: list[str] = []
    for row in clusters or []:
        if isinstance(row, dict):
            name = str(row.get("name") or "").strip()
        else:
            name = str(row).strip()
        if name:
            names.append(name)
    return _string_list(names, limit=12)


def _inventory_titles(content_inventory: list[dict[str, Any]] | None, *, limit: int = 40) -> list[str]:
    titles: list[str] = []
    for row in content_inventory or []:
        title = str(row.get("title") or "").strip()
        if not title or _NAV_TITLE.search(title):
            continue
        titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def build_site_strategy_profile(
    *,
    ai_extraction: dict[str, Any] | None,
    website: dict[str, Any],
    competitors: list[dict[str, Any]] | None = None,
    content_inventory: list[dict[str, Any]] | None = None,
    vertical: str = "auto",
) -> dict[str, Any]:
    """Compact persisted profile: what the site is (not what articles to write)."""
    ai_extraction = ai_extraction or {}
    niche = ai_extraction.get("niche_intelligence") or {}
    product_intel = ai_extraction.get("product_intelligence") or {}
    signals = build_signal_inventory(website, competitors or [], vertical=vertical)
    digest = build_website_analysis_digest(website, competitors or [], max_pages_per_site=40, max_competitor_pages=4)
    rollup = (digest.get("website") or {}).get("rollup") or {}

    products = _string_list(
        [
            *(product_intel.get("extracted_products") or []),
            *(rollup.get("product_page_titles") or []),
            *(signals.get("product_intelligence", {}).get("extracted_products") or []),
            *(signals.get("product_candidates") or []),
        ],
        limit=40,
    )
    categories = _string_list(
        [
            *(rollup.get("category_pages") or []),
            *(signals.get("product_intelligence", {}).get("product_families") or []),
        ],
        limit=20,
    )
    audiences = _audience_names(ai_extraction.get("audiences") or [])
    clusters = _cluster_names(ai_extraction.get("clusters") or ai_extraction.get("topical_clusters") or [])
    existing_articles = _inventory_titles(content_inventory)

    business_type = str(
        ai_extraction.get("business_type")
        or niche.get("business_type")
        or signals.get("vertical_intelligence", {}).get("business_type")
        or "ecommerce"
    ).strip()

    return {
        "business_type": business_type,
        "primary_niche": str(
            ai_extraction.get("primary_niche")
            or niche.get("primary_niche")
            or ai_extraction.get("detected_vertical")
            or signals.get("niche_intelligence", {}).get("primary_niche")
            or "generic"
        ).strip(),
        "secondary_niches": _string_list(
            ai_extraction.get("secondary_niches") or niche.get("secondary_niches") or niche.get("adjacent_niches"),
            limit=10,
        ),
        "known_products": products,
        "known_categories": categories,
        "audiences": audiences,
        "topical_clusters": clusters,
        "existing_articles": existing_articles,
        "content_inventory_summary": str(ai_extraction.get("content_inventory_summary") or ai_extraction.get("summary") or "")[:500],
    }


def strategy_profile_from_understanding(understanding: dict[str, Any] | None) -> dict[str, Any] | None:
    if not understanding:
        return None
    source = understanding.get("source") or {}
    if isinstance(source, dict) and isinstance(source.get("strategy_profile"), dict):
        return source["strategy_profile"]
    profile = understanding.get("strategy_profile")
    return profile if isinstance(profile, dict) else None


def strategy_profile_from_niche_and_inventory(
    niche_profile: dict[str, Any] | None,
    *,
    understanding: dict[str, Any] | None = None,
    content_inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    niche_profile = niche_profile or {}
    understanding = understanding or {}
    return {
        "business_type": "ecommerce",
        "primary_niche": str(
            niche_profile.get("primary_niche")
            or understanding.get("detected_niche")
            or "generic"
        ).strip(),
        "secondary_niches": _string_list(niche_profile.get("secondary_niches"), limit=10),
        "known_products": _string_list(niche_profile.get("known_products"), limit=40),
        "known_categories": _string_list(niche_profile.get("known_categories"), limit=20),
        "audiences": _string_list(niche_profile.get("known_audiences"), limit=8),
        "topical_clusters": _string_list(niche_profile.get("known_categories"), limit=12),
        "existing_articles": _inventory_titles(content_inventory),
        "content_inventory_summary": str(understanding.get("summary") or "")[:500] if understanding else "",
    }


def resolve_site_strategy_profile(
    *,
    understanding: dict[str, Any] | None = None,
    niche_profile: dict[str, Any] | None = None,
    content_inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = strategy_profile_from_understanding(understanding)
    if profile:
        if content_inventory and not profile.get("existing_articles"):
            profile = {**profile, "existing_articles": _inventory_titles(content_inventory)}
        return profile
    return strategy_profile_from_niche_and_inventory(
        niche_profile,
        understanding=understanding,
        content_inventory=content_inventory,
    )


def build_strategist_context_from_profile(
    profile: dict[str, Any],
    *,
    max_ideas: int = 40,
    coverage_gaps: list[str] | None = None,
    competitor_seo_patterns: list[str] | None = None,
    existing_eog_titles: list[str] | None = None,
) -> dict[str, Any]:
    """Minimal strategist input — DeepSeek-style product/niche list."""
    existing = _string_list(profile.get("existing_articles") or [], limit=40)
    existing.extend(_string_list(existing_eog_titles or [], limit=20))
    return {
        "business_type": str(profile.get("business_type") or "ecommerce"),
        "primary_niche": str(profile.get("primary_niche") or ""),
        "secondary_niches": _string_list(profile.get("secondary_niches"), limit=8),
        "known_products": _string_list(profile.get("known_products"), limit=30),
        "known_categories": _string_list(profile.get("known_categories"), limit=15),
        "audiences": _string_list(profile.get("audiences"), limit=8),
        "topical_clusters": _string_list(profile.get("topical_clusters"), limit=10),
        "existing_articles": _string_list(existing, limit=50),
        "coverage_gaps": _string_list(coverage_gaps or [], limit=12),
        "competitor_seo_patterns": _string_list(competitor_seo_patterns or [], limit=8),
        "max_ideas_hint": max(1, int(max_ideas)),
    }


def build_legacy_strategist_context(
    *,
    workspace: dict[str, Any] | None,
    understanding: dict[str, Any] | None,
    niche_profile: dict[str, Any] | None,
    content_inventory: list[dict[str, Any]] | None = None,
    coverage: list[dict[str, Any]] | None = None,
    competitor_snapshots: list[dict[str, Any]] | None = None,
    existing_eog_titles: list[str] | None = None,
    max_ideas: int = 40,
) -> dict[str, Any]:
    """Wide context shape retained for size/comparison tests (legacy strategist removed)."""
    profile = resolve_site_strategy_profile(
        understanding=understanding,
        niche_profile=niche_profile,
        content_inventory=content_inventory,
    )
    ctx = build_strategist_context_from_profile(
        profile,
        max_ideas=max_ideas,
        existing_eog_titles=existing_eog_titles,
    )
    pages = (understanding or {}).get("pages") or []
    return {
        **ctx,
        "workspace": workspace or {},
        "pages": pages[:50],
        "content_inventory": content_inventory or [],
        "coverage": coverage or [],
        "competitor_snapshots": competitor_snapshots or [],
        "max_ideas_hint": max_ideas,
    }


def build_reviewer_context_from_profile(
    profile: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "business_type": profile.get("business_type"),
        "primary_niche": profile.get("primary_niche"),
        "known_products": _string_list(profile.get("known_products"), limit=30),
        "known_categories": _string_list(profile.get("known_categories"), limit=15),
        "existing_articles": _string_list(profile.get("existing_articles"), limit=20),
        "recommendations": recommendations,
    }


def strip_ideation_from_extraction(ai_extraction: dict[str, Any]) -> dict[str, Any]:
    """Remove article seeds from website analysis model output before downstream use."""
    cleaned = dict(ai_extraction)
    cleaned["opportunities"] = []
    cleaned["suggestions"] = []
    cleaned["authority_graph"] = {"nodes": [], "edges": []}
    return cleaned
