# Prompt Responsibility Audit

**Date:** 2026-06-02  
**Scope:** Website analysis, site understanding (profile extraction), AI Editorial Strategist, AI Recommendation Reviewer  
**Validation site:** Example Lab (`https://www.example.com/`, workspace `2a71aaf6-cc69-4663-be7f-7b13e50c3722`)

---

## Executive summary

Responsibilities were split so **website analysis classifies the site** and **the editorial strategist generates article ideas** from a compact **Site Strategy Profile**. Website analysis v6 no longer emits article seeds. Strategist v2 consumes profile JSON only (optional coverage gaps / competitor patterns). Reviewer v1 remains a relevance gate with compact profile context.

| Component | Before | After |
|-----------|--------|-------|
| Website analysis | Extraction + 25–75 editorial seeds | Extraction/classification only |
| Strategist input | Crawl digest, inventory dumps, wide site context | Site Strategy Profile (~200–800 chars) |
| Reviewer input | Wide site profile context | Compact profile + recommendation list |

---

## 1. Website analysis (`website_analysis.yaml`)

| Field | Detail |
|-------|--------|
| **Template** | `app/prompts/templates/website_analysis.yaml` |
| **Version** | v5 → **v6** |
| **Model task** | `WEBSITE_ANALYSIS` |
| **Purpose** | Answer: *What kind of site is this?* |

### Inputs

| Input | Description |
|-------|-------------|
| `website_data_json` | Compact crawl digest (`build_website_analysis_digest`) — rollup titles, entities, category/product signals; not full page HTML |

### Outputs (required JSON)

- `business_type`, `primary_niche`, `secondary_niches`
- `known_products`, `known_categories`
- `audiences`, `topical_clusters`
- `content_inventory_summary`, `summary`
- Nested `niche_intelligence`, `product_intelligence`, `competitor_intelligence`
- **Explicitly excluded:** `opportunities`, `suggestions`, `authority_graph`, article titles

Post-processing: `strip_ideation_from_extraction()` clears any model-emitted seeds before OI.

### Token / size measurements

| Metric | Before (v4/v5) | After (v6) |
|--------|----------------|------------|
| Prompt template + instructions | ~2,500–3,500 est. tokens (seed generation, 75–200 opportunity contract) | **~1,037 est. tokens** |
| Crawl digest input (8-page Example Lab fixture) | Full crawl JSON could exceed 50k chars | **~1,792 chars** digest |
| Model output cap | 8,000 tokens (large JSON seeds) | 8,000 tokens (classification JSON only; typical response much smaller) |
| Timeout risk | High (180s+ on seed-heavy runs) | Reduced — extraction-only contract |

Fixture measurement command: `python -c` using `build_website_analysis_prompt()` on Example Lab sample pages (see `tests/test_site_strategy_profile.py`).

### Responsibilities

| | Before | After (recommended) |
|---|--------|---------------------|
| Business type | ✓ | ✓ |
| Niche / vertical | ✓ | ✓ |
| Products / categories | ✓ | ✓ |
| Audiences / clusters | ✓ | ✓ |
| Content inventory summary | ✓ | ✓ |
| Article seeds / opportunities | ✓ (25–75) | **Removed** |
| Editorial planning | ✓ (implicit) | **Removed** |
| SEO recommendations | ✓ (implicit) | **Removed** |

---

## 2. Site understanding / Site Strategy Profile (deterministic + persisted)

| Field | Detail |
|-------|--------|
| **Module** | `app/site_strategy_profile.py` |
| **Purpose** | Persist compact site facts for downstream AI and diagnostics |

### Inputs

- Website analysis JSON (extraction fields)
- Crawl signal inventory (`build_signal_inventory`)
- Content inventory titles (optional)
- Niche profile fallback when profile not yet persisted

### Outputs (example)

```json
{
  "business_type": "ecommerce",
  "primary_niche": "research peptides",
  "secondary_niches": [],
  "known_products": ["BPC-157", "TB-500", "GHK-CU"],
  "known_categories": ["Research Peptides"],
  "audiences": [],
  "topical_clusters": [],
  "existing_articles": [],
  "content_inventory_summary": "..."
}
```

### Persistence

- Artifact: `analysis_intelligence_artifacts.site_strategy_profile`
- `site_understanding.source_json.strategy_profile`
- Analyze UI Diagnostics tab (via `extract_flow_summary` → `summary.site.strategy_profile`)

### Token size

Profile JSON typically **300–900 chars** (~75–225 est. tokens) vs multi-kB crawl dumps.

---

## 3. AI Editorial Strategist (`ai_editorial_strategist.yaml`)

| Field | Detail |
|-------|--------|
| **Template** | `app/prompts/templates/ai_editorial_strategist.yaml` |
| **Version** | v1 → **v2** |
| **Model task** | `CLASSIFICATION` |
| **Purpose** | Generate useful article ideas for this business |

### Inputs

