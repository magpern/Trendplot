from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkspaceNicheProfile:
    primary_niche: str = "generic"
    secondary_niches: list[str] = field(default_factory=list)
    known_entities: list[str] = field(default_factory=list)
    known_products: list[str] = field(default_factory=list)
    known_categories: list[str] = field(default_factory=list)
    known_audiences: list[str] = field(default_factory=list)
    common_terminology: list[str] = field(default_factory=list)
    confidence: float = 0.5
    sources: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary_niche": self.primary_niche,
            "secondary_niches": self.secondary_niches,
            "known_entities": self.known_entities,
            "known_products": self.known_products,
            "known_categories": self.known_categories,
            "known_audiences": self.known_audiences,
            "common_terminology": self.common_terminology,
            "confidence": self.confidence,
            "sources": self.sources,
        }
