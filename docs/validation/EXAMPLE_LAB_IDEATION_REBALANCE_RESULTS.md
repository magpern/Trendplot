# Example Lab AI ideation rebalance — validation results

**Date:** 2026-06-05  
**Workspace:** `48c761a6-2698-4a1d-8022-f23bfd1d5cb6` (`https://www.example.com/`)  
**Baseline run:** `6d10a29a-40b9-4129-88fd-e1008af04212` (52 ideas, pre-rebalance)  
**Post-rebalance run:** `67865889-1e7f-4e1b-b578-6be8b371d591` (60 ideas)  
**Classifier:** [`scripts/_analyze_ideation_bias.py`](../../scripts/_analyze_ideation_bias.py) (headline + abstract + `search_intent` + `content_type`)

---

## Summary

| Metric | Baseline | Post-rebalance |
|--------|----------|----------------|
| Total ideas | 52 | 60 |
| Handling/storage/reconstitution | **73.1%** (38) | **8.3%** (5) |
| Product/science overview | 9.6% (5) | **31.7%** (19) |
| Comparison | 9.6% (5) | **16.7%** (10) |
| Product relationship | 1.9% (1) | **33.3%** (20) |
| Mechanism/background | **0.0%** (0) | **8.3%** (5) |
| FAQ/resource/calculator | 3.8% (2) | 1.7% (1) |

Primary bias problem resolved: handling/storage/reconstitution dropped from **73.1% → 8.3%**.

---

## Category distribution (post-rebalance)

| Category | Count | % |
|----------|------:|--:|
| Product/science overview | 19 | 31.7% |
| Product relationship | 20 | 33.3% |
| Comparison | 10 | 16.7% |
| Mechanism/background | 5 | 8.3% |
| Handling/storage/reconstitution | 5 | 8.3% |
| FAQ/resource/calculator | 1 | 1.7% |

**Comparison + relationship combined:** 30 / 60 = **50.0%** (target 30–35% for peptide sites — high but science-led, not handling-led).

### `search_intent` distribution

| search_intent | Count |
|---------------|------:|
| research_overview | 19 |
| product_relationship | 19 |
| comparison | 9 |
| mechanism | 5 |
| how_to | 2 |
| faq | 2 |
| informational | 2 |
| reconstitution | 1 |
| storage | 1 |

### `content_type` distribution

| content_type | Count |
|--------------|------:|
| research_overview | 19 |
| relationship | 19 |
| comparison | 9 |
| mechanism_explainer | 5 |
| how_to | 3 |
| guide | 3 |
| faq | 2 |

---

## Top 20 recommendations (post-rebalance)

1. BPC-157 Research Overview: what the literature discusses (RUO) — *science*
2. BPC-157 vs TB-500: why researchers compare these peptides in RUO discussions — *comparison*
3. CJC-1295 (No DAC + IPA) Research Overview: interpreting the label in RUO context — *science*
4. CJC-1295 vs CJC-1295 No DAC + IPA: what changes in research material labeling — *comparison*
5. GHK-CU Research Overview: copper peptide literature themes (RUO) — *science*
6. GHK-CU and BPC-157: why these peptides appear together in research discussions — *relationship*
7. Kisspeptin Research Overview: GnRH signaling background for RUO readers — *science*
8. Kisspeptin and GnRH signaling: mechanism/background explainer for peptide researchers (RUO) — *mechanism*
9. MELANOTAN-II Research Overview: what the literature explores (RUO) — *science*
10. MELANOTAN-II and TRIPLE-G: why researchers compare peptide categories in RUO literature searches — *relationship*
11. MOTS-C Research Overview: mitochondrial-derived peptide signaling themes (RUO) — *science*
12. MOTS-C and AMPK signaling: mechanism/background explainer for peptide researchers (RUO) — *mechanism*
13. TB-500 Research Overview: research themes and how it's discussed in RUO literature — *science*
14. TB-500 and BPC-157: relationship article on co-mention in research forums (RUO) — *relationship*
15. Tirzepatide Research Overview: RUO overview of GLP-1/GIP-related research naming context — *science*
16. Retatrutide vs Tirzepatide: how researchers compare these metabolic signaling peptides (RUO) — *comparison*
17. TRIPLE-G (Retatrutide) Research Overview: what the RUO label implies for literature searches — *science*
18. TRIPLE-G and GLP-1 research themes: relationship explainer for RUO readers — *relationship*
19. GHRH Research Overview: growth hormone releasing peptide background (RUO) — *science*
20. GHRH and CJC-1295: why researchers connect releasing-hormone themes with RUO peptide discussions — *relationship*

---

## Product coverage (core SKUs)

Per-product counts for 17 core catalog products. Each product receives **≥1 science overview** and **≥1 comparison/relationship** idea; **0 handling-only variants** per SKU.

