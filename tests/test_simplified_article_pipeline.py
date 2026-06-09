"""Gates and helpers for the simplified article generation pipeline."""

from app.config import Settings
from app.services.article_pipeline import (
    effective_max_repair_passes,
    should_run_humanization,
    should_run_narrative_editor,
    should_run_section_expansion,
    should_run_semantic_sanity,
    should_run_youtube_ai_evaluation,
    skipped_section_expansion_result,
)


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_simplified_pipeline_defaults_disable_expensive_stages() -> None:
    settings = _settings()
    assert settings.simplified_article_pipeline is True
    assert should_run_humanization(settings) is False
    assert should_run_narrative_editor(settings) is False
    assert should_run_semantic_sanity(settings) is False
    assert should_run_youtube_ai_evaluation(settings) is False
    assert should_run_section_expansion(settings, publishable_word_count=500) is False
    assert should_run_section_expansion(settings, publishable_word_count=2500) is False


def test_simplified_pipeline_caps_repair_passes() -> None:
    settings = _settings(max_repair_passes=3)
    assert effective_max_repair_passes(settings) == 1


def test_legacy_pipeline_enables_all_llm_stages() -> None:
    settings = _settings(simplified_article_pipeline=False, max_repair_passes=3)
    assert should_run_humanization(settings) is True
    assert should_run_narrative_editor(settings) is True
    assert should_run_semantic_sanity(settings) is True
    assert should_run_youtube_ai_evaluation(settings) is True
    assert should_run_section_expansion(settings, publishable_word_count=5000) is True
    assert effective_max_repair_passes(settings) == 3


def test_section_expansion_opt_in_when_under_word_target() -> None:
    settings = _settings(enable_section_expansion=True)
    assert should_run_section_expansion(settings, publishable_word_count=1200) is True
    assert should_run_section_expansion(settings, publishable_word_count=2200) is False


def test_skipped_section_expansion_preserves_word_count() -> None:
    from app.article_schema import ArticleSchema

    article = ArticleSchema.model_validate(
        {
            "title": "Test",
            "slug": "test",
            "excerpt": "Excerpt",
            "meta_title": "Test",
            "meta_description": "Desc",
            "primary_keyword": "kw",
            "sections": [{"heading": "One", "content_markdown": "Body " * 50}],
        }
    )
    result = skipped_section_expansion_result(article, reason="disabled", word_count=900)
    assert result.summary["skipped"] is True
    assert result.summary["word_count_before"] == 900
    assert result.article.title == "Test"
