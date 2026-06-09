from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CoverageSummary:
    coverage_type: str
    name: str
    coverage_score: float
    freshness_score: float
    content_count: int
    published_count: int = 0
    draft_count: int = 0
    gap_score: float = 0.0
    saturation_score: float = 0.0
    cannibalization_risk: float = 0.0
    duplicate_topic_risk: float = 0.0
    refresh_score: float = 0.0
    refresh_candidate: bool = False
    refresh_reason: str = ""
    last_published: str | None = None
    last_updated: str | None = None
    last_major_update: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "coverage_type": self.coverage_type,
            "name": self.name,
            "coverage_score": self.coverage_score,
            "freshness_score": self.freshness_score,
            "content_count": self.content_count,
            "published_count": self.published_count,
            "draft_count": self.draft_count,
            "gap_score": self.gap_score,
            "saturation_score": self.saturation_score,
            "cannibalization_risk": self.cannibalization_risk,
            "duplicate_topic_risk": self.duplicate_topic_risk,
            "refresh_score": self.refresh_score,
            "refresh_candidate": self.refresh_candidate,
            "refresh_reason": self.refresh_reason,
            "last_published": self.last_published,
            "last_updated": self.last_updated,
            "last_major_update": self.last_major_update,
            "metadata": self.metadata,
        }
