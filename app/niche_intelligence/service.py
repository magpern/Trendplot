import re
from typing import Any

from app.niche_intelligence.models import WorkspaceNicheProfile


class NicheIntelligenceService:
    """Builds persistent, generic niche memory for a workspace."""

    def build_profile(
        self,
        *,
        workspace: dict[str, Any],
        understanding: dict[str, Any] | None,
        competitor_snapshots: list[dict[str, Any]],
        trend_signals: list[dict[str, Any]],
        coverage: list[dict[str, Any]],
        existing_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        understanding = understanding or {}
        existing_profile = existing_profile or {}
        primary_niche = _first_text(
            understanding.get("detected_niche"),
            existing_profile.get("primary_niche"),
            workspace.get("name"),
            "generic",
        )
        secondary_niches = _dedupe(
            [
                *_list_values(existing_profile.get("secondary_niches")),
                *_secondary_from_understanding(understanding),
                *_coverage_names(coverage, {"cluster", "entity"})[:12],
            ],
            skip={primary_niche},
            limit=30,
        )
        known_products = _dedupe(
            [
                *_list_values(existing_profile.get("known_products")),
                *_string_items(understanding.get("products_services")),
                *_competitor_values(competitor_snapshots, "products_services"),
            ],
            limit=60,
        )
        known_entities = _dedupe(
            [
                *_list_values(existing_profile.get("known_entities")),
                *known_products,
                *_string_items(understanding.get("content_gaps")),
                *_trend_topics(trend_signals),
                *_coverage_names(coverage, {"entity"}),
            ],
            limit=100,
        )
        known_categories = _dedupe(
            [
                *_list_values(existing_profile.get("known_categories")),
                *_string_items(understanding.get("trust_topics")),
                *_competitor_values(competitor_snapshots, "topics"),
                *_coverage_names(coverage, {"cluster", "search_intent"}),
            ],
            limit=60,
        )
        known_audiences = _dedupe(
            [
                *_list_values(existing_profile.get("known_audiences")),
                *_string_items(understanding.get("audiences")),
                *_coverage_names(coverage, {"audience"}),
            ],
            limit=40,
        )
        terminology = _dedupe(
            [
                *_list_values(existing_profile.get("common_terminology")),
                *_terms([primary_niche, *secondary_niches, *known_entities, *known_categories]),
            ],
            limit=80,
        )
        confidence = _confidence(
            understanding=understanding,
            existing_profile=existing_profile,
            competitor_snapshots=competitor_snapshots,
            trend_signals=trend_signals,
            coverage=coverage,
        )
        profile = WorkspaceNicheProfile(
            primary_niche=primary_niche,
            secondary_niches=secondary_niches,
            known_entities=known_entities,
            known_products=known_products,
            known_categories=known_categories,
            known_audiences=known_audiences,
            common_terminology=terminology,
            confidence=confidence,
            sources={
                "site_understanding_id": understanding.get("id"),
                "analysis_job_id": understanding.get("analysis_job_id"),
                "competitor_snapshots": len(competitor_snapshots),
                "trend_signals": len(trend_signals),
                "coverage_records": len(coverage),
                "existing_profile_id": existing_profile.get("id"),
            },
        )
        return profile.as_dict()


def _first_text(*values: Any) -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return "generic"


def _secondary_from_understanding(understanding: dict[str, Any]) -> list[str]:
    vertical = understanding.get("vertical_detection") if isinstance(understanding.get("vertical_detection"), dict) else {}
    values = []
    values.extend(_string_items(vertical.get("secondary_verticals")))
    values.extend(_string_items(vertical.get("candidate_verticals")))
    values.extend(_string_items(understanding.get("trust_topics")))
    return values


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = [value] if value else []
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(_clean(item.get("name") or item.get("title") or item.get("topic") or item.get("description")))
        else:
            result.append(_clean(item))
    return [item for item in result if item]


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    if isinstance(value, str):
        return [_clean(item) for item in value.split(",") if _clean(item)]
    return []


def _competitor_values(snapshots: list[dict[str, Any]], key: str) -> list[str]:
    values = []
    for snapshot in snapshots:
        values.extend(_string_items(snapshot.get(key)))
    return values


def _trend_topics(signals: list[dict[str, Any]]) -> list[str]:
    return [_clean(signal.get("trend_topic") or signal.get("query")) for signal in signals if _clean(signal.get("trend_topic") or signal.get("query"))]


def _coverage_names(coverage: list[dict[str, Any]], coverage_types: set[str]) -> list[str]:
    return [
        _clean(item.get("name"))
        for item in coverage
        if str(item.get("coverage_type") or "") in coverage_types and _clean(item.get("name"))
    ]


def _terms(values: list[str]) -> list[str]:
    terms = []
    ignored = {"and", "the", "for", "with", "from", "into", "this", "that", "guide", "overview"}
    for value in values:
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", value):
            if token.lower() not in ignored:
                terms.append(token)
    return terms


def _dedupe(values: list[str], *, skip: set[str] | None = None, limit: int = 50) -> list[str]:
    result = []
    seen = {_clean(item).lower() for item in skip or set() if _clean(item)}
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _confidence(
    *,
    understanding: dict[str, Any],
    existing_profile: dict[str, Any],
    competitor_snapshots: list[dict[str, Any]],
    trend_signals: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> float:
    base = float(understanding.get("niche_confidence") or existing_profile.get("confidence") or 0.45)
    source_bonus = 0.0
    if competitor_snapshots:
        source_bonus += 0.08
    if trend_signals:
        source_bonus += 0.06
    if coverage:
        source_bonus += 0.06
    if existing_profile:
        source_bonus += 0.05
    return round(max(0.0, min(1.0, base + source_bonus)), 3)


def _clean(value: Any) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" -:,.")
    return cleaned[:120]
