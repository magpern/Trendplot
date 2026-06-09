from __future__ import annotations

import re
from typing import Any

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "to",
        "in",
        "on",
        "of",
        "why",
        "how",
        "what",
        "are",
        "is",
        "often",
        "discussed",
        "together",
        "article",
        "research",
    }
)


def find_similar_items(
    headline: str,
    *,
    recommendations: list[dict[str, Any]],
    articles: list[dict[str, Any]] | None = None,
    threshold: float = 0.55,
) -> list[dict[str, str]]:
    target_tokens = _token_set(headline)
    if not target_tokens:
        return []

    matches: list[dict[str, str]] = []
    for item in recommendations:
        candidate = str(item.get("title") or item.get("topic") or "").strip()
        if not candidate:
            continue
        score = _similarity(target_tokens, _token_set(candidate))
        if score >= threshold:
            matches.append(
                {
                    "type": "recommendation",
                    "id": str(item.get("id") or ""),
                    "title": candidate,
                    "score": f"{score:.2f}",
                }
            )

    for item in articles or []:
        candidate = str(item.get("title") or "").strip()
        if not candidate:
            continue
        score = _similarity(target_tokens, _token_set(candidate))
        if score >= threshold:
            matches.append(
                {
                    "type": "article",
                    "id": str(item.get("id") or item.get("job_id") or ""),
                    "title": candidate,
                    "score": f"{score:.2f}",
                }
            )
    return matches


def _token_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
