"""Article generation prompt template expectations."""

from app.prompts import ArticlePromptInput, build_article_prompt


def test_article_generation_prompt_word_count_guidance() -> None:
    prompt = build_article_prompt(
        ArticlePromptInput(
            title="Storage Guide",
            target_keyword="bacteriostatic water storage",
            product_name="BAC Water",
            product_url="https://example.com/bac-water/",
            min_word_count=1800,
            max_word_count=3000,
        )
    )
    text = str(prompt)
    assert "1800" in text and "3000" in text
    assert "2400" in text  # midpoint
    assert "Do not use broken range phrasing" in text
    assert "sections[0] and sections[1]" in text


def test_article_generation_prompt_anti_repetition_and_links() -> None:
    prompt = build_article_prompt(
        ArticlePromptInput(
            title="CRM for Agencies",
            target_keyword="crm for agencies",
            product_name="AgencyCRM",
            product_url="https://example.com/agencycrm/",
            min_word_count=1500,
            max_word_count=2500,
        )
    )
    text = str(prompt)
    assert "call_to_action" not in text
    assert "internal_links must include" in text
    assert "AgencyCRM" in text
    assert "Do not repeat the same safety warning" in text
    assert "ecommerce, SaaS, services" in text.lower() or "ecommerce, SaaS" in text
    assert "10–15%" in text or "10-15%" in text
