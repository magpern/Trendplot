from pathlib import Path
from typing import Any

import yaml

from app.prompts.prompt_renderer import PromptTemplate


class PromptTemplateError(ValueError):
    pass


REQUIRED_FIELDS = {
    "id",
    "version",
    "description",
    "model_task",
    "required_variables",
    "template",
}


class PromptLoader:
    def __init__(self, template_dir: str | Path) -> None:
        self.template_dir = Path(template_dir)

    def load_all(self) -> dict[str, PromptTemplate]:
        if not self.template_dir.exists():
            raise PromptTemplateError(f"Prompt template directory does not exist: {self.template_dir}")

        prompts: dict[str, PromptTemplate] = {}
        for path in sorted(self.template_dir.glob("*.yaml")):
            prompt = self.load(path)
            if prompt.id in prompts:
                raise PromptTemplateError(f"Duplicate prompt id '{prompt.id}' in {path}")
            prompts[prompt.id] = prompt
        if not prompts:
            raise PromptTemplateError(f"No prompt templates found in {self.template_dir}")
        return prompts

    def load(self, path: str | Path) -> PromptTemplate:
        template_path = Path(path)
        try:
            payload = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PromptTemplateError(f"Invalid YAML in {template_path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise PromptTemplateError(f"Prompt template must be a mapping: {template_path}")
        self._validate_payload(payload, template_path)
        return PromptTemplate(
            id=str(payload["id"]),
            version=int(payload["version"]),
            description=str(payload["description"]),
            model_task=str(payload["model_task"]),
            required_variables=[str(item) for item in payload["required_variables"]],
            template=str(payload["template"]),
            output_contract=str(payload.get("output_contract") or ""),
            safety_rules=[str(item) for item in payload.get("safety_rules") or []],
        )

    def _validate_payload(self, payload: dict[str, Any], path: Path) -> None:
        missing = sorted(REQUIRED_FIELDS - set(payload))
        if missing:
            raise PromptTemplateError(f"Prompt template {path} is missing fields: {', '.join(missing)}")
        if not str(payload.get("id") or "").strip():
            raise PromptTemplateError(f"Prompt template {path} has an empty id.")
        if not isinstance(payload.get("version"), int):
            raise PromptTemplateError(f"Prompt template {path} version must be an integer.")
        if not isinstance(payload.get("required_variables"), list):
            raise PromptTemplateError(f"Prompt template {path} required_variables must be a list.")
        if not str(payload.get("template") or "").strip():
            raise PromptTemplateError(f"Prompt template {path} has an empty template.")
        if payload.get("output_contract") is not None and not isinstance(payload.get("output_contract"), str):
            raise PromptTemplateError(f"Prompt template {path} output_contract must be a string.")
        if payload.get("safety_rules") is not None and not isinstance(payload.get("safety_rules"), list):
            raise PromptTemplateError(f"Prompt template {path} safety_rules must be a list.")
