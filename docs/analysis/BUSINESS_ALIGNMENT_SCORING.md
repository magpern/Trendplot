# Business Alignment Scoring

**Date:** 2026-06-02  
**Scope:** Ecommerce recommendation ranking and CREATE eligibility in Opportunity Intelligence (OI)  
**Validation site:** Example Lab-style peptide ecommerce (fixture-based, no hardcoded product allowlists)

---

## Problem

The pipeline behaved like *“what topics exist in this niche?”* instead of *“what content supports this business and its products?”*

Observed CREATE examples that should not dominate:

- Introduction to Bookshelf for New Readers
- Introduction to Experimental Design for New Readers
- Introduction to Lab Reproducibility for New Readers
- Generic biology concepts (inflammation, AMPK) without catalog linkage

---

## Solution overview

Added **business-alignment-first** scoring for ecommerce sites without removing EOG, OI, strategist, or reviewer.

Module: `app/opportunity_intelligence/business_alignment.py`

Flow:

```text
Candidate discovered (EOG / niche profile / market / strategist)
  → classify business alignment tier (1–5)
  → persist business_alignment_score + linked_product/category
  → adjust OI composite score (+bonus / −penalty by tier)
  → decide_action (existing rules)
  → apply_ecommerce_create_gate (tier-based CREATE cap)
  → explainability + Analyze diagnostics
```

Ecommerce detection: `business_type` is ecommerce **or** `known_products` has ≥2 items (from niche profile or Site Strategy Profile).

---

## Part 1 — Business alignment tiers

| Tier | Label | Examples (peptide ecommerce) | CREATE default |
|------|-------|------------------------------|----------------|
| **1** | Product anchored | What Is BPC-157?, BPC-157 FAQ, Retatrutide vs Tirzepatide | **Yes** |
| **2** | Product support | Peptide Storage Guide, Reconstitution Guide, Purity/Handling | **Yes** |
| **3** | Category anchored | Research Peptides Overview, Metabolic Peptides Guide | **Yes** |
| **4** | General niche | Autophagy, AMPK, Inflammation (no catalog match) | **Monitor** (CREATE only with strong external evidence + score ≥ 0.72) |
| **5** | Generic science / junk | Bookshelf, Experimental Design, Lab Reproducibility, template fragments | **Ignore** |

Classification uses:

- `known_products`, `known_categories` (niche profile + Site Strategy Profile)
- Generic product-support regex (storage, reconstitution, lyophilized, bacteriostatic, FAQ, etc.)
- Niche entities (known_entities minus products)
- `is_generic_science_concept_entity()` junk filter

No peptide names are hardcoded.

---

## Part 2 — Business alignment score

Field: `business_alignment_score` (0.0–1.0)

| Tier | Score band |
|------|------------|
| 1 | ~0.96–1.00 |
| 2 | ~0.84 |
| 3 | ~0.70 |
| 4 | ~0.45 |
| 5 | ~0.12 |

Persisted on recommendation `metadata` and `metadata.explainability`:

```json
{
  "business_alignment_tier": 1,
  "business_alignment_score": 0.96,
  "linked_product": "BPC-157",
  "linked_category": null,
  "business_alignment_trace": "product_anchored"
}
```

OI composite score adjustment (`scoring.py`):

| Tier | Score delta |
|------|-------------|
| 1 | +0.14 |
| 2 | +0.09 |
| 3 | +0.04 |
| 4 | −0.14 |
| 5 | −0.30 |

---

## Part 3 — CREATE eligibility (ecommerce)

After standard `decide_action()`:

| Tier | Gate result |
|------|-------------|
| 1–3 | CREATE allowed (if other OI gates pass) |
| 4 | Demote CREATE → **monitor** always |
| 5 | Demote CREATE → **ignore** |

Function: `apply_ecommerce_create_gate()`

---

## Part 4 — Product dominance target

Summary metric in OI `build_recommendations` summary:

```json
"ecommerce_business_alignment": {
  "create_total": 6,
  "product_anchored_create": 4,
  "product_support_create": 1,
  "category_anchored_create": 1,
  "general_niche_create": 0,
  "generic_science_create": 0,
  "product_category_support_create_pct": 100.0,
  "generic_science_create_pct": 0.0
}
```

**Target:** 80–90% of CREATE rows in tiers 1–3.

---

## Part 5 — Bad extracted entities

Extended `app/market_intelligence/filters.py`:

- `GENERIC_SCIENCE_CONCEPT_TERMS` — bookshelf, practical, experimental design, lab reproducibility, etc.
- `is_generic_science_concept_entity()` — template phrases (`Introduction to`, `How Researchers Approach`, …)
- Wired into `is_entity_quality_junk()` so seeds are blocked upstream of EOG

**Origin of junk entities:** capitalized-token extraction from page titles/headings (`PageSignalParser` regex), merged into `known_entities` via niche intelligence, then fed to market seeds and EOG templates.

---

## Part 6 — Diagnostics

Analyze Website → **Diagnostics** → Recommendation scoring cards show:

```text
Business alignment: tier 1 · score 0.96 · product BPC-157
```

---

## Part 7 — Example Lab validation (fixture run)

Mixed editorial backlog (junk + product + support + niche):

| Metric | Result |
|--------|--------|
| Bookshelf / Experimental Design / Lab Reproducibility CREATE | **0** |
| Product-aligned CREATE examples | BPC-157, GHK-CU, Kisspeptin, Retatrutide vs Tirzepatide, Peptide Storage Guide |
| `product_category_support_create_pct` | **100%** (fixture cohort) |
| `generic_science_create_pct` | **0%** |
| Inflammation (tier 4) | **monitor**, not CREATE |

Tests: `tests/test_business_alignment_scoring.py`

---

## Files changed

| File | Change |
|------|--------|
| `app/opportunity_intelligence/business_alignment.py` | **New** — tiers, score, gate, summary |
| `app/opportunity_intelligence/service.py` | Apply alignment; gate; summary |
| `app/opportunity_intelligence/scoring.py` | Tier score bonus/penalty |
| `app/opportunity_intelligence/explainability.py` | Diagnostics fields |
| `app/market_intelligence/filters.py` | Generic science entity filter |
| `app/analyze_ui.py` | Diagnostics UI |
| `app/autopilot/service.py` | Pass `strategy_profile` into OI |
| `tests/test_business_alignment_scoring.py` | **New** |

---

## Conclusion

**A) Business-alignment-first scoring implemented**

Ecommerce sites now rank and gate recommendations by catalog linkage (product → support → category) instead of raw niche breadth. Generic science and template junk are filtered upstream and blocked from CREATE downstream.