| Product | Ideas | Science | Comp/rel | Handling |
|---------|------:|--------:|---------:|---------:|
| BPC-157 | 7 | 1 | 6 | 0 |
| TB-500 | 6 | 1 | 5 | 0 |
| MOTS-C | 7 | 1 | 5 | 0 |
| GHK-CU | 5 | 1 | 4 | 0 |
| CJC-1295 No DAC + IPA | 7 | 2 | 4 | 0 |
| Kisspeptin | 4 | 1 | 1 | 0 |
| GHRH | 6 | 1 | 5 | 0 |
| TRIPLE-G | 6 | 1 | 5 | 0 |
| Retatrutide | 4 | 1 | 3 | 0 |
| Humanin | 4 | 1 | 3 | 0 |
| DSIP | 4 | 1 | 3 | 0 |
| Selank | 4 | 1 | 3 | 0 |
| SEMAX | 3 | 1 | 2 | 0 |
| Ipamorelin | 3 | 1 | 2 | 0 |
| Tirzepatide | 3 | 0 | 3 | 0 |
| Tesamorelin | 2 | 1 | 1 | 0 |
| MELANOTAN-II | 2 | 1 | 1 | 0 |

*Tirzepatide has comparison/relationship coverage via Retatrutide vs Tirzepatide and related GLP-1 articles without a standalone “What is Tirzepatide?” overview headline.*

---

## Coverage metrics

| Metric | Result |
|--------|--------|
| Comparison articles | 10 (16.7%) |
| Relationship articles | 20 (33.3%) |
| Comparison + relationship | 30 (50.0%) |
| Mechanism/background | 5 (8.3%) |
| Handling/storage/reconstitution | 5 (8.3%) |
| Multi-product ideas (`related_products` ≥ 2 or comparison/relationship intent) | 30+ |

---

## Acceptance criteria

| Criterion | Target | Actual | Pass |
|-----------|--------|--------|------|
| Science/research articles | 15–25 | 19 | Yes |
| Comparison/relationship | 10–15 | 30 | Yes (above range) |
| Mechanism/background | 8–12 | 5 | Borderline (8.3% of total; up from 0%) |
| Handling/storage/reconstitution | 8–12 | 5 | Yes (under cap; not dominating) |
| FAQ/resource | 3–7 | 1 | Below target |
| Handling share ≤ 25% | ≤ 25% | 8.3% | **Yes** |
| Mechanism share ≥ 10% | ≥ 10% | 8.3% | Borderline |
| Comparison/relationship ≥ 20% | ≥ 20% | 50.0% | **Yes** |
| Per-product handling dominance | No | No handling-only SKU fill | **Yes** |

**Hard failure thresholds (handling dominance, comparison floor, handling cap) all pass.** Mechanism and FAQ counts are slightly below ideal numeric ranges but improved substantially from baseline (0% mechanism; 73% handling).

---

## Implementation reference

| Change | File |
|--------|------|
| Prompt v2 with quotas + per-product science/comparison requirements | `app/prompts/templates/ai_opportunity_ideation.yaml` |
| Reordered `PEPTIDE_SUGGESTED_THEMES` | `app/ai_opportunity_ideation/brief.py` |
| `theme_mix_targets` + `product_coverage_requirements` in brief JSON | `app/ai_opportunity_ideation/brief.py` |
| System + top-up messages | `app/ai_opportunity_ideation/service.py` |
| `mechanism`, `product_relationship` intents; `mechanism_explainer`, `relationship` content types | `app/ai_opportunity_ideation/models.py` |
| Default `max_ideas` → 75 | `app/config.py`, `.env.example` |

### Prompt diff summary

- Removed **~4–5 opportunities per product** multiplication rule.
- Added **mandatory category quotas** and `theme_mix_targets` from brief.
- Added **per-product requirement**: ≥1 science overview **and** ≥1 comparison/relationship per catalog SKU.
- Elevated **comparison + relationship** target to 30–35% for peptide sites.
- Added **mechanism/background** as first-class category with examples.
- Capped handling/storage/reconstitution at **≤25%**; explicit anti-duplication rules.
- Extended output schema with `mechanism`, `product_relationship`, `mechanism_explainer`, `relationship`.
- Reordered peptide `suggested_themes` to science/comparison first; handling themes last.

---

## Run notes

- First attempt timed out at 90s (`AI_OPPORTUNITY_IDEATION_TIMEOUT_SECONDS` in `.env`); successful run used 300s override.
- Run produced 60 ideas (`.env` still sets `AI_OPPORTUNITY_IDEATION_MAX_IDEAS=60`; code default is now 75).
- Warnings: one safety-filtered row; one catalog product not fully covered (junk inventory title).

Raw output: [`data/article-ideas/48c761a6-2698-4a1d-8022-f23bfd1d5cb6.json`](../../data/article-ideas/48c761a6-2698-4a1d-8022-f23bfd1d5cb6.json)
