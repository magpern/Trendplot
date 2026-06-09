from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.config import Settings

if TYPE_CHECKING:
    from app.providers.model_router import ModelTask, ModelTier


class ReasoningDecisionSource(StrEnum):
    TASK_OVERRIDE = "task_override"
    TIER_DEFAULT = "tier_default"
    GLOBAL_DEFAULT = "global_default"
    DISABLED = "disabled"


@dataclass(slots=True)
class ReasoningDecision:
    enabled: bool
    effort: str | None
    source: ReasoningDecisionSource


class ReasoningPolicy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(self, task: "ModelTask", tier: "ModelTier") -> ReasoningDecision:
        task_effort = self._task_override(task)
        if task_effort is not None:
            if task_effort == "off":
                return ReasoningDecision(False, None, ReasoningDecisionSource.TASK_OVERRIDE)
            return ReasoningDecision(True, task_effort, ReasoningDecisionSource.TASK_OVERRIDE)

        tier_enabled = self._tier_enabled(tier)
        tier_effort = self._tier_effort(tier)
        if tier_enabled is not None:
            if not tier_enabled:
                return ReasoningDecision(False, None, ReasoningDecisionSource.TIER_DEFAULT)
            return ReasoningDecision(True, tier_effort or self._suggested_effort(task, tier), ReasoningDecisionSource.TIER_DEFAULT)

        if self.settings.openai_enable_reasoning:
            return ReasoningDecision(
                True,
                self._global_effort_for_task(task, tier),
                ReasoningDecisionSource.GLOBAL_DEFAULT,
            )

        return ReasoningDecision(False, None, ReasoningDecisionSource.DISABLED)

    def _task_override(self, task: "ModelTask") -> str | None:
        raw = self.settings.openai_reasoning_task_overrides.get(task.value)
        if raw is None:
            return None
        normalized = raw.strip().lower()
        if normalized in {"false", "off", "disabled", "none", "no", "0"}:
            return "off"
        return _normalize_effort(normalized)

    def _tier_enabled(self, tier: "ModelTier") -> bool | None:
        return self.settings.openai_reasoning_tier_enabled.get(tier.value)

    def _tier_effort(self, tier: "ModelTier") -> str | None:
        raw = self.settings.openai_reasoning_tier_effort.get(tier.value)
        return _normalize_effort(raw) if raw else None

    def _global_effort_for_task(self, task: "ModelTask", tier: "ModelTier") -> str:
        return _normalize_effort(self.settings.openai_reasoning_effort)

    def _suggested_effort(self, task: "ModelTask", tier: "ModelTier") -> str:
        if task.value in {"section_expansion", "sanity_review", "biomedical_review"}:
            return "high"
        if task.value in {"article_generation", "article_repair", "humanization", "quality_review"}:
            return "medium"
        if tier.value == "standard":
            return "low"
        return "low"


def _normalize_effort(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high"}:
        return "medium"
    return normalized
