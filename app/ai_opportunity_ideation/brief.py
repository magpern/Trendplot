from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.catalog.products import build_catalog_products, catalog_dedupe_key
from app.catalog.sitemap_products import discover_sitemap_catalog_products
from app.config import Settings
from app.catalog.filters import is_entity_quality_junk, is_navigation_label
from app.repositories import Repositories
from app.site_strategy_profile import _inventory_titles, _string_list, resolve_site_strategy_profile

_RESEARCH_NICHE = re.compile(
    r"\b(peptides?|research|laboratory|labs?|ruo|biomedical|compounds?|ecommerce)\b",
    re.I,
)

GENERIC_SUGGESTED_THEMES = [
    "storage",
    "handling",
    "comparison articles",
    "FAQ and guide articles",
    "troubleshooting",
    "buyer guides",
    "research overviews",
]

PEPTIDE_SUGGESTED_THEMES = [
    "research overviews",
    "mechanism and background explainers",
    "comparison articles",
    "product relationship articles",
    "FAQ and guide articles",
    "lab calculations",
    "storage",
    "reconstitution",
    "handling",
]

PEPTIDE_THEME_MIX_TARGETS: dict[str, Any] = {
    "science_overview_pct": [30, 40],
    "comparison_relationship_pct": [30, 35],
    "mechanism_pct": [15, 20],
    "handling_storage_pct": [15, 20],
    "faq_resource_pct": [5, 10],
    "max_handling_storage_pct": 25,
    "min_multi_product_pct": 20,
}

GENERIC_THEME_MIX_TARGETS: dict[str, Any] = {
    "science_overview_pct": [25, 35],
    "comparison_relationship_pct": [20, 30],
    "mechanism_pct": [10, 15],
    "handling_storage_pct": [15, 25],
    "faq_resource_pct": [5, 15],
    "max_handling_storage_pct": 30,
    "min_multi_product_pct": 15,
}


def _is_peptide_niche(*, niche: str, niche_profile: dict[str, Any] | None) -> bool:
    niche_blob = " ".join(
        [
            str(niche or ""),
            str((niche_profile or {}).get("primary_niche") or ""),
            str((niche_profile or {}).get("vertical_id") or ""),
        ]
    ).lower()
    return "peptide" in niche_blob or str((niche_profile or {}).get("vertical_id") or "").strip() == "peptides"


def _suggested_ideation_themes(*, niche: str, niche_profile: dict[str, Any] | None) -> list[str]:
    if _is_peptide_niche(niche=niche, niche_profile=niche_profile):
        return list(PEPTIDE_SUGGESTED_THEMES)
    return list(GENERIC_SUGGESTED_THEMES)


def _theme_mix_targets(*, niche: str, niche_profile: dict[str, Any] | None) -> dict[str, Any]:
    if _is_peptide_niche(niche=niche, niche_profile=niche_profile):
        return dict(PEPTIDE_THEME_MIX_TARGETS)
    return dict(GENERIC_THEME_MIX_TARGETS)


def _product_coverage_requirements(catalog_count: int) -> dict[str, Any]:
    if catalog_count > 75:
        return {
            "mode": "large_catalog",
            "per_product_min_science_overview": 0,
            "per_product_min_comparison_or_relationship": 0,
            "note": "Catalog has more than 75 products; prioritize major SKUs for science and comparison coverage.",
        }
    return {
        "mode": "full_catalog",
        "per_product_min_science_overview": 1,
        "per_product_min_comparison_or_relationship": 1,
        "note": (
            "Each catalog product needs at least one science/research overview and "
            "one comparison or product-relationship article. Do not satisfy coverage with handling-only ideas."
        ),
    }


