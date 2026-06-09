from enum import StrEnum


class ArticleRenderSurface(StrEnum):
    """Controls which article fields appear in rendered HTML / markdown exports."""

    EDITORIAL_FULL = "editorial_full"
    PUBLISHABLE = "publishable"
