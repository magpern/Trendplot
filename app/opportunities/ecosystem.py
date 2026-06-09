from typing import Any

from app.opportunities.schemas import AudienceProfile, OpportunityCluster


def summarize_editorial_ecosystem(
    signal_inventory: dict[str, Any],
    audiences: list[AudienceProfile],
    clusters: list[OpportunityCluster],
) -> dict[str, Any]:
    return {
        "top_terms": signal_inventory.get("terms", [])[:25],
        "questions": signal_inventory.get("questions", [])[:25],
        "audience_count": len(audiences),
        "cluster_count": len(clusters),
        "pillar_candidates": [cluster.name for cluster in clusters if cluster.pillar_candidate],
        "support_clusters": [cluster.name for cluster in clusters if not cluster.pillar_candidate],
    }
