from typing import Any

from app.article_schema import ArticleSchema, article_to_markdown
from app.rendering.render_surface import ArticleRenderSurface
from app.rendering.youtube_embed import youtube_watch_url
from app.rules.compliance_rules import default_publisher_name, GENERIC_PUBLISHER_FALLBACK


def build_schema_jsonld(
    article: ArticleSchema,
    request_data: dict[str, Any],
    youtube_video: dict[str, Any] | None = None,
    category: dict[str, Any] | None = None,
    organization_name: str | None = None,
) -> list[dict[str, Any]]:
    publisher = str(organization_name or "").strip() or default_publisher_name(
        product_name=str(request_data.get("product_name") or ""),
        product_url=str(request_data.get("product_url") or ""),
        workspace_name=str(request_data.get("workspace_name") or request_data.get("site_name") or ""),
        site_name=str(request_data.get("site_name") or ""),
    )
    if not publisher:
        publisher = GENERIC_PUBLISHER_FALLBACK
    schemas: list[dict[str, Any]] = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": article.title,
            "description": article.meta_description or article.excerpt,
            "keywords": [article.primary_keyword, *article.secondary_keywords],
            "articleBody": article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE)[:12000],
            "author": {"@type": "Organization", "name": publisher},
            "publisher": {"@type": "Organization", "name": publisher},
        }
    ]
    if article.faq:
        schemas.append(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item.question,
                        "acceptedAnswer": {"@type": "Answer", "text": item.answer},
                    }
                    for item in article.faq
                    if item.question and item.answer
                ],
            }
        )
    if youtube_video:
        watch_url = youtube_watch_url(youtube_video)
        if watch_url:
            schemas.append(
                {
                    "@context": "https://schema.org",
                    "@type": "VideoObject",
                    "name": youtube_video.get("title") or "Related video",
                    "description": youtube_video.get("selection_reason")
                    or "Related media selected for topical relevance; verify independently.",
                    "thumbnailUrl": youtube_video.get("thumbnail_url"),
                    "embedUrl": youtube_video.get("embed_url"),
                    "url": watch_url,
                    "uploadDate": youtube_video.get("published_at"),
                }
            )
    if category:
        name = category.get("name") or category.get("slug")
        if name:
            schemas.append(
                {
                    "@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Home", "item": request_data.get("site_url") or "/"},
                        {"@type": "ListItem", "position": 2, "name": name},
                    ],
                }
            )
    schemas.append({"@context": "https://schema.org", "@type": "Organization", "name": publisher})
    return [schema for schema in schemas if schema]
