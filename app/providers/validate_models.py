from app.config import get_settings
from app.providers.model_router import ModelRouter, ModelTask, supports_reasoning, uses_max_completion_tokens


def main() -> None:
    settings = get_settings()
    router = ModelRouter(settings)

    print("OpenAI model routing validation")
    print(f"provider: {settings.openai_provider_name}")
    print(f"request_timeout_seconds: {settings.openai_request_timeout_seconds}")
    print(f"legacy_openai_model: {settings.openai_model} (not used for task routing)")
    print(f"light_model: {settings.openai_light_model}")
    print(f"standard_model: {settings.openai_standard_model}")
    print(f"premium_model: {settings.openai_premium_model}")
    print(
        "max_output_tokens: "
        f"light={settings.openai_max_output_tokens_light}; "
        f"standard={settings.openai_max_output_tokens_standard}; "
        f"premium={settings.openai_max_output_tokens_premium}; "
        f"article_generation={settings.openai_max_output_tokens_article_generation}; "
        f"article_repair={settings.openai_max_output_tokens_article_repair}; "
        f"section_expansion={settings.openai_max_output_tokens_section_expansion}; "
        f"humanization={settings.openai_max_output_tokens_humanization}"
    )
    print(f"reasoning_enabled: {'yes' if settings.openai_enable_reasoning else 'no'}")
    print(f"reasoning_effort_config: {settings.openai_reasoning_effort}")
    print(f"tier_reasoning_enabled: {settings.openai_reasoning_tier_enabled or '{}'}")
    print(f"tier_reasoning_effort: {settings.openai_reasoning_tier_effort or '{}'}")
    print(f"task_reasoning_overrides: {settings.openai_reasoning_task_overrides or '{}'}")
    print("")

    warnings = _model_warnings(settings)
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
        print("")

    print("Task routing:")
    for task in ModelTask:
        selection = router.select(task)
        print(
            " - "
            f"task_type={selection.task_type.value}; "
            f"tier={selection.tier.value}; "
            f"selected_model={selection.model}; "
            f"reasoning_supported={'yes' if selection.reasoning_supported else 'no'}; "
            f"reasoning_enabled={'yes' if selection.reasoning_enabled else 'no'}; "
            f"reasoning_effort={selection.reasoning_effort or 'none'}; "
            f"reasoning_source={selection.reasoning_source}; "
            f"max_output_tokens={selection.max_output_tokens}; "
            f"max_token_parameter={'max_completion_tokens' if uses_max_completion_tokens(selection.model) else 'max_tokens'}; "
            f"estimated_cost_available={'yes' if _cost_available(router, selection) else 'no'}"
        )

    print("")
    print("Validation complete. Token usage is reported after live OpenAI calls when the API returns usage.")
    print("Reasoning does not bypass quality checks, sanity checks, or publishing gates.")


def _cost_available(router: ModelRouter, selection: object) -> bool:
    return router.estimate_cost(selection, 1000, 1000) is not None  # type: ignore[arg-type]


def _model_warnings(settings: object) -> list[str]:
    warnings: list[str] = []
    for label, model in {
        "OPENAI_LIGHT_MODEL": settings.openai_light_model,
        "OPENAI_STANDARD_MODEL": settings.openai_standard_model,
        "OPENAI_PREMIUM_MODEL": settings.openai_premium_model,
    }.items():
        if not str(model).strip():
            warnings.append(f"{label} is empty.")
        if settings.openai_enable_reasoning and not supports_reasoning(str(model)):
            warnings.append(f"{label}={model} does not appear to support reasoning; reasoning params will not be sent.")
    if settings.openai_reasoning_effort.strip().lower() not in {"low", "medium", "high"}:
        warnings.append("OPENAI_REASONING_EFFORT should be one of: low, medium, high. It will default to medium.")
    return warnings


if __name__ == "__main__":
    main()
