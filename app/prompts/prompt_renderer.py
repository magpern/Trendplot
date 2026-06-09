import re
from dataclasses import dataclass, field
from typing import Any


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class PromptRenderError(ValueError):
    pass


class PromptText(str):
    @property
    def prompt_metadata(self) -> dict[str, Any]:
        return getattr(self, "_prompt_metadata", {})

    @classmethod
    def create(cls, value: str, metadata: dict[str, Any]) -> "PromptText":
        item = cls(value)
        item._prompt_metadata = metadata
        return item


@dataclass(slots=True)
class PromptTemplate:
    id: str
    version: int
    description: str
    model_task: str
    required_variables: list[str]
    template: str
    output_contract: str = ""
    safety_rules: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RenderedPrompt:
    prompt_id: str
    version: int
    model_task: str
    text: PromptText

    def metadata(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_version": self.version,
            "model_task": self.model_task,
        }


class PromptRenderer:
    def render(
        self,
        prompt_template: PromptTemplate,
        variables: dict[str, Any],
        strict: bool = True,
    ) -> RenderedPrompt:
        missing = [name for name in prompt_template.required_variables if name not in variables]
        if missing:
            raise PromptRenderError(
                f"Missing required variables for prompt '{prompt_template.id}': {', '.join(missing)}"
            )

        placeholders = sorted(set(PLACEHOLDER_PATTERN.findall(prompt_template.template)))
        unlisted = [name for name in placeholders if name not in prompt_template.required_variables]
        if strict and unlisted:
            raise PromptRenderError(
                f"Prompt '{prompt_template.id}' uses placeholders not listed in required_variables: {', '.join(unlisted)}"
            )

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise PromptRenderError(f"Missing variable '{name}' for prompt '{prompt_template.id}'.")
            value = variables[name]
            return "" if value is None else str(value)

        rendered = PLACEHOLDER_PATTERN.sub(replace, prompt_template.template).strip()
        if prompt_template.output_contract.strip():
            rendered = f"{rendered}\n\nOutput contract:\n{prompt_template.output_contract.strip()}"
        if prompt_template.safety_rules:
            rules = "\n".join(f"- {rule}" for rule in prompt_template.safety_rules)
            rendered = f"{rendered}\n\nSafety rules:\n{rules}"

        metadata = {
            "prompt_id": prompt_template.id,
            "prompt_version": prompt_template.version,
            "model_task": prompt_template.model_task,
        }
        return RenderedPrompt(
            prompt_id=prompt_template.id,
            version=prompt_template.version,
            model_task=prompt_template.model_task,
            text=PromptText.create(rendered, metadata),
        )
