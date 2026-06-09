"""One-off trim for phase 2 cleanup. Run from repo root."""
from __future__ import annotations

import re
from pathlib import Path

path = Path("app/autopilot/service.py")
text = path.read_text(encoding="utf-8")

blocks = [
    (r"    async def _removed_analyze_workspace_full\(", r"    async def load_saved_website_crawl\("),
    (r"    async def rerun_competitor_discovery\(", r"    async def _persist_ideation_recommendations\("),
    (r"    async def discover_trends\(", r"    async def refresh_niche_profile\("),
    (r"    async def refresh_opportunity_intelligence\(", r"    async def refresh_publishing_memory\("),
    (r"    async def refresh_publishing_memory\(", r"    async def coverage_summary\("),
    (r"    async def coverage_summary\(", r"    async def connector_capabilities\("),
    (r"    async def _refresh_market_intelligence\(", r"    async def _run_ai_opportunity_ideation\("),
    (r"    async def _run_ai_editorial_strategist\(", r"    async def _run_editorial_generator\("),
    (r"    async def _run_editorial_generator\(", r"    def _market_inputs_for_oi\("),
    (r"    def _market_inputs_for_oi\(", r"    async def _workspace\("),
]
for start_pat, end_pat in blocks:
    m1 = re.search(start_pat, text)
    m2 = re.search(end_pat, text)
    if not m1 or not m2 or m2.start() <= m1.start():
        raise SystemExit(f"block not found: {start_pat!r}")
    text = text[: m1.start()] + text[m2.start() :]

# rerun_recommendations: keep only ideation path
text = re.sub(
    r"(    async def rerun_recommendations\([\s\S]*?)        if self\.settings\.is_ai_ideation_only_mode:\n"
    r"            return await self\._rerun_ideation_recommendations\(workspace_id, progress_callback=progress_callback\)\n\n"
    r"        workspace = await self\._workspace[\s\S]*?"
    r"        return \{\n            \"market_intelligence\": market_intelligence,\n            \"opportunity_intelligence\": opportunity_intelligence,\n        \}\n",
    r"\1        return await self._rerun_ideation_recommendations(workspace_id, progress_callback=progress_callback)\n",
    text,
    count=1,
)

path.write_text(text, encoding="utf-8")
print(f"trimmed {path} -> {len(text.splitlines())} lines")