def _competitor_domains(snapshots: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()
    for row in snapshots or []:
        url = str(row.get("competitor_url") or row.get("url") or "").strip()
        if not url:
            continue
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if not host or host in seen:
            continue
        seen.add(host)
        domains.append(host)
        if len(domains) >= limit:
            break
    return domains


def _competitor_gap_topics(snapshots: list[dict[str, Any]], *, limit: int = 15) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for row in snapshots or []:
        for key in ("topics", "products_services", "content_gaps", "gap_notes"):
            values = row.get(key)
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                continue
            for item in values:
                text = str(item if not isinstance(item, dict) else item.get("name") or item.get("title") or "").strip()
                key_norm = text.lower()
                if not text or key_norm in seen:
                    continue
                seen.add(key_norm)
                topics.append(text)
                if len(topics) >= limit:
                    return topics
    return topics


def _audience_names(understanding: dict[str, Any] | None, profile: dict[str, Any]) -> list[str]:
    names: list[str] = _string_list(profile.get("audiences"), limit=8)
    for row in (understanding or {}).get("audiences") or []:
        if isinstance(row, dict):
            name = str(row.get("name") or row.get("audience_type") or "").strip()
        else:
            name = str(row).strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= 8:
            break
    return names


def _filtered_services(understanding: dict[str, Any] | None) -> list[str]:
    raw = (understanding or {}).get("products_services") or []
    names: list[str] = []
    for row in raw:
        if isinstance(row, dict):
            text = str(row.get("name") or row.get("title") or "").strip()
        else:
            text = str(row).strip()
        if not text or is_navigation_label(text) or is_entity_quality_junk(text):
            continue
        names.append(text)
        if len(names) >= 20:
            break
    return names


def _filtered_entities(niche_profile: dict[str, Any] | None, profile: dict[str, Any]) -> list[str]:
    entities: list[str] = []
    for item in _string_list((niche_profile or {}).get("known_entities"), limit=25):
        if is_navigation_label(item) or is_entity_quality_junk(item):
            continue
        entities.append(item)
    for item in _string_list((niche_profile or {}).get("common_terminology"), limit=15):
        if item not in entities and not is_navigation_label(item):
            entities.append(item)
    return entities[:30]


def _strategy_product_names(profile: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("known_products",):
        names.extend(_string_list(profile.get(key), limit=50))
    digest = profile.get("analysis_digest") if isinstance(profile.get("analysis_digest"), dict) else {}
    product_intel = digest.get("product_intelligence") if isinstance(digest.get("product_intelligence"), dict) else {}
    rollup = digest.get("rollup") if isinstance(digest.get("rollup"), dict) else {}
    signals = digest.get("signals") if isinstance(digest.get("signals"), dict) else {}
    for source in (
        product_intel.get("extracted_products") or [],
        rollup.get("product_page_titles") or [],
        (signals.get("product_intelligence") or {}).get("extracted_products") or [],
    ):
        for item in source:
            text = str(item if not isinstance(item, dict) else item.get("name") or item.get("title") or "").strip()
            if text:
                names.append(text)
    return names


def _research_context(*, niche: str, trust_topics: list[str]) -> bool:
    blob = " ".join([niche, *trust_topics]).lower()
    return bool(_RESEARCH_NICHE.search(blob))


def _constraints_and_disclaimers(
    *,
    understanding: dict[str, Any] | None,
    niche: str,
    settings: Settings,
) -> tuple[list[str], list[str]]:
    trust = [str(t).strip() for t in (understanding or {}).get("trust_topics") or [] if str(t).strip()]
    constraints: list[str] = []
    disclaimers: list[str] = []
    if _research_context(niche=niche, trust_topics=trust):
        constraints.extend(
            [
                "Research and laboratory use framing only",
                "No human consumption, dosing, treatment, clinical, or veterinary use",
                "No medical claims",
            ]
        )
        if settings.biomedical_ruo_disclaimer:
            disclaimers.append(settings.biomedical_ruo_disclaimer.strip())
    for topic in trust[:5]:
        if topic.lower() not in {d.lower() for d in disclaimers}:
            constraints.append(topic)
    return constraints[:8], disclaimers[:4]


def _truncate(text: str, limit: int = 300) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _site_description(
    understanding: dict[str, Any] | None,
    profile: dict[str, Any],
    workspace: dict[str, Any],
) -> str:
    summary = str((understanding or {}).get("summary") or "").strip()
    if re.search(r"\d+\s+topical article opportunities", summary, re.I):
        summary = ""
    if not summary:
        summary = str(profile.get("content_inventory_summary") or "").strip()
    if not summary or re.search(r"\d+\s+topical article opportunities", summary, re.I):
        url = str(workspace.get("website_url") or "")
        niche = str(profile.get("primary_niche") or "specialty ecommerce")
        summary = f"{niche.replace('_', ' ').title()} ecommerce site ({url})."
    return _truncate(summary)


async def _resolve_workspace_id(
    *,
    workspace_id: str | None,
    analysis_job_id: str | None,
    repositories: Repositories,
) -> tuple[str, str | None]:
    if workspace_id:
        return workspace_id, analysis_job_id
    if not analysis_job_id:
        raise ValueError("Either workspace_id or analysis_job_id is required.")
    job = await repositories.analysis_jobs.get(analysis_job_id)
    if not job:
        raise ValueError(f"Analysis job not found: {analysis_job_id}")
    ws_id = str(job.get("workspace_id") or "").strip()
    if not ws_id:
        raise ValueError(f"Analysis job {analysis_job_id} has no workspace_id.")
    return ws_id, analysis_job_id


def _merge_catalog(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for names in lists:
        for name in names:
            key = catalog_dedupe_key(name)
            if key in seen:
                continue
            seen.add(key)
            merged.append(name)
    return merged


async def build_opportunity_ideation_brief(
    *,
    workspace_id: str | None = None,
    analysis_job_id: str | None = None,
    repositories: Repositories,
    settings: Settings | None = None,
    include_sitemap: bool = True,
) -> dict[str, Any]:
    """Compact product/niche brief for AI opportunity ideation."""
    settings = settings or Settings()
    ws_id, job_id = await _resolve_workspace_id(
        workspace_id=workspace_id,
        analysis_job_id=analysis_job_id,
        repositories=repositories,
    )

    workspace = await repositories.autopilot_workspaces.get(ws_id)
    if not workspace:
        raise ValueError(f"Workspace not found: {ws_id}")

    understanding = await repositories.site_understanding.latest_for_workspace(ws_id)
    niche_profile = await repositories.workspace_niche_profiles.get(ws_id)
    inventory = await repositories.workspace_content_inventory.list_for_workspace(ws_id, limit=500)
    profile = resolve_site_strategy_profile(
        understanding=understanding,
        niche_profile=niche_profile,
        content_inventory=inventory,
    )

    niche = str(
        profile.get("primary_niche")
        or (understanding or {}).get("detected_niche")
        or (niche_profile or {}).get("primary_niche")
        or "generic"
    ).strip()
    site_description = _site_description(understanding, profile, workspace)
    constraints, disclaimers = _constraints_and_disclaimers(
        understanding=understanding,
        niche=niche,
        settings=settings,
    )

    url_discovery_artifact = None
    resolved_job_id = job_id or workspace.get("last_analysis_job_id") or (understanding or {}).get("analysis_job_id")
    if resolved_job_id:
        for artifact in await repositories.analysis_intelligence_artifacts.list_for_job(resolved_job_id):
            if artifact.get("artifact_type") == "url_discovery":
                url_discovery_artifact = artifact.get("content_json")
                break

    website_url = str(workspace.get("website_url") or "")
    sitemap_catalog: dict[str, Any] = {"source": "disabled", "product_names": [], "product_urls": []}
    if include_sitemap and website_url:
        sitemap_catalog = await discover_sitemap_catalog_products(
            website_url,
            settings=settings,
            url_discovery_artifact=url_discovery_artifact if isinstance(url_discovery_artifact, dict) else None,
        )

    workspace_competitors = (workspace.get("settings") or {}).get("competitors") or []
    competitor_snapshots = [
        {"competitor_url": str(url).strip()}
        for url in workspace_competitors
        if str(url).strip()
    ]

    catalog_products = build_catalog_products(
        profile_products=_string_list(profile.get("known_products"), limit=75),
        strategy_products=_strategy_product_names(profile),
        niche_products=_string_list((niche_profile or {}).get("known_products"), limit=75),
        niche_entities=_string_list((niche_profile or {}).get("known_entities"), limit=80),
        services_products=_filtered_services(understanding),
        sitemap_products=list(sitemap_catalog.get("product_names") or []),
        product_urls=list(sitemap_catalog.get("product_urls") or []),
        inventory=inventory,
        max_products=75,
    )

    return {
        "workspace_id": ws_id,
        "analysis_job_id": resolved_job_id,
        "website_url": website_url,
        "site_name": str(workspace.get("name") or workspace.get("website_url") or ws_id),
        "niche": niche,
        "site_description": site_description,
        "business_type": str(profile.get("business_type") or "ecommerce"),
        "catalog_products": catalog_products,
        "products": catalog_products,
        "sitemap_catalog": sitemap_catalog,
        "categories": _string_list(profile.get("known_categories"), limit=20),
        "entities": _filtered_entities(niche_profile, profile),
        "services": _filtered_services(understanding),
        "audiences": _audience_names(understanding, profile),
        "constraints": constraints,
        "disclaimers": disclaimers,
        "existing_page_titles": _inventory_titles(inventory, limit=40),
        "competitor_domains": _competitor_domains(competitor_snapshots),
        "competitor_gap_topics": _competitor_gap_topics(competitor_snapshots),
        "suggested_themes": _suggested_ideation_themes(niche=niche, niche_profile=niche_profile),
        "theme_mix_targets": _theme_mix_targets(niche=niche, niche_profile=niche_profile),
        "product_coverage_requirements": _product_coverage_requirements(len(catalog_products)),
    }
