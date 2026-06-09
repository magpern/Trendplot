from app.providers.base import GeneratedContent, PublishPolicy


class PlaceholderSocialPublisher:
    def __init__(self, platform: str) -> None:
        self.platform = platform
        self.provider_name = f"{platform.lower()}-placeholder"

    async def publish(self, content: str, policy: PublishPolicy) -> GeneratedContent:
        return GeneratedContent(
            content_json={
                "platform": self.platform,
                "status": "not_published",
                "reason": "Publisher is a placeholder for future implementation.",
                "policy": policy.mode,
                "content": content,
            },
            provider=self.provider_name,
        )
