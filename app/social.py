from app.prompts import build_social_prompt
from app.providers.base import ContentGenerationProvider, GeneratedContent


class SocialContentService:
    def __init__(self, content_provider: ContentGenerationProvider) -> None:
        self.content_provider = content_provider

    async def generate_post(
        self,
        platform: str,
        article_markdown: str,
        title: str,
        product_name: str,
        product_url: str,
    ) -> tuple[str, GeneratedContent]:
        prompt = build_social_prompt(
            platform=platform,
            article_markdown=article_markdown,
            title=title,
            product_name=product_name,
            product_url=product_url,
        )
        result = await self.content_provider.generate_social_post(platform, prompt)
        return prompt, result
