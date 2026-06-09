from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.article_schema import ArticleSchema
from app.config import Settings
from app.media.image_placement_planner import ImagePlacementPlanner
from app.opportunities.verticals import VerticalProfile
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask


GENERIC_FORBIDDEN_IMAGE_TERMS = (
    "fake logo",
    "fake certification",
    "guaranteed result",
    "copyrighted style",
    "trademarked style",
    "before and after",
    "misleading claim",
)


@dataclass(slots=True)
class ArticleImageWorkflowResult:
    image_placement_plan: GeneratedContent
    image_prompt: GeneratedContent
    image_generation_result: GeneratedContent
    image_alt_text: GeneratedContent
    image_caption: GeneratedContent
    image_safety_notes: GeneratedContent
    generated_images: GeneratedContent
    approved_images: GeneratedContent
    rejected_images: GeneratedContent


class ArticleImageGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        *,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        active_vertical_profile: VerticalProfile,
        detected_vertical: str,
        safety_context: dict[str, Any] | None = None,
    ) -> ArticleImageWorkflowResult:
        placement_plan = ImagePlacementPlanner(
            max_inline_images=self.settings.effective_ai_image_max_inline_image_placements,
            enable_vertical_rules=self.settings.ai_image_enable_vertical_rules,
            brand_style=self.settings.ai_image_style,
        ).plan(
            article=article,
            request_data=request_data,
            active_vertical_profile=active_vertical_profile,
            detected_vertical=detected_vertical,
            safety_context=safety_context or {},
        )
        if not self.settings.enable_ai_image_generation:
            disabled_prompt = GeneratedContent(
                content_json={
                    "featured_image_prompt": placement_plan.get("featured_image", {}).get("prompt", ""),
                    "inline_image_prompts": [item.get("prompt", "") for item in placement_plan.get("inline_images", [])],
                    "negative_prompt_notes": placement_plan.get("featured_image", {}).get("safety_notes", []),
                    "alt_text": placement_plan.get("featured_image", {}).get("alt_text", ""),
                    "caption": placement_plan.get("featured_image", {}).get("caption", ""),
                    "safety_notes": "AI image generation is disabled. Placement plan was created but no images were generated.",
                },
                provider="image-prompt-generator",
                model=None,
                task_type=ModelTask.IMAGE_PROMPT_GENERATION.value,
            )
            disabled_result = GeneratedContent(
                content_json={
                    "enabled": False,
                    "status": "disabled",
                    "images": [],
                    "requires_human_review": False,
                    "approved_for_publish": False,
                    "reason": "ENABLE_AI_IMAGE_GENERATION=false.",
                },
                provider="ai-image-generation",
                model=self.settings.ai_image_model,
            )
            return ArticleImageWorkflowResult(
                image_placement_plan=GeneratedContent(content_json=placement_plan, provider="image-placement-planner"),
                image_prompt=disabled_prompt,
                image_generation_result=disabled_result,
                image_alt_text=GeneratedContent(content_text="", provider="image-prompt-generator"),
                image_caption=GeneratedContent(content_text="", provider="image-prompt-generator"),
                image_safety_notes=GeneratedContent(content_text="AI image generation is disabled.", provider="image-prompt-generator"),
                generated_images=GeneratedContent(content_json={"images": []}, provider="ai-image-generation"),
                approved_images=GeneratedContent(content_json={"images": []}, provider="ai-image-generation"),
                rejected_images=GeneratedContent(content_json={"images": []}, provider="ai-image-generation"),
            )
        prompt_result = await self._build_image_prompt(content_provider, article, request_data, placement_plan)
        payload = prompt_result.content_json or {}
        safety_notes = str(payload.get("safety_notes") or "")
        image_result = GeneratedContent(
            content_json={
                "enabled": self.settings.enable_ai_image_generation,
                "status": "disabled",
                "images": [],
                "requires_human_review": False,
                "approved_for_publish": False,
                "reason": "ENABLE_AI_IMAGE_GENERATION=false.",
            },
            provider="ai-image-generation",
            model=self.settings.ai_image_model,
        )

        if self.settings.enable_ai_image_generation:
            image_result = await self._generate_planned_images(placement_plan, payload)
        images = (image_result.content_json or {}).get("images", [])
        approved_images = _renderable_images(images)
        rejected_images = [item for item in images if item.get("status") in {"rejected", "blocked_by_image_safety"}]

        return ArticleImageWorkflowResult(
            image_placement_plan=GeneratedContent(content_json=placement_plan, provider="image-placement-planner"),
            image_prompt=prompt_result,
            image_generation_result=image_result,
            image_alt_text=GeneratedContent(content_text=str(payload.get("alt_text") or ""), provider="image-prompt-generator"),
            image_caption=GeneratedContent(content_text=str(payload.get("caption") or ""), provider="image-prompt-generator"),
            image_safety_notes=GeneratedContent(content_text=safety_notes, provider="image-prompt-generator"),
            generated_images=GeneratedContent(content_json={"images": images}, provider="ai-image-generation"),
            approved_images=GeneratedContent(content_json={"images": approved_images}, provider="ai-image-generation"),
            rejected_images=GeneratedContent(content_json={"images": rejected_images}, provider="ai-image-generation"),
        )

    async def _build_image_prompt(
        self,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        placement_plan: dict[str, Any],
    ) -> GeneratedContent:
        featured = placement_plan.get("featured_image", {})
        payload = {
            "featured_image_prompt": featured.get("prompt", ""),
            "inline_image_prompts": [item.get("prompt", "") for item in placement_plan.get("inline_images", [])],
            "negative_prompt_notes": featured.get("safety_notes", []),
            "alt_text": featured.get("alt_text", ""),
            "caption": featured.get("caption", ""),
            "safety_notes": " ".join(str(item) for item in featured.get("safety_notes", [])),
            "placement_plan": placement_plan,
        }
        return GeneratedContent(
            content_json=_normalize_image_prompt_payload(payload, self.settings.ai_image_style) | {"placement_plan": placement_plan},
            provider="image-placement-planner",
            model=None,
            task_type=ModelTask.IMAGE_PROMPT_GENERATION.value,
        )

    async def _generate_planned_images(self, placement_plan: dict[str, Any], payload: dict[str, Any]) -> GeneratedContent:
        planned_images = []
        if self.settings.ai_image_generate_featured and placement_plan.get("featured_image", {}).get("recommended"):
            planned_images.append({"type": "featured", **placement_plan["featured_image"]})
        if self.settings.effective_ai_image_generate_inline_images:
            planned_images.extend(
                {"type": "inline", **item}
                for item in placement_plan.get("inline_images", [])[
                    : self.settings.effective_ai_image_max_inline_image_placements
                ]
            )
        planned_images = planned_images[: self.settings.effective_ai_image_max_images]
        if not planned_images:
            return GeneratedContent(
                content_json={
                    "enabled": True,
                    "status": "no_images_planned",
                    "images": [],
                    "requires_human_review": False,
                    "approved_for_publish": False,
                    "placement_plan": placement_plan,
                },
                provider="ai-image-generation",
                model=self.settings.ai_image_model,
            )

        client = AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.openai_request_timeout_seconds)
        output_dir = Path(self.settings.ai_image_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        images = []
        raw_responses = []
        for index, planned in enumerate(planned_images, start=1):
            prompt = str(planned.get("prompt") or "").strip()
            safety = _image_prompt_safety(prompt, planned, placement_plan)
            if not safety["passed"]:
                images.append(
                    {
                        "type": planned.get("type", "inline"),
                        "status": "blocked_by_image_safety",
                        "placement": planned.get("placement", ""),
                        "section_heading": planned.get("section_heading", ""),
                        "image_type": planned.get("image_type", ""),
                        "url": "",
                        "local_path": "",
                        "alt_text": planned.get("alt_text") or "",
                        "caption": planned.get("caption") or "",
                        "approved_for_publish": False,
                        "safety": safety,
                    }
                )
                continue
            response = await client.images.generate(
                model=self.settings.ai_image_model,
                prompt=prompt,
                n=self.settings.effective_ai_image_variants_per_placement,
                size="1536x1024",
            )
            raw_responses.append(response.model_dump() if hasattr(response, "model_dump") else None)
            for item in response.data or []:
                local_path = ""
                image_url = getattr(item, "url", None)
                b64_json = getattr(item, "b64_json", None)
                if b64_json:
                    local_path = str(output_dir / f"generated-{planned.get('type', 'image')}-{index}.png")
                    Path(local_path).write_bytes(base64.b64decode(b64_json))
                    image_url = image_url or _local_generated_image_url(local_path)
                images.append(
                    {
                        "type": planned.get("type", "inline"),
                        "status": "generated",
                        "placement": planned.get("placement", ""),
                        "section_heading": planned.get("section_heading", ""),
                        "image_type": planned.get("image_type", ""),
                        "prompt": prompt,
                        "url": image_url,
                        "local_path": local_path,
                        "alt_text": planned.get("alt_text") or payload.get("alt_text") or "",
                        "caption": planned.get("caption") or payload.get("caption") or "",
                        "approved_for_publish": True,
                        "safety": safety,
                    }
                )
        renderable_images = _renderable_images(images)
        return GeneratedContent(
            content_json={
                "enabled": True,
                "status": "generated" if images else "not_generated",
                "images": images,
                "requires_human_review": False,
                "approved_for_publish": bool(renderable_images),
                "placement_plan": placement_plan,
                "model": self.settings.ai_image_model,
                "max_images": self.settings.effective_ai_image_max_images,
            },
            provider="ai-image-generation",
            model=self.settings.ai_image_model,
            raw_response={"responses": raw_responses},
        )

    async def _generate_featured_image(self, payload: dict[str, Any]) -> GeneratedContent:
        prompt = str(payload.get("featured_image_prompt") or "").strip()
        safety = _image_prompt_safety(prompt, payload, {})
        if not safety["passed"]:
            return GeneratedContent(
                content_json={
                    "enabled": True,
                    "status": "blocked_by_image_safety",
                    "images": [],
                    "requires_human_review": False,
                    "approved_for_publish": False,
                    "safety": safety,
                },
                provider="ai-image-generation",
                model=self.settings.ai_image_model,
            )

        client = AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.openai_request_timeout_seconds)
        response = await client.images.generate(
            model=self.settings.ai_image_model,
            prompt=prompt,
            n=self.settings.effective_ai_image_variants_per_placement,
            size="1536x1024",
        )
        output_dir = Path(self.settings.ai_image_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        images = []
        for index, item in enumerate(response.data or [], start=1):
            local_path = ""
            image_url = getattr(item, "url", None)
            b64_json = getattr(item, "b64_json", None)
            if b64_json:
                local_path = str(output_dir / f"generated-featured-{index}.png")
                Path(local_path).write_bytes(base64.b64decode(b64_json))
                image_url = image_url or _local_generated_image_url(local_path)
            images.append(
                {
                    "type": "featured",
                    "url": image_url,
                    "local_path": local_path,
                    "alt_text": payload.get("alt_text") or "",
                    "caption": payload.get("caption") or "",
                    "approved_for_publish": True,
                }
            )
        return GeneratedContent(
            content_json={
                "enabled": True,
                "status": "generated",
                "images": images,
                "requires_human_review": False,
                "approved_for_publish": bool(_renderable_images(images)),
                "safety": safety,
                "model": self.settings.ai_image_model,
            },
            provider="ai-image-generation",
            model=self.settings.ai_image_model,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )


def _normalize_image_prompt_payload(payload: dict[str, Any], style: str) -> dict[str, Any]:
    featured = str(payload.get("featured_image_prompt") or "").strip()
    if not featured:
        featured = (
            f"Create a {style} brand-safe editorial visual for the article topic, "
            "grounded in product or concept context, with no misleading claims, fake logos, fake certifications, or text overlay."
        )
    inline = payload.get("inline_image_prompts") if isinstance(payload.get("inline_image_prompts"), list) else []
    negatives = payload.get("negative_prompt_notes") if isinstance(payload.get("negative_prompt_notes"), list) else []
    return {
        "featured_image_prompt": featured,
        "inline_image_prompts": [str(item) for item in inline[:3] if str(item).strip()],
        "negative_prompt_notes": [str(item) for item in negatives if str(item).strip()],
        "alt_text": str(payload.get("alt_text") or "Editorial visual for the article."),
        "caption": str(payload.get("caption") or "Editorial visual generated for manual review."),
        "safety_notes": str(payload.get("safety_notes") or "Avoids misleading visual claims, fake branding, and unsupported outcomes."),
    }


def _renderable_images(images: list[Any]) -> list[dict[str, Any]]:
    return [
        image
        for image in images
        if isinstance(image, dict)
        and image.get("status") == "generated"
        and (image.get("url") or image.get("local_path"))
    ]


def _image_prompt_safety(prompt: str, payload: dict[str, Any], placement_plan: dict[str, Any]) -> dict[str, Any]:
    haystack = " ".join(
        [
            _affirmative_prompt_text(prompt),
            str(payload.get("caption") or ""),
        ]
    ).lower()
    unsafe = placement_plan.get("vertical_rules", {}).get("unsafe_visual_concepts", [])
    generic_unsafe = placement_plan.get("generic_rules", {}).get("unsafe_visual_concepts", [])
    blocked_terms = list(dict.fromkeys([*GENERIC_FORBIDDEN_IMAGE_TERMS, *unsafe, *generic_unsafe]))
    blocked = [term for term in blocked_terms if term and term.lower() in haystack]
    return {
        "passed": not blocked,
        "blocked_terms": blocked,
        "rules": placement_plan.get("featured_image", {}).get("safety_notes")
        or placement_plan.get("generic_rules", {}).get("image_avoid_rules", [])
        or ["Avoid misleading, unsafe, or unsupported visual claims."],
    }


def _affirmative_prompt_text(prompt: str) -> str:
    """Return the requested visual subject without trailing negative instructions."""
    lowered = prompt.lower()
    cut_points = [
        index
        for marker in (" avoid:", " negative prompt:", " do not include:")
        if (index := lowered.find(marker)) >= 0
    ]
    if not cut_points:
        return prompt
    return prompt[: min(cut_points)]


def _local_generated_image_url(local_path: str) -> str:
    filename = Path(local_path).name
    return f"/generated-images/{filename}" if filename else ""