| Input | Before (Mode A legacy) | After (Mode B compact) |
|-------|------------------------|------------------------|
| Site profile block | Full `site_profile`, description, domain | **Removed** |
| Crawl / pages | Via understanding pages in competitor intel | **Removed** |
| Products / categories | From niche profile + inventory dump (60 titles) | `known_products`, `known_categories` (capped) |
| Inventory | `existing_content_summary` (60 titles) | `existing_articles` (40 titles) |
| Competitor data | Up to 20 SEO gap objects | Optional `competitor_seo_patterns` (≤8 strings) |
| Coverage | Up to 40 gap topics | Optional `coverage_gaps` (≤12) |

Context builder: `build_strategist_context()` → `build_strategist_context_from_profile()`.

### Outputs

JSON `ideas[]` with `title`, `type`, `entity`, `rationale`, `priority`, `topic`, `target_keyword`. Max `max_ideas_hint`.

### Token / size measurements (Example Lab workspace, 2026-06-02)

| Mode | Chars | Est. tokens | Notes |
|------|-------|-------------|-------|
| **A — Legacy wide context** | 1,492 | 373 | Niche profile + inventory + site description |
| **B — Compact profile** | 820 | 205 | **45% reduction** |
| **B — Minimal fixture** (6 products) | 339 | 84 | DeepSeek-style product list |

Full crawl-dump strategist context (pre-refactor, 30+ inventory rows + pages) could exceed **3,000–8,000+ est. tokens**; compact profile avoids that scaling.

### Responsibilities

| | Before | After |
|---|--------|-------|
| Article ideation | Shared with website analysis + EOG | **Primary owner** |
| Product education / FAQ / comparisons | Partial | **Prioritized in prompt** |
| Generic / platform topics | Often leaked | **Explicit avoid list** |
| Raw crawl interpretation | Strategist received dumps | **Removed** |

---

## 4. AI Recommendation Reviewer (`ai_recommendation_reviewer.yaml`)

| Field | Detail |
|-------|--------|
| **Template** | `app/prompts/templates/ai_recommendation_reviewer.yaml` |
| **Version** | v1 (unchanged) |
| **Model task** | `CLASSIFICATION` |
| **Purpose** | Relevance validation only |

### Inputs (after audit)

`build_reviewer_context_from_profile()`:

- `business_type`, `primary_niche`
- `known_products`, `known_categories`, `existing_articles`
- `recommendations[]` (subset for review)

### Outputs

Per-recommendation scores and `recommended_action` (`create|refresh|monitor|ignore`).

### Token size

Typically **<800 chars** context for top-N recommendations (see `tests/test_ai_recommendation_reviewer.py`).

### Responsibilities audit

| Allowed | Forbidden (enforced in prompt) |
|---------|------------------------------|
| Score relevance / alignment | Generate new ideas |
| Recommend action per existing row | Rewrite titles |
| Flag platform noise (Facebook, etc.) | Invent recommendations |

**Conclusion:** Reviewer scope unchanged; context tightened to Site Strategy Profile.

---

## 5. Strategist context A/B experiment (Part 4b)

Script: `scripts/run_strategist_context_ab.py`

Example Lab run (mock ideation when `--live` not set):

| Metric | Mode A (legacy) | Mode B (compact) |
|--------|-----------------|------------------|
| Context tokens | 373 | 205 |
| `product_alignment_rate` (mock) | N/A (size-only A) | **0.875** |
| `category_alignment_rate` | — | 0.438 |
| `off_topic_rate` | — | **0.0** |

Mock Mode B ideas resemble expected outputs: `BPC-157 Research Overview`, `What Is Kisspeptin?`, `Research Peptide Storage Guide`, `Peptide Reconstitution Guide`.

**Finding:** Smaller context does not reduce product alignment on Example Lab; it improves focus. Live `--live` run recommended after next full analyze to compare OpenAI-generated ideas.

Full JSON: `docs/analysis/STRATEGIST_CONTEXT_AB.json`

---

## 6. Example Lab validation expectations (Part 8)

After refactor, strategist should prioritize:

- What Is BPC-157? / BPC-157 FAQ
- GHK-CU / MOTS-C / Kisspeptin research overviews
- Retatrutide vs Tirzepatide (comparison)
- Research Peptide Storage / Reconstitution guides

Current persisted recommendation queue (pre re-analyze): **0** matches for Facebook, Bookshelf, Adhesives, Characteristics, Internet — off-topic items were from earlier pipeline runs (see lineage audit).

---

## 7. Tests

| Test file | Coverage |
|-----------|----------|
| `tests/test_site_strategy_profile.py` | WA extraction-only prompt, strip ideation, profile build, context size reduction |
| `tests/test_analysis_digest.py` | Digest compactness, v6 extraction prompt |
| `tests/test_ai_editorial_strategist_context.py` | Compact strategist context, parser anchoring |
| `tests/test_ai_recommendation_reviewer.py` | Reviewer behavior + compact context |

---

## Conclusion

**A) Prompt responsibilities simplified and strategist input tightened**

Website analysis is extraction-only. Article ideation moved to the editorial strategist. Site Strategy Profile is persisted and wired to strategist, reviewer, and diagnostics. Strategist context reduced ~45% on Example Lab (higher reduction possible vs full crawl-dump legacy paths).
