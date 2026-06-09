import json
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.providers.base import GeneratedContent, ProviderUsage
from app.providers.model_router import ModelRouter, ModelTask, uses_max_completion_tokens


class OpenAIContentGenerationProvider:
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.model_router = ModelRouter(settings)
        self.settings = settings
        self.model = settings.openai_standard_model
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_request_timeout_seconds,
        )

    async def generate_article(
        self,
        prompt: str,
        task_type: str | ModelTask | None = None,
    ) -> GeneratedContent:
        result = await self._generate_text(
            system_message=(
                "You are a senior SEO content strategist and scientific editor. "
                "Return strict JSON only. Put verification material only in designated editorial fields "
                "(references_to_verify, study_cards, research_insights, research_metadata_panel), not in public sections."
            ),
            prompt=prompt,
            response_format={"type": "json_object"},
            task_type=task_type or ModelTask.ARTICLE_GENERATION,
        )
        if result.content_text:
            try:
                result.content_json = json.loads(result.content_text)
            except json.JSONDecodeError:
                result.content_json = {"article_markdown": result.content_text}
        return result

    async def generate_article_markdown(self, prompt: str) -> GeneratedContent:
        article = await self.generate_article(prompt, task_type=ModelTask.ARTICLE_GENERATION)
        content_json = article.content_json or {}
        article.content_text = str(content_json.get("article_markdown") or article.content_text or "")
        return article

    async def generate_seo_metadata(self, prompt: str) -> GeneratedContent:
        result = await self._generate_text(
            system_message="You create concise SEO metadata and return strict JSON only.",
            prompt=prompt,
            response_format={"type": "json_object"},
            task_type=ModelTask.SEO_METADATA,
        )
        if result.content_text:
            try:
                result.content_json = json.loads(result.content_text)
            except json.JSONDecodeError:
                result.content_json = {"raw": result.content_text}
        return result

    async def generate_social_post(self, platform: str, prompt: str) -> GeneratedContent:
        return await self._generate_text(
            system_message=f"You write high-performing, factual social posts for {platform}.",
            prompt=prompt,
            task_type=ModelTask.SOCIAL_POST_GENERATION,
        )

    async def generate_website_analysis(self, prompt: str) -> GeneratedContent:
        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_request_timeout_seconds,
            max_retries=max(0, int(self.settings.openai_website_analysis_max_retries)),
        )
        result = await self._generate_text(
            system_message=(
                "You are an SEO strategist. Analyze lightweight website signals and "
                "return strict JSON only."
            ),
            prompt=prompt,
            response_format={"type": "json_object"},
            task_type=ModelTask.WEBSITE_ANALYSIS,
            client=client,
        )
        if result.content_text:
            try:
                result.content_json = json.loads(result.content_text)
            except json.JSONDecodeError:
                result.content_json = {
                    "summary": "",
                    "suggestions": [],
                    "raw": result.content_text,
                }
        return result

    async def evaluate_youtube_candidates(self, prompt: str) -> GeneratedContent:
        result = await self._generate_text(
            system_message=(
                "You evaluate YouTube search results for article enrichment relevance. "
                "Return strict JSON only."
            ),
            prompt=prompt,
            response_format={"type": "json_object"},
            task_type=ModelTask.YOUTUBE_EVALUATION,
        )
        if result.content_text:
            try:
                result.content_json = json.loads(result.content_text)
            except json.JSONDecodeError:
                result.content_json = {
                    "selected_video_id": "",
                    "score": 0,
                    "reason": "",
                    "reject_reason": "Model returned invalid JSON.",
                    "raw": result.content_text,
                }
        return result

    async def _generate_text(
        self,
        system_message: str,
        prompt: str,
        response_format: dict[str, str] | None = None,
        task_type: ModelTask | str = ModelTask.ARTICLE_GENERATION,
        *,
        client: AsyncOpenAI | None = None,
    ) -> GeneratedContent:
        selection = self.model_router.select(task_type)
        kwargs: dict[str, Any] = {
            "model": selection.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        }
        if uses_max_completion_tokens(selection.model):
            kwargs["max_completion_tokens"] = selection.max_output_tokens
        else:
            kwargs["max_tokens"] = selection.max_output_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if selection.reasoning_enabled and selection.reasoning_effort:
            kwargs["reasoning_effort"] = selection.reasoning_effort

        active_client = client or self.client
        response = await active_client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        usage = response.usage
        token_input = usage.prompt_tokens if usage else None
        token_output = usage.completion_tokens if usage else None

        return GeneratedContent(
            content_text=content,
            provider=self.provider_name,
            model=selection.model,
            task_type=selection.task_type.value,
            usage=ProviderUsage(
                token_input=token_input,
                token_output=token_output,
                estimated_cost=self.model_router.estimate_cost(selection, token_input, token_output),
            ),
            raw_response={
                "request": {
                    "model": selection.model,
                    "task_type": selection.task_type.value,
                    "tier": selection.tier.value,
                    "reasoning_supported": selection.reasoning_supported,
                    "reasoning_enabled": selection.reasoning_enabled,
                    "reasoning_effort": selection.reasoning_effort,
                    "reasoning_source": selection.reasoning_source,
                    "max_output_tokens": selection.max_output_tokens,
                    "max_token_parameter": "max_completion_tokens"
                    if uses_max_completion_tokens(selection.model)
                    else "max_tokens",
                    "response_format": response_format,
                },
                "response": response.model_dump(),
            },
            reasoning_enabled=selection.reasoning_enabled,
            reasoning_effort=selection.reasoning_effort,
            reasoning_supported=selection.reasoning_supported,
            reasoning_source=selection.reasoning_source,
        )
