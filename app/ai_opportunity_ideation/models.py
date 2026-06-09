from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEARCH_INTENTS = frozenset(
    {
        "informational",
        "comparison",
        "how_to",
        "faq",
        "calculator",
        "research_overview",
        "product_handling",
        "storage",
        "reconstitution",
        "mechanism",
        "product_relationship",
    }
)

CONTENT_TYPES = frozenset(
    {
        "guide",
        "comparison",
        "faq",
        "calculator_support",
        "research_overview",
        "how_to",
        "troubleshooting",
        "mechanism_explainer",
        "relationship",
    }
)

RECOMMENDATION_TYPES = frozenset({"create", "refresh", "expand", "follow_up"})


@dataclass(slots=True)
class AIOpportunity:
    headline: str
    abstract: str
    search_intent: str
    content_type: str
    related_products: list[str] = field(default_factory=list)
    related_topics: list[str] = field(default_factory=list)
    target_audience: str = ""
    priority_reason: str = ""
    safety_notes: list[str] = field(default_factory=list)
    recommendation_type: str = "create"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_row(
        self,
        *,
        workspace_id: str,
        run_id: str,
        opportunity_id: str,
        created_at: str,
    ) -> dict[str, Any]:
        return {
            "id": opportunity_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "headline": self.headline,
            "abstract": self.abstract,
            "search_intent": self.search_intent,
            "content_type": self.content_type,
            "recommendation_type": self.recommendation_type,
            "related_products_json": list(self.related_products),
            "related_topics_json": list(self.related_topics),
            "target_audience": self.target_audience,
            "priority_reason": self.priority_reason,
            "safety_notes_json": list(self.safety_notes),
            "metadata_json": {},
            "created_at": created_at,
        }
