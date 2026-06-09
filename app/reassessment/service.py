from typing import Any


class ReassessmentService:
    def build_report(
        self,
        *,
        workspace: dict[str, Any],
        understanding: dict[str, Any] | None,
        plan_items: list[dict[str, Any]],
        trend_signals: list[dict[str, Any]],
        published_content: list[dict[str, Any]],
        provider_status: list[dict[str, Any]],
        coverage: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        coverage = coverage or []
        planned_count = len([item for item in plan_items if item.get("state") in {"planned", "approved", "scheduled"}])
        failed_count = len([item for item in plan_items if item.get("state") == "failed"])
        published_count = len(published_content)
        trend_count = len(trend_signals)
        coverage_gaps = [item for item in coverage if (item.get("gap_score") or 0) >= 0.5]
        refresh_candidates = [item for item in coverage if item.get("refresh_candidate")]
        cannibalization_risks = [item for item in coverage if (item.get("cannibalization_risk") or 0) >= 0.7]
        adjustments = []
        if not understanding:
            adjustments.append("Run website intelligence before enabling autopilot.")
        if planned_count == 0:
            adjustments.append("Generate a fresh 30-day publishing plan.")
        if failed_count:
            adjustments.append("Review failed plan items before scheduling more automatic publishing.")
        if trend_count == 0:
            adjustments.append("Refresh trend signals or continue with evergreen opportunities.")
        if coverage_gaps:
            adjustments.append("Prioritize uncovered entities, clusters, audiences, or intents before adding more similar content.")
        if refresh_candidates:
            adjustments.append("Refresh older published coverage before creating entirely new articles for the same topic.")
        if cannibalization_risks:
            adjustments.append("Avoid duplicate content angles where Publishing Memory detects cannibalization risk.")
        degraded = [item for item in provider_status if item.get("status") not in {"ok", "connected"}]
        if degraded:
            adjustments.append("Some intelligence providers are unavailable; confidence should stay conservative.")
        if not adjustments:
            adjustments.append("Current calendar is healthy; keep monitoring trend freshness and cluster coverage.")
        return {
            "status": "completed",
            "summary": (
                f"Reassessed {workspace.get('name') or 'workspace'} with {planned_count} upcoming items, "
                f"{published_count} published items, and {trend_count} trend signals."
            ),
            "strategy_adjustments": adjustments,
            "new_opportunities": _new_opportunity_notes(trend_signals),
            "retired_opportunities": [],
            "recommended_refreshes": _refresh_notes(published_content, refresh_candidates),
            "calendar_diff": {
                "planned_items": planned_count,
                "failed_items": failed_count,
                "published_items": published_count,
                "trend_signals": trend_count,
                "coverage_gaps": len(coverage_gaps),
                "refresh_candidates": len(refresh_candidates),
                "cannibalization_risks": len(cannibalization_risks),
            },
            "provider_status": {
                "providers": provider_status,
                "degraded_count": len(degraded),
            },
        }


def _new_opportunity_notes(trend_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "trend_topic": signal.get("trend_topic"),
            "recommended_format": signal.get("recommended_format"),
            "reason": "Trend signal remains available for future calendar planning.",
        }
        for signal in trend_signals[:5]
    ]


def _refresh_notes(published_content: list[dict[str, Any]], refresh_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage_notes = [
        {
            "title": item.get("name"),
            "url": None,
            "reason": item.get("refresh_reason") or "Publishing Memory marked this topic as a refresh candidate.",
            "refresh_score": item.get("refresh_score"),
        }
        for item in refresh_candidates[:5]
    ]
    fallback_notes = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "reason": "Check for freshness during the next performance feedback cycle.",
        }
        for item in published_content[:5]
    ]
    return coverage_notes or fallback_notes
