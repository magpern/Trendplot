from __future__ import annotations

from dataclasses import dataclass

from app.article_schema import ArticleSchema
from app.rendering.article_renderer import RenderedArticle, render_article
from app.rendering.render_surface import ArticleRenderSurface


@dataclass(slots=True)
class DualRenderedArticle:
    publishable: RenderedArticle
    editorial: RenderedArticle


def render_dual_surfaces(
    article: ArticleSchema,
    *,
    youtube_video: dict | None = None,
    generated_images: dict | None = None,
) -> DualRenderedArticle:
    return DualRenderedArticle(
        publishable=render_article(
            article,
            youtube_video=youtube_video,
            generated_images=generated_images,
            surface=ArticleRenderSurface.PUBLISHABLE,
        ),
        editorial=render_article(
            article,
            youtube_video=youtube_video,
            generated_images=generated_images,
            surface=ArticleRenderSurface.EDITORIAL_FULL,
        ),
    )
