from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db import resolve_sqlite_database_path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATABASE_URL = f"sqlite:///{(_PROJECT_ROOT / 'data' / 'seo_content_worker.db').as_posix()}"


class Settings(BaseSettings):
    app_name: str = "seo-content-worker"
    log_level: str = "INFO"

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_light_model: str = Field(default="gpt-4o-mini", alias="OPENAI_LIGHT_MODEL")
    openai_standard_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_STANDARD_MODEL")
    openai_premium_model: str = Field(default="gpt-4.1", alias="OPENAI_PREMIUM_MODEL")
    openai_light_input_cost_per_1m: float = Field(default=0.15, alias="OPENAI_LIGHT_INPUT_COST_PER_1M")
    openai_light_output_cost_per_1m: float = Field(default=0.60, alias="OPENAI_LIGHT_OUTPUT_COST_PER_1M")
    openai_standard_input_cost_per_1m: float = Field(default=0.40, alias="OPENAI_STANDARD_INPUT_COST_PER_1M")
    openai_standard_output_cost_per_1m: float = Field(default=1.60, alias="OPENAI_STANDARD_OUTPUT_COST_PER_1M")
    openai_premium_input_cost_per_1m: float = Field(default=2.00, alias="OPENAI_PREMIUM_INPUT_COST_PER_1M")
    openai_premium_output_cost_per_1m: float = Field(default=8.00, alias="OPENAI_PREMIUM_OUTPUT_COST_PER_1M")
    openai_request_timeout_seconds: float = Field(default=180.0, alias="OPENAI_REQUEST_TIMEOUT_SECONDS")
    openai_provider_name: str = Field(default="openai", alias="OPENAI_PROVIDER_NAME")
    openai_max_output_tokens_light: int = Field(default=2000, alias="OPENAI_MAX_OUTPUT_TOKENS_LIGHT")
    openai_max_output_tokens_standard: int = Field(default=4000, alias="OPENAI_MAX_OUTPUT_TOKENS_STANDARD")
    openai_max_output_tokens_premium: int = Field(default=12000, alias="OPENAI_MAX_OUTPUT_TOKENS_PREMIUM")
    openai_max_output_tokens_article_generation: int | None = Field(
        default=16000,
        alias="OPENAI_MAX_OUTPUT_TOKENS_ARTICLE_GENERATION",
    )
    openai_max_output_tokens_article_repair: int | None = Field(
        default=16000,
        alias="OPENAI_MAX_OUTPUT_TOKENS_ARTICLE_REPAIR",
    )
    openai_max_output_tokens_section_expansion: int | None = Field(
        default=8000,
        alias="OPENAI_MAX_OUTPUT_TOKENS_SECTION_EXPANSION",
    )
    openai_max_output_tokens_humanization: int | None = Field(
        default=16000,
        alias="OPENAI_MAX_OUTPUT_TOKENS_HUMANIZATION",
    )
    openai_max_output_tokens_website_analysis: int | None = Field(
        default=8000,
        alias="OPENAI_MAX_OUTPUT_TOKENS_WEBSITE_ANALYSIS",
    )
    openai_website_analysis_max_retries: int = Field(default=0, alias="OPENAI_WEBSITE_ANALYSIS_MAX_RETRIES")
    website_analysis_max_seed_opportunities: int = Field(default=25, alias="WEBSITE_ANALYSIS_MAX_SEED_OPPORTUNITIES")
    website_analysis_digest_max_pages: int = Field(default=40, alias="WEBSITE_ANALYSIS_DIGEST_MAX_PAGES")
    openai_enable_reasoning: bool = Field(default=False, alias="OPENAI_ENABLE_REASONING")
    openai_reasoning_effort: str = Field(default="medium", alias="OPENAI_REASONING_EFFORT")
    openai_light_reasoning_enabled: bool | None = Field(default=None, alias="OPENAI_LIGHT_REASONING_ENABLED")
    openai_standard_reasoning_enabled: bool | None = Field(default=None, alias="OPENAI_STANDARD_REASONING_ENABLED")
    openai_premium_reasoning_enabled: bool | None = Field(default=None, alias="OPENAI_PREMIUM_REASONING_ENABLED")
    openai_light_reasoning_effort: str | None = Field(default=None, alias="OPENAI_LIGHT_REASONING_EFFORT")
    openai_standard_reasoning_effort: str | None = Field(default=None, alias="OPENAI_STANDARD_REASONING_EFFORT")
    openai_premium_reasoning_effort: str | None = Field(default=None, alias="OPENAI_PREMIUM_REASONING_EFFORT")
    openai_reasoning_article_generation: str | None = Field(default=None, alias="OPENAI_REASONING_ARTICLE_GENERATION")
    openai_reasoning_article_repair: str | None = Field(default=None, alias="OPENAI_REASONING_ARTICLE_REPAIR")
    openai_reasoning_section_expansion: str | None = Field(default=None, alias="OPENAI_REASONING_SECTION_EXPANSION")
    openai_reasoning_sanity_review: str | None = Field(default=None, alias="OPENAI_REASONING_SANITY_REVIEW")
    openai_reasoning_biomedical_review: str | None = Field(default=None, alias="OPENAI_REASONING_BIOMEDICAL_REVIEW")
    openai_reasoning_humanization: str | None = Field(default=None, alias="OPENAI_REASONING_HUMANIZATION")
    openai_reasoning_quality_review: str | None = Field(default=None, alias="OPENAI_REASONING_QUALITY_REVIEW")
    openai_reasoning_website_analysis: str | None = Field(default=None, alias="OPENAI_REASONING_WEBSITE_ANALYSIS")

    wordpress_base_url: str = Field(default="", alias="WORDPRESS_BASE_URL")
    wordpress_username: str = Field(default="", alias="WORDPRESS_USERNAME")
    wordpress_app_password: str = Field(default="", alias="WORDPRESS_APP_PASSWORD")
    wordpress_default_template: str = Field(default="elementor_full_width", alias="WORDPRESS_DEFAULT_TEMPLATE")
    wordpress_default_category_id: str = Field(default="", alias="WORDPRESS_DEFAULT_CATEGORY_ID")
    wordpress_default_category_slug: str = Field(default="", alias="WORDPRESS_DEFAULT_CATEGORY_SLUG")
    wordpress_default_tags: str = Field(default="", alias="WORDPRESS_DEFAULT_TAGS")
    wordpress_auto_create_tags: bool = Field(default=True, alias="WORDPRESS_AUTO_CREATE_TAGS")
    wordpress_max_tags: int = Field(default=8, alias="WORDPRESS_MAX_TAGS")
    wordpress_allow_elementor_canvas: bool = Field(default=False, alias="WORDPRESS_ALLOW_ELEMENTOR_CANVAS")
    wordpress_require_featured_image: bool = Field(default=False, alias="WORDPRESS_REQUIRE_FEATURED_IMAGE")
    wordpress_upload_featured_image: bool = Field(default=False, alias="WORDPRESS_UPLOAD_FEATURED_IMAGE")
    wordpress_fail_on_template_error: bool = Field(default=False, alias="WORDPRESS_FAIL_ON_TEMPLATE_ERROR")
    wordpress_connector_enabled: bool = Field(default=False, alias="WORDPRESS_CONNECTOR_ENABLED")
    wordpress_connector_active_environment: str = Field(default="staging", alias="WORDPRESS_CONNECTOR_ACTIVE_ENVIRONMENT")
    wordpress_connector_base_url: str = Field(default="", alias="WORDPRESS_CONNECTOR_BASE_URL")
    wordpress_connector_site_id: str = Field(default="", alias="WORDPRESS_CONNECTOR_SITE_ID")
    wordpress_connector_secret: str = Field(default="", alias="WORDPRESS_CONNECTOR_SECRET")
    wordpress_connector_staging_base_url: str = Field(default="", alias="WORDPRESS_CONNECTOR_STAGING_BASE_URL")
    wordpress_connector_staging_site_id: str = Field(default="", alias="WORDPRESS_CONNECTOR_STAGING_SITE_ID")
    wordpress_connector_staging_secret: str = Field(default="", alias="WORDPRESS_CONNECTOR_STAGING_SECRET")
    wordpress_connector_production_base_url: str = Field(default="", alias="WORDPRESS_CONNECTOR_PRODUCTION_BASE_URL")
    wordpress_connector_production_site_id: str = Field(default="", alias="WORDPRESS_CONNECTOR_PRODUCTION_SITE_ID")
    wordpress_connector_production_secret: str = Field(default="", alias="WORDPRESS_CONNECTOR_PRODUCTION_SECRET")
    wordpress_connector_timeout_seconds: float = Field(default=30.0, alias="WORDPRESS_CONNECTOR_TIMEOUT_SECONDS")

    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    placeholder_image_url: str = Field(default="", alias="PLACEHOLDER_IMAGE_URL")
    research_use_disclaimer_url: str = Field(default="", alias="RESEARCH_USE_DISCLAIMER_URL")

    database_url: str = Field(
        default=_DEFAULT_DATABASE_URL,
        alias="DATABASE_URL",
    )

    default_publish_policy: str = Field(default="manual_review", alias="DEFAULT_PUBLISH_POLICY")
    publish_policy: str = Field(default="manual_review", alias="PUBLISH_POLICY")
    allow_live_publish: bool = Field(default=False, alias="ALLOW_LIVE_PUBLISH")
    allow_auto_live: bool = Field(default=False, alias="ALLOW_AUTO_LIVE")
    unattended_mode_enabled: bool = Field(default=False, alias="UNATTENDED_MODE_ENABLED")
    unattended_default_publish_policy: str = Field(default="auto_draft", alias="UNATTENDED_DEFAULT_PUBLISH_POLICY")
    unattended_allow_auto_live: bool = Field(default=False, alias="UNATTENDED_ALLOW_AUTO_LIVE")
    unattended_require_quality_pass: bool = Field(default=True, alias="UNATTENDED_REQUIRE_QUALITY_PASS")
    unattended_require_sanity_pass: bool = Field(default=True, alias="UNATTENDED_REQUIRE_SANITY_PASS")
    human_review_required: bool = Field(default=True, alias="HUMAN_REVIEW_REQUIRED")
    autopilot_enabled: bool = Field(default=True, alias="AUTOPILOT_ENABLED")
    autopilot_default_mode: str = Field(default="manual_review", alias="AUTOPILOT_DEFAULT_MODE")
    autopublish_cadence: str = Field(default="weekly", alias="AUTOPUBLISH_CADENCE")
    content_plan_horizon_days: int = Field(default=30, alias="CONTENT_PLAN_HORIZON_DAYS")
    max_autopilot_jobs_per_day: int = Field(default=1, alias="MAX_AUTOPILOT_JOBS_PER_DAY")
    max_pages_per_site: int = Field(default=30, alias="MAX_PAGES_PER_SITE")
    crawl_small_site_full_threshold: int = Field(default=50, alias="CRAWL_SMALL_SITE_FULL_THRESHOLD")
    crawl_large_site_sample_limit: int = Field(default=100, alias="CRAWL_LARGE_SITE_SAMPLE_LIMIT")
    crawl_concurrency_per_domain: int = Field(default=4, alias="CRAWL_CONCURRENCY_PER_DOMAIN")
    crawl_request_timeout_seconds: float = Field(default=15.0, alias="CRAWL_REQUEST_TIMEOUT_SECONDS")
    crawl_retry_count: int = Field(default=1, alias="CRAWL_RETRY_COUNT")
    crawl_retry_backoff_seconds: float = Field(default=2.0, alias="CRAWL_RETRY_BACKOFF_SECONDS")
    crawl_politeness_delay_ms: int = Field(default=250, alias="CRAWL_POLITENESS_DELAY_MS")
    sitemap_discovery_enabled: bool = Field(default=True, alias="SITEMAP_DISCOVERY_ENABLED")
    crawl_fallback_enabled: bool = Field(default=True, alias="CRAWL_FALLBACK_ENABLED")
    sitemap_max_urls_to_parse: int = Field(default=5000, alias="SITEMAP_MAX_URLS_TO_PARSE")
    sitemap_max_sitemaps_to_parse: int = Field(default=50, alias="SITEMAP_MAX_SITEMAPS_TO_PARSE")
    reassessment_enabled: bool = Field(default=True, alias="REASSESSMENT_ENABLED")
    reassessment_interval_days: int = Field(default=7, alias="REASSESSMENT_INTERVAL_DAYS")
    max_repair_passes: int = Field(default=1, alias="MAX_REPAIR_PASSES")
    target_min_word_count: int = Field(default=1800, alias="TARGET_MIN_WORD_COUNT")
    max_section_expansion_passes: int = Field(default=2, alias="MAX_SECTION_EXPANSION_PASSES")
    max_sections_expanded_per_pass: int = Field(default=5, alias="MAX_SECTIONS_EXPANDED_PER_PASS")
    target_section_min_words: int = Field(default=250, alias="TARGET_SECTION_MIN_WORDS")
    target_article_min_words: int = Field(default=1800, alias="TARGET_ARTICLE_MIN_WORDS")
    humanization_rewrite_strength: str = Field(default="editorial_rewrite", alias="HUMANIZATION_REWRITE_STRENGTH")
    simplified_article_pipeline: bool = Field(default=True, alias="SIMPLIFIED_ARTICLE_PIPELINE")
    enable_article_humanization: bool = Field(default=False, alias="ENABLE_ARTICLE_HUMANIZATION")
    enable_narrative_editor: bool = Field(default=False, alias="ENABLE_NARRATIVE_EDITOR")
    enable_semantic_sanity_review: bool = Field(default=False, alias="ENABLE_SEMANTIC_SANITY_REVIEW")
    enable_section_expansion: bool = Field(default=False, alias="ENABLE_SECTION_EXPANSION")
    enable_youtube_ai_evaluation: bool = Field(default=False, alias="ENABLE_YOUTUBE_AI_EVALUATION")
    biomedical_ruo_disclaimer: str = Field(
        default="For research use only. Not intended for human consumption, therapeutic, or diagnostic use.",
        alias="BIOMEDICAL_RUO_DISCLAIMER",
    )
    prompt_template_dir: str = Field(default="app/prompts/templates", alias="PROMPT_TEMPLATE_DIR")
    allow_prompt_fallback: bool = Field(default=False, alias="ALLOW_PROMPT_FALLBACK")
    prompt_strict_mode: bool = Field(default=True, alias="PROMPT_STRICT_MODE")
    enable_jsonld_schema: bool = Field(default=True, alias="ENABLE_JSONLD_SCHEMA")
    article_default_render_surface: str = Field(default="publishable", alias="ARTICLE_DEFAULT_RENDER_SURFACE")
    enable_ai_image_generation: bool = Field(default=False, alias="ENABLE_AI_IMAGE_GENERATION")
    opportunity_vertical: str = Field(default="auto", alias="OPPORTUNITY_VERTICAL")
    enable_external_research: bool = Field(default=False, alias="ENABLE_EXTERNAL_RESEARCH")
    external_research_max_queries: int = Field(default=20, alias="EXTERNAL_RESEARCH_MAX_QUERIES")
    external_research_max_results_per_query: int = Field(default=5, alias="EXTERNAL_RESEARCH_MAX_RESULTS_PER_QUERY")
    enable_academic_research: bool = Field(default=False, alias="ENABLE_ACADEMIC_RESEARCH")
    enable_reddit_research: bool = Field(default=False, alias="ENABLE_REDDIT_RESEARCH")
    web_search_provider: str = Field(default="", alias="WEB_SEARCH_PROVIDER")
    brave_search_api_key: str = Field(default="", alias="BRAVE_SEARCH_API_KEY")
    web_search_timeout_seconds: float = Field(default=10.0, alias="WEB_SEARCH_TIMEOUT_SECONDS")
    duckduckgo_search_timeout_seconds: float = Field(default=10.0, alias="DUCKDUCKGO_SEARCH_TIMEOUT_SECONDS")
    duckduckgo_search_max_results: int = Field(default=10, alias="DUCKDUCKGO_SEARCH_MAX_RESULTS")
    niche_intelligence_enabled: bool = Field(default=True, alias="NICHE_INTELLIGENCE_ENABLED")
    min_analysis_pages_for_create: int = Field(default=8, alias="MIN_ANALYSIS_PAGES_FOR_CREATE")
    ai_opportunity_ideation_enabled: bool = Field(default=True, alias="AI_OPPORTUNITY_IDEATION_ENABLED")
    ai_opportunity_ideation_model: str = Field(default="", alias="AI_OPPORTUNITY_IDEATION_MODEL")
    ai_opportunity_ideation_min_ideas: int = Field(default=40, alias="AI_OPPORTUNITY_IDEATION_MIN_IDEAS")
    ai_opportunity_ideation_max_ideas: int = Field(default=75, alias="AI_OPPORTUNITY_IDEATION_MAX_IDEAS")
    ai_opportunity_ideation_temperature: float = Field(default=0.3, alias="AI_OPPORTUNITY_IDEATION_TEMPERATURE")
    ai_opportunity_ideation_timeout_seconds: float = Field(default=240.0, alias="AI_OPPORTUNITY_IDEATION_TIMEOUT_SECONDS")
    ai_opportunity_ideation_include_sitemap: bool = Field(default=True, alias="AI_OPPORTUNITY_IDEATION_INCLUDE_SITEMAP")
    ai_opportunity_ideation_cache_enabled: bool = Field(default=True, alias="AI_OPPORTUNITY_IDEATION_CACHE_ENABLED")
    ai_opportunity_ideation_cache_ttl_hours: int = Field(default=24, alias="AI_OPPORTUNITY_IDEATION_CACHE_TTL_HOURS")
    ai_opportunity_ideation_max_output_tokens: int = Field(default=16384, alias="AI_OPPORTUNITY_IDEATION_MAX_OUTPUT_TOKENS")
    ai_opportunity_ideation_batch_size: int = Field(default=30, alias="AI_OPPORTUNITY_IDEATION_BATCH_SIZE")
    ai_opportunity_ideation_max_top_up_rounds: int = Field(default=3, alias="AI_OPPORTUNITY_IDEATION_MAX_TOP_UP_ROUNDS")
    ai_image_model: str = Field(default="gpt-image-1", alias="AI_IMAGE_MODEL")
    ai_image_style: str = Field(default="clean editorial scientific", alias="AI_IMAGE_STYLE")
    ai_image_variants_per_placement: int = Field(default=1, alias="AI_IMAGE_VARIANTS_PER_PLACEMENT")
    ai_image_max_images: int = Field(default=3, alias="AI_IMAGE_MAX_IMAGES")
    ai_image_plan_inline_images: bool = Field(default=True, alias="AI_IMAGE_PLAN_INLINE_IMAGES")
    ai_image_max_inline_image_placements: int = Field(default=2, alias="AI_IMAGE_MAX_INLINE_IMAGE_PLACEMENTS")
    ai_image_enable_vertical_rules: bool = Field(default=True, alias="AI_IMAGE_ENABLE_VERTICAL_RULES")
    ai_image_generate_featured: bool = Field(default=True, alias="AI_IMAGE_GENERATE_FEATURED")
    ai_image_output_dir: str = Field(default="data/generated-images", alias="AI_IMAGE_OUTPUT_DIR")
    ai_image_count: int | None = Field(default=None, alias="AI_IMAGE_COUNT")
    ai_image_max_inline_images: int | None = Field(default=None, alias="AI_IMAGE_MAX_INLINE_IMAGES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_sqlite_database_url(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            return value
        return resolve_sqlite_database_path(value, base_dir=_PROJECT_ROOT)

    @computed_field
    @property
    def openai_reasoning_tier_enabled(self) -> dict[str, bool]:
        return {
            key: value
            for key, value in {
                "light": self.openai_light_reasoning_enabled,
                "standard": self.openai_standard_reasoning_enabled,
                "premium": self.openai_premium_reasoning_enabled,
            }.items()
            if value is not None
        }

    @computed_field
    @property
    def openai_reasoning_tier_effort(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "light": self.openai_light_reasoning_effort,
                "standard": self.openai_standard_reasoning_effort,
                "premium": self.openai_premium_reasoning_effort,
            }.items()
            if value
        }

    @computed_field
    @property
    def openai_reasoning_task_overrides(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "article_generation": self.openai_reasoning_article_generation,
                "article_repair": self.openai_reasoning_article_repair,
                "section_expansion": self.openai_reasoning_section_expansion,
                "sanity_review": self.openai_reasoning_sanity_review,
                "biomedical_review": self.openai_reasoning_biomedical_review,
                "humanization": self.openai_reasoning_humanization,
                "quality_review": self.openai_reasoning_quality_review,
                "website_analysis": self.openai_reasoning_website_analysis,
            }.items()
            if value
        }

    @property
    def effective_ai_opportunity_ideation_model(self) -> str:
        return self.ai_opportunity_ideation_model or self.openai_light_model

    @property
    def is_ai_ideation_only_mode(self) -> bool:
        """Product path: website analysis + AI opportunity ideation (sole analyze pipeline)."""
        return bool(self.ai_opportunity_ideation_enabled)

    @property
    def effective_ai_image_variants_per_placement(self) -> int:
        value = self.ai_image_count if self.ai_image_count is not None else self.ai_image_variants_per_placement
        return max(1, min(value, 3))

    @property
    def effective_ai_image_max_images(self) -> int:
        return max(1, min(self.ai_image_max_images, 8))

    @property
    def effective_ai_image_max_inline_image_placements(self) -> int:
        if not self.ai_image_plan_inline_images:
            return 0
        value = (
            self.ai_image_max_inline_images
            if self.ai_image_max_inline_images is not None
            else self.ai_image_max_inline_image_placements
        )
        return max(0, min(value, max(0, self.effective_ai_image_max_images - 1), 7))

    @property
    def effective_ai_image_generate_inline_images(self) -> bool:
        return self.ai_image_plan_inline_images and self.effective_ai_image_max_inline_image_placements > 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
