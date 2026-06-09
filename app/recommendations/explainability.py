from __future__ import annotations

from typing import Any


def build_recommendation_audit_report(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        explain = meta.get("explainability") if isinstance(meta.get("explainability"), dict) else {}
        items.append(
            {
                "title": rec.get("title"),
                "topic": rec.get("topic"),
                "action": rec.get("action"),
                "final_score": rec.get("score"),
                **explain,
            }
            if explain
            else {
                "title": rec.get("title"),
                "topic": rec.get("topic"),
                "action": rec.get("action"),
                "final_score": rec.get("score"),
                "niche_relevance": rec.get("niche_relevance"),
                "business_relevance": rec.get("business_relevance"),
                "coverage_gap": rec.get("coverage_gap"),
                "competitor_evidence": rec.get("competitor_gap"),
                "external_demand": rec.get("demand_score") if rec.get("has_external_evidence") else 0,
                "entity_relevance": meta.get("entity_relevance"),
                "action_reason": rec.get("explanation"),
                "rank_reason": "",
            }
        )

    def by_action(action: str) -> list[dict[str, Any]]:
        return sorted(
            [item for item in items if str(item.get("action") or "").lower() == action],
            key=lambda row: float(row.get("final_score") or 0),
            reverse=True,
        )

    create_items = by_action("create")
    monitor_items = by_action("monitor")
    return {
        "summary": {
            "total": len(items),
            "create": len(create_items),
            "monitor": len(monitor_items),
            "refresh": len(by_action("refresh")),
            "expand": len(by_action("expand")),
            "merge": len(by_action("merge")),
            "ignore": len(by_action("ignore")),
        },
        "top_create": create_items[:20],
        "top_monitor": monitor_items[:20],
        "items": items,
    }
