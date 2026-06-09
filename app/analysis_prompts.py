import json
from typing import Any

from app.analysis_digest import build_website_analysis_digest
from app.prompts import render_prompt


def build_website_analysis_prompt(
    website: dict[str, Any],
    competitors: list[dict[str, Any]],
    vertical_context: dict[str, Any] | None = None,
    *,
    max_digest_pages: int = 40,
    max_competitor_pages: int = 6,
) -> str:
    digest = build_website_analysis_digest(
        website,
        competitors,
        vertical_context=vertical_context,
        max_pages_per_site=max_digest_pages,
        max_competitor_pages=max_competitor_pages,
    )
    return render_prompt(
        "website_analysis",
        {
            "website_data_json": json.dumps(digest, ensure_ascii=False, separators=(",", ":")),
        },
    )
