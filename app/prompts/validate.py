from app.prompts.prompt_registry import PromptRegistry
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    registry = PromptRegistry(
        template_dir=settings.prompt_template_dir,
        strict_mode=settings.prompt_strict_mode,
        allow_fallback=False,
    )
    templates = registry.load()
    errors: list[str] = []
    for prompt_id, prompt in sorted(templates.items()):
        try:
            registry.render(prompt_id, {name: f"sample_{name}" for name in prompt.required_variables})
        except Exception as exc:  # pragma: no cover - CLI output path
            errors.append(f"{prompt_id}: {exc}")
        if not prompt.output_contract.strip() and prompt_id not in {"social_posts"}:
            errors.append(f"{prompt_id}: output_contract is required.")

    if errors:
        print("Prompt validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"Prompt validation passed: {len(templates)} templates.")


if __name__ == "__main__":
    main()
