from __future__ import annotations

from pathlib import Path


def test_env_example_and_env_include_ideation_keys():
    root = Path(__file__).resolve().parents[1]
    example = (root / ".env.example").read_text(encoding="utf-8")
    env = (root / ".env").read_text(encoding="utf-8")
    required = [
        "AI_OPPORTUNITY_IDEATION_ENABLED",
        "AI_OPPORTUNITY_IDEATION_MIN_IDEAS",
        "AI_OPPORTUNITY_IDEATION_MAX_IDEAS",
        "NICHE_INTELLIGENCE_ENABLED",
        "SITEMAP_DISCOVERY_ENABLED",
    ]
    for key in required:
        assert key in example, f"missing from .env.example: {key}"
        assert key in env, f"missing from .env: {key}"
    assert "AI_OPPORTUNITY_IDEATION_SHORT_CIRCUIT" not in example
    assert "MARKET_INTELLIGENCE_ENABLED" not in example
