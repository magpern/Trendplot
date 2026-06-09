from __future__ import annotations

from typing import Any

from app.config import Settings
from app.intelligence.brave_search import BraveSearchProvider
from app.intelligence.duckduckgo_search import DuckDuckGoSearchProvider


def build_web_search_provider(settings: Settings) -> Any | None:
    provider = str(settings.web_search_provider or "").strip().lower()
    if provider == "brave":
        return BraveSearchProvider(settings)
    if provider == "duckduckgo":
        return DuckDuckGoSearchProvider(settings)
    return None
