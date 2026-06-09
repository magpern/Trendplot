"""Re-render a job's structured article with publishable vs editorial surfaces."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from app.article_schema import normalize_article
from app.rendering.article_renderer import render_article
from app.rendering.render_surface import ArticleRenderSurface

CHECKS = (
    "Research Metadata",
    "Research Insights",
    "Research Notes To Verify",
    "References to verify",
    "Evidence gap",
)


def main(job_id: str) -> int:
    db = Path("data/seo_content_worker.db")
    if not db.exists():
        print("Database not found:", db)
        return 1
    conn = sqlite3.connect(db)
    row = conn.execute(
        """
        SELECT content_json FROM artifacts
        WHERE job_id = ? AND artifact_type = 'structured_article_json'
        ORDER BY id DESC LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    if not row:
        print("No structured_article_json for job", job_id)
        return 1
    article = normalize_article(json.loads(row[0]), defaults={})
    before = render_article(article, surface=ArticleRenderSurface.EDITORIAL_FULL).html
    after = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html
    print("Title:", article.title)
    print("\n--- Before (editorial_full) ---")
    for label in CHECKS:
        print(f"  {label}: {label in before}")
    print("\n--- After (publishable) ---")
    for label in CHECKS:
        print(f"  {label}: {label in after}")
    print("  Limitations and Safety Notes:", "Limitations and Safety Notes" in after)
    print("  FAQ:", "FAQ" in after)
    print("  Product reference:", "Product reference" in after)
    return 0


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "2509c670-0e5e-4284-a3b4-fb271be226b1"
    raise SystemExit(main(job))
