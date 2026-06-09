from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.config import Settings
from app.intelligence.brave_search import BraveSearchProvider
from app.intelligence.duckduckgo_search import DuckDuckGoSearchProvider
from app.intelligence.web_search_factory import build_web_search_provider


DDGS_PAYLOAD = [
    {
        "title": "Rival One",
        "href": "https://rival-one.com/about",
        "body": "A competitor site",
    },
    {
        "title": "Rival Two",
        "href": "https://www.rival-two.com",
        "body": "Another competitor",
    },
]

BRAVE_PAYLOAD = {
    "web": {
        "results": [
            {
                "title": "Rival One",
                "url": "https://rival-one.com/about",
                "description": "A competitor site",
            },
            {
                "title": "Rival Two",
                "url": "https://www.rival-two.com",
                "description": "Another competitor",
            },
        ]
    }
}


def test_build_web_search_provider_returns_brave_instance() -> None:
    provider = build_web_search_provider(Settings(WEB_SEARCH_PROVIDER="brave"))
    assert isinstance(provider, BraveSearchProvider)


def test_build_web_search_provider_returns_duckduckgo_instance() -> None:
    provider = build_web_search_provider(Settings(WEB_SEARCH_PROVIDER="duckduckgo"))
    assert isinstance(provider, DuckDuckGoSearchProvider)
    assert provider.is_configured() is True


def test_build_web_search_provider_returns_none_for_unknown() -> None:
    assert build_web_search_provider(Settings(WEB_SEARCH_PROVIDER="serper")) is None


def test_duckduckgo_provider_normalizes_results() -> None:
    provider = DuckDuckGoSearchProvider(Settings(WEB_SEARCH_PROVIDER="duckduckgo"))

    with patch.object(provider, "_search_sync", return_value=DDGS_PAYLOAD):
        results = asyncio.run(provider.search_web("peptide competitors", max_results=5))

    assert len(results) == 2
    assert results[0]["url"] == "https://rival-one.com/about"
    assert results[0]["domain"] == "rival-one.com"
    assert results[0]["provider"] == "duckduckgo"
    assert results[0]["status"] == "ok"


def test_duckduckgo_provider_fail_open_on_exception() -> None:
    provider = DuckDuckGoSearchProvider(Settings(WEB_SEARCH_PROVIDER="duckduckgo"))

    with patch.object(provider, "_search_sync", side_effect=RuntimeError("blocked")):
        results = asyncio.run(provider.search_web("example competitors"))

    assert results == []


def test_duckduckgo_provider_fail_open_on_timeout() -> None:
    import time

    provider = DuckDuckGoSearchProvider(Settings(WEB_SEARCH_PROVIDER="duckduckgo", DUCKDUCKGO_SEARCH_TIMEOUT_SECONDS=1))

    def slow_search(*_args: object, **_kwargs: object) -> list[dict]:
        time.sleep(5)
        return []

    with patch.object(provider, "_search_sync", side_effect=slow_search):
        results = asyncio.run(provider.search_web("example competitors"))

    assert results == []


def test_missing_api_key_is_not_configured() -> None:
    provider = BraveSearchProvider(Settings(WEB_SEARCH_PROVIDER="brave", BRAVE_SEARCH_API_KEY=""))
    assert provider.is_configured() is False
    assert asyncio.run(provider.search_web("example competitors")) == []


def test_configured_provider_returns_normalized_results() -> None:
    provider = BraveSearchProvider(Settings(WEB_SEARCH_PROVIDER="brave", BRAVE_SEARCH_API_KEY="test-key"))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = BRAVE_PAYLOAD

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.intelligence.brave_search.httpx.AsyncClient", return_value=mock_client):
        results = asyncio.run(provider.search_web("peptide competitors", max_results=5))

    assert len(results) == 2
    assert results[0]["url"] == "https://rival-one.com/about"
    assert results[0]["domain"] == "rival-one.com"
    assert results[0]["provider"] == "brave-search"
    assert results[0]["status"] == "ok"


def test_provider_timeout_fail_open() -> None:
    provider = BraveSearchProvider(Settings(WEB_SEARCH_PROVIDER="brave", BRAVE_SEARCH_API_KEY="test-key"))
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.intelligence.brave_search.httpx.AsyncClient", return_value=mock_client):
        results = asyncio.run(provider.search_web("example competitors"))

    assert results == []


def test_provider_rate_limit_fail_open() -> None:
    provider = BraveSearchProvider(Settings(WEB_SEARCH_PROVIDER="brave", BRAVE_SEARCH_API_KEY="test-key"))
    mock_response = MagicMock()
    mock_response.status_code = 429

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.intelligence.brave_search.httpx.AsyncClient", return_value=mock_client):
        results = asyncio.run(provider.search_web("example competitors"))

    assert results == []


def test_provider_http_error_fail_open() -> None:
    provider = BraveSearchProvider(Settings(WEB_SEARCH_PROVIDER="brave", BRAVE_SEARCH_API_KEY="test-key"))
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error",
        request=MagicMock(),
        response=mock_response,
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.intelligence.brave_search.httpx.AsyncClient", return_value=mock_client):
        results = asyncio.run(provider.search_web("example competitors"))

    assert results == []
