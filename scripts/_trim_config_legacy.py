"""Remove legacy Settings fields from config.py (phase 2)."""
from pathlib import Path

path = Path("app/config.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
remove_prefixes = (
    "    competitor_max_pages:",
    "    trend_refresh_interval_days:",
    "    enable_trend_research:",
    "    opportunity_intelligence_enabled:",
    "    demand_",
    "    search_console_",
    "    market_",
    "    competitor_discovery_",
    "    competitor_total_",
    "    editorial_generator_",
    "    entity_relevance_",
    "    ai_editorial_strategist_",
    "    ai_recommendation_review_",
    "    recommendation_min_",
    "    recommendation_max_",
    "    trend_intelligence_",
    "    trend_discovery_",
    "    trend_provider_",
    "    publishing_memory_enabled:",
    "    coverage_refresh_threshold_days:",
    "    coverage_saturation_threshold:",
    "    cannibalization_risk_threshold:",
    "    website_analysis_max_seed_opportunities:",
)
remove_props = (
    "    def effective_entity_relevance_model",
    "    def effective_ai_editorial_strategist_model",
    "    def effective_ai_recommendation_review_model",
)
out: list[str] = []
skip = False
for line in lines:
    if any(line.startswith(p) for p in remove_prefixes):
        skip = True
        continue
    if skip:
        if line.startswith("    ") and not line.startswith("    #") and ": " in line and "Field(" in line:
            continue
        if line.strip() == "" or line.startswith("    #"):
            skip = False
        elif not line.startswith("    "):
            skip = False
        else:
            continue
    if any(line.startswith(p) for p in remove_props):
        skip = True
        continue
    out.append(line)
path.write_text("".join(out), encoding="utf-8")
print("trimmed config.py")
