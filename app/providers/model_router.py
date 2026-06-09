from dataclasses import dataclass
from enum import StrEnum

from app.config import Settings
from app.providers.reasoning_policy import ReasoningPolicy


class ModelTier(StrEnum):
    LIGHT = "light"
    STANDARD = "standard"
    PREMIUM = "premium"


class ModelTask(StrEnum):
    WEBSITE_ANALYSIS = "website_analysis"
    AUDIENCE_INTELLIGENCE = "audience_intelligence"
    AUTHORITY_GRAPH_MAPPING = "authority_graph_mapping"
    YOUTUBE_EVALUATION = "youtube_evaluation"
    SEO_METADATA = "seo_metadata"
    SOCIAL_POST_GENERATION = "social_post_generation"
    BACKLINK_PLANNING = "backlink_planning"
    SIMPLE_EXTRACTION = "simple_extraction"
    CATEGORY_LOOKUP = "category_lookup"
    CLEANUP = "cleanup"
    CLASSIFICATION = "classification"
    ARTICLE_GENERATION = "article_generation"
    ARTICLE_REPAIR = "article_repair"
    SECTION_EXPANSION = "section_expansion"
    HUMANIZATION = "humanization"
    AI_EDITORIAL_STRATEGIST = "ai_editorial_strategist"
    AI_RECOMMENDATION_REVIEW = "ai_recommendation_review"
    QUALITY_REVIEW = "quality_review"
    SANITY_REVIEW = "sanity_review"
    BIOMEDICAL_REVIEW = "biomedical_review"
    FAQ_GENERATION = "faq_generation"
    IMAGE_PROMPT_GENERATION = "image_prompt_generation"


@dataclass(slots=True)
class ModelSelection:
    task_type: ModelTask
    tier: ModelTier
    model: str
    max_output_tokens: int
    reasoning_enabled: bool = False
    reasoning_supported: bool = False
    reasoning_effort: str | None = None
    reasoning_source: str = "disabled"


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.reasoning_policy = ReasoningPolicy(settings)
        self._task_tiers = {
            ModelTask.SIMPLE_EXTRACTION: ModelTier.LIGHT,
            ModelTask.CATEGORY_LOOKUP: ModelTier.LIGHT,
            ModelTask.CLEANUP: ModelTier.LIGHT,
            ModelTask.CLASSIFICATION: ModelTier.LIGHT,
            ModelTask.AI_EDITORIAL_STRATEGIST: ModelTier.LIGHT,
            ModelTask.AI_RECOMMENDATION_REVIEW: ModelTier.LIGHT,
            ModelTask.WEBSITE_ANALYSIS: ModelTier.STANDARD,
            ModelTask.AUDIENCE_INTELLIGENCE: ModelTier.STANDARD,
            ModelTask.AUTHORITY_GRAPH_MAPPING: ModelTier.STANDARD,
            ModelTask.YOUTUBE_EVALUATION: ModelTier.STANDARD,
            ModelTask.SOCIAL_POST_GENERATION: ModelTier.STANDARD,
            ModelTask.SEO_METADATA: ModelTier.STANDARD,
            ModelTask.BACKLINK_PLANNING: ModelTier.STANDARD,
            ModelTask.FAQ_GENERATION: ModelTier.STANDARD,
            ModelTask.IMAGE_PROMPT_GENERATION: ModelTier.STANDARD,
            ModelTask.ARTICLE_GENERATION: ModelTier.PREMIUM,
            ModelTask.ARTICLE_REPAIR: ModelTier.PREMIUM,
            ModelTask.SECTION_EXPANSION: ModelTier.PREMIUM,
            ModelTask.HUMANIZATION: ModelTier.PREMIUM,
            ModelTask.QUALITY_REVIEW: ModelTier.PREMIUM,
            ModelTask.SANITY_REVIEW: ModelTier.PREMIUM,
            ModelTask.BIOMEDICAL_REVIEW: ModelTier.PREMIUM,
        }

    def select(self, task_type: ModelTask | str) -> ModelSelection:
        task = ModelTask(task_type)
        tier = self._task_tiers.get(task, ModelTier.STANDARD)
        model = self._model_for_tier(tier)
        reasoning_supported = supports_reasoning(model)
        reasoning_decision = self.reasoning_policy.decide(task, tier)
        reasoning_enabled = bool(reasoning_decision.enabled and reasoning_supported)
        return ModelSelection(
            task_type=task,
            tier=tier,
            model=model,
            max_output_tokens=self._max_output_tokens_for_task(task, tier),
            reasoning_supported=reasoning_supported,
            reasoning_enabled=reasoning_enabled,
            reasoning_effort=reasoning_decision.effort if reasoning_enabled else None,
            reasoning_source=reasoning_decision.source.value,
        )

    def estimate_cost(
        self,
        selection: ModelSelection,
        token_input: int | None,
        token_output: int | None,
    ) -> float | None:
        if token_input is None and token_output is None:
            return None
        input_rate, output_rate = self._rates_for_tier(selection.tier)
        return round(
            ((token_input or 0) / 1_000_000 * input_rate)
            + ((token_output or 0) / 1_000_000 * output_rate),
            6,
        )

    def _model_for_tier(self, tier: ModelTier) -> str:
        if tier == ModelTier.LIGHT:
            return self.settings.openai_light_model
        if tier == ModelTier.PREMIUM:
            return self.settings.openai_premium_model
        return self.settings.openai_standard_model

    def _rates_for_tier(self, tier: ModelTier) -> tuple[float, float]:
        if tier == ModelTier.LIGHT:
            return (
                self.settings.openai_light_input_cost_per_1m,
                self.settings.openai_light_output_cost_per_1m,
            )
        if tier == ModelTier.PREMIUM:
            return (
                self.settings.openai_premium_input_cost_per_1m,
                self.settings.openai_premium_output_cost_per_1m,
            )
        return (
            self.settings.openai_standard_input_cost_per_1m,
            self.settings.openai_standard_output_cost_per_1m,
        )

    def _max_output_tokens_for_task(self, task: ModelTask, tier: ModelTier) -> int:
        task_specific = {
            ModelTask.ARTICLE_GENERATION: self.settings.openai_max_output_tokens_article_generation,
            ModelTask.ARTICLE_REPAIR: self.settings.openai_max_output_tokens_article_repair,
            ModelTask.SECTION_EXPANSION: self.settings.openai_max_output_tokens_section_expansion,
            ModelTask.HUMANIZATION: self.settings.openai_max_output_tokens_humanization,
            ModelTask.WEBSITE_ANALYSIS: self.settings.openai_max_output_tokens_website_analysis,
        }.get(task)
        if task_specific:
            return max(1, task_specific)
        if tier == ModelTier.LIGHT:
            return max(1, self.settings.openai_max_output_tokens_light)
        if tier == ModelTier.PREMIUM:
            return max(1, self.settings.openai_max_output_tokens_premium)
        return max(1, self.settings.openai_max_output_tokens_standard)

def supports_reasoning(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return normalized.startswith(("gpt-5", "o1", "o3", "o4"))


def uses_max_completion_tokens(model_name: str) -> bool:
    return supports_reasoning(model_name)

