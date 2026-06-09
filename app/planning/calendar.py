from datetime import datetime, timedelta, timezone
from typing import Any


CONTENT_MIX = (
    "trend_article",
    "product_deep_dive",
    "glossary_page",
    "comparison_page",
    "supporting_article",
    "faq_geo_page",
)


class ContentCalendarEngine:
    def build_plan(
        self,
        *,
        workspace: dict[str, Any],
        understanding: dict[str, Any] | None,
        opportunities: list[dict[str, Any]],
        trend_signals: list[dict[str, Any]],
        coverage: list[dict[str, Any]] | None = None,
        horizon_days: int = 30,
    ) -> dict[str, Any]:
        cadence = str(workspace.get("cadence") or "weekly")
        interval_days = _cadence_interval(cadence)
        max_items = max(1, min(30, horizon_days // interval_days if interval_days else horizon_days))
        selected = _select_opportunities(opportunities, trend_signals, coverage or [], max_items)
        if not selected:
            selected = [
                {
                    "title": f"Publishing plan for {workspace.get('name') or workspace.get('website_url') or 'the site'}",
                    "target_keyword": str((understanding or {}).get("detected_niche") or "publishing strategy"),
                    "content_role": "supporting_article",
                    "source_type": "fallback",
                    "needs_verification": True,
                }
            ]
        start = datetime.now(timezone.utc) + timedelta(days=1)
        items = []
        for index, opportunity in enumerate(selected):
            role = _content_role(opportunity, index)
            scheduled_for = start + timedelta(days=index * interval_days)
            items.append(
                {
                    "sequence_index": index + 1,
                    "scheduled_for": scheduled_for.isoformat(),
                    "state": "planned",
                    "opportunity_id": opportunity.get("id"),
                    "trend_signal_id": opportunity.get("_trend_signal_id"),
                    "content_role": role,
                    "title": str(opportunity.get("title") or opportunity.get("trend_topic") or "Untitled publishing opportunity"),
                    "target_keyword": str(opportunity.get("target_keyword") or opportunity.get("trend_topic") or ""),
                    "audience": _audience_label(opportunity, understanding),
                    "notes": _notes(opportunity, role),
                    "policy": str(workspace.get("mode") or "manual_review"),
                    "metadata": {
                        "cluster_id": opportunity.get("cluster_id"),
                        "source_type": opportunity.get("source_type") or "inferred",
                        "content_mix_role": role,
                        "planner_action": opportunity.get("_planner_action") or "create",
                        "coverage_gap_score": opportunity.get("_coverage_gap_score"),
                        "cannibalization_risk": opportunity.get("_cannibalization_risk"),
                        "refresh_score": opportunity.get("_refresh_score"),
                        "needs_verification": bool(opportunity.get("needs_verification", True)),
                    },
                }
            )
        return {
            "plan": {
                "name": "30-day publishing plan",
                "cadence": cadence,
                "publish_policy": str(workspace.get("mode") or "manual_review"),
                "horizon_days": horizon_days,
                "status": "draft",
                "summary": _summary(workspace, understanding, items),
                "plan": {
                    "content_mix": CONTENT_MIX,
                    "item_count": len(items),
                    "generated_by": "trendplot-calendar-engine",
                },
            },
            "items": items,
        }


def _cadence_interval(cadence: str) -> int:
    if cadence == "daily":
        return 1
    if cadence == "custom":
        return 3
    return 7


def _select_opportunities(
    opportunities: list[dict[str, Any]],
    trend_signals: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    max_items: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_clusters: set[str] = set()
    coverage_index = _coverage_index(coverage)
    trend_candidates = [
        {
            **signal,
            "id": signal.get("content_opportunity_id"),
            "title": signal.get("trend_topic"),
            "target_keyword": signal.get("trend_topic"),
            "content_role": signal.get("recommended_format") or "trend_article",
            "_trend_signal_id": signal.get("id"),
            "_planning_priority": _planning_priority(signal, coverage_index),
            **_coverage_metadata(signal.get("trend_topic"), coverage_index),
        }
        for signal in trend_signals
    ]
    opportunity_candidates = [
        {
            **opportunity,
            "_planning_priority": _planning_priority(opportunity, coverage_index),
            **_coverage_metadata(opportunity.get("target_keyword") or opportunity.get("title"), coverage_index),
        }
        for opportunity in opportunities
    ]
    ordered = sorted([*trend_candidates, *opportunity_candidates], key=lambda item: item.get("_planning_priority") or 0, reverse=True)
    for candidate in ordered:
        if candidate.get("_planner_action") == "skip":
            continue
        cluster = str(candidate.get("cluster_id") or candidate.get("trend_topic") or candidate.get("target_keyword") or "")
        if cluster and cluster in seen_clusters and len(selected) < len(CONTENT_MIX):
            continue
        if cluster:
            seen_clusters.add(cluster)
        selected.append(candidate)
        if len(selected) >= max_items:
            break
    return selected


def _content_role(opportunity: dict[str, Any], index: int) -> str:
    role = str(opportunity.get("content_role") or opportunity.get("recommended_format") or "").strip()
    if role:
        return role
    return CONTENT_MIX[index % len(CONTENT_MIX)]


def _audience_label(opportunity: dict[str, Any], understanding: dict[str, Any] | None) -> str:
    if opportunity.get("audience"):
        return str(opportunity["audience"])
    audiences = (understanding or {}).get("audiences") if isinstance((understanding or {}).get("audiences"), list) else []
    if audiences:
        first = audiences[0]
        if isinstance(first, dict):
            return str(first.get("name") or "Primary audience")
        return str(first)
    return "Primary audience"


def _notes(opportunity: dict[str, Any], role: str) -> str:
    action = opportunity.get("_planner_action")
    if action == "refresh":
        return f"Refresh existing coverage for this topic. {opportunity.get('_coverage_reason') or ''}".strip()
    if action == "alternate_angle":
        return "Use a differentiated angle because existing coverage is close to saturation or has cannibalization risk."
    if opportunity.get("evidence_summary"):
        return str(opportunity["evidence_summary"])
    if opportunity.get("why_it_matters"):
        return str(opportunity["why_it_matters"])
    if opportunity.get("recommended_angle"):
        return str(opportunity["recommended_angle"])
    if opportunity.get("rationale"):
        return str(opportunity["rationale"])
    return f"Scheduled as {role.replace('_', ' ')} to support publishing authority without repeating the same cluster."


def _summary(workspace: dict[str, Any], understanding: dict[str, Any] | None, items: list[dict[str, Any]]) -> str:
    niche = str((understanding or {}).get("detected_niche") or "the site")
    cadence = str(workspace.get("cadence") or "weekly")
    return f"Trendplot planned {len(items)} {cadence} publishing items for {niche}, balancing trend, evergreen, and authority-building content."


def _coverage_index(coverage: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for item in coverage:
        name = str(item.get("name") or "").lower()
        if name:
            indexed[name] = item
    return indexed


def _coverage_metadata(topic: Any, coverage_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    coverage = _matching_coverage(str(topic or ""), coverage_index)
    if not coverage:
        return {"_planner_action": "create", "_coverage_gap_score": 1.0, "_cannibalization_risk": 0.0, "_refresh_score": 0.0}
    cannibalization = float(coverage.get("cannibalization_risk") or 0)
    saturation = float(coverage.get("saturation_score") or 0)
    refresh_score = float(coverage.get("refresh_score") or 0)
    gap_score = float(coverage.get("gap_score") or 0)
    if coverage.get("refresh_candidate"):
        action = "refresh"
    elif cannibalization >= 0.7 or saturation >= 0.85:
        action = "alternate_angle"
    elif gap_score <= 0.15:
        action = "skip"
    else:
        action = "create"
    return {
        "_planner_action": action,
        "_coverage_gap_score": gap_score,
        "_cannibalization_risk": cannibalization,
        "_refresh_score": refresh_score,
        "_coverage_reason": coverage.get("refresh_reason") or "",
    }


def _planning_priority(candidate: dict[str, Any], coverage_index: dict[str, dict[str, Any]]) -> float:
    metadata = _coverage_metadata(candidate.get("trend_topic") or candidate.get("target_keyword") or candidate.get("title"), coverage_index)
    base = float(candidate.get("opportunity_score") or candidate.get("priority_score") or candidate.get("confidence_score") or 0.5)
    gap = float(metadata.get("_coverage_gap_score") or 0)
    refresh = float(metadata.get("_refresh_score") or 0)
    cannibalization = float(metadata.get("_cannibalization_risk") or 0)
    return round(base + gap * 0.25 + refresh * 0.2 - cannibalization * 0.2, 3)


def _matching_coverage(topic: str, coverage_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    words = {word for word in topic.lower().split() if len(word) > 3}
    for key, coverage in coverage_index.items():
        key_words = {word for word in key.split() if len(word) > 3}
        if topic.lower() == key or (words and key_words and words & key_words):
            return coverage
    return None
