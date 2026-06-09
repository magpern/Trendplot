from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.prompts.prompt_loader import PromptLoader, PromptTemplateError
from app.prompts.prompt_renderer import PromptRenderer, PromptTemplate, RenderedPrompt


class PromptRegistry:
    def __init__(
        self,
        template_dir: str | Path,
        strict_mode: bool = True,
        allow_fallback: bool = False,
    ) -> None:
        self.template_dir = Path(template_dir)
        self.strict_mode = strict_mode
        self.allow_fallback = allow_fallback
        self.renderer = PromptRenderer()
        self._templates: dict[str, PromptTemplate] | None = None

    def load(self) -> dict[str, PromptTemplate]:
        if self._templates is None:
            try:
                self._templates = PromptLoader(self.template_dir).load_all()
            except PromptTemplateError:
                if not self.allow_fallback:
                    raise
                self._templates = {}
        return self._templates

    def get_prompt(self, prompt_id: str) -> PromptTemplate:
        templates = self.load()
        try:
            return templates[prompt_id]
        except KeyError as exc:
            raise PromptTemplateError(f"Prompt template '{prompt_id}' was not found.") from exc

    def render(self, prompt_id: str, variables: dict[str, Any]) -> RenderedPrompt:
        prompt = self.get_prompt(prompt_id)
        return self.renderer.render(prompt, variables, strict=self.strict_mode)


@lru_cache
def get_default_prompt_registry() -> PromptRegistry:
    settings = get_settings()
    return PromptRegistry(
        template_dir=settings.prompt_template_dir,
        strict_mode=settings.prompt_strict_mode,
        allow_fallback=settings.allow_prompt_fallback,
    )
