from typing import Any


def summarize_competitor_gaps(signal_inventory: dict[str, Any]) -> dict[str, Any]:
    overlap = signal_inventory.get("competitor_overlap", {})
    competitor_only = overlap.get("competitor_only_terms", [])
    shared = overlap.get("shared_terms", [])
    return {
        "shared_terms": shared,
        "competitor_only_terms": competitor_only,
        "gap_count": len(competitor_only),
        "overlap_ratio": overlap.get("overlap_ratio", 0),
        "priority_terms": competitor_only[:25],
    }
