# AI ideation prompt rebalance plan

**Status:** Design only — **do not apply** until reviewed.  
**Companion trace:** [`docs/debug/AI_IDEATION_PROMPT_TRACE.md`](../debug/AI_IDEATION_PROMPT_TRACE.md)  
**Target site:** Example Lab (`peptides` / RUO ecommerce)

---

## Problem statement

Latest Example Lab ideation run (52 ideas, 2026-06-05) produced **~73% handling/storage/reconstitution** topics and **0% mechanism/background** ideas. Comparisons often reframe as *"lab handling comparison"*. The prompt, peptide `suggested_themes`, catalog-coverage rule, and `search_intent` schema collectively steer the model toward safe, repetitive lab-workflow content.

---

## Target category mix (generation-time)

| Category | Target % | Notes |
|----------|----------|--------|
| Product/science research overview | **30–40%** | At least one per major catalog product |
| Comparison + product relationship | **20–25%** | Includes vs, paired-product, co-discussion |
| Mechanism/background explainers | **15–20%** | Signaling, pathways, literature context |
| Handling/storage/reconstitution/practical lab | **15–20%** | Useful but **must not dominate** |
| FAQ/resource/calculator/supporting | **5–10%** | Checklists, calculators, glossaries |

### Hard rules

1. **Handling/storage/reconstitution must not exceed ~25%** of total ideas in a single run.
2. **Each major catalog product** (top SKUs by catalog order) gets **≥1 science/research overview** (not only handling).
3. **≥20% of ideas** must connect **two or more products or concepts** (comparison or relationship).
4. **No near-duplicate handling articles** for the same product (max **one** storage + **one** reconstitution/handling per product unless catalog &gt;75).
5. Maintain RUO framing; **no** dosing, treatment, human-use, or combined-use recommendations.
6. Relationship articles may note products are **often researched or discussed together** — **never** imply recommended combined use.

---

## Implementation plan (when approved)

### Phase A — Prompt + brief (highest leverage)

| Change | File |
|--------|------|
| Replace YAML template with rebalance version below | `app/prompts/templates/ai_opportunity_ideation.yaml` |
| Reorder `PEPTIDE_SUGGESTED_THEMES` — science/comparison first, handling capped | `app/ai_opportunity_ideation/brief.py` |
| Add `theme_mix_targets` object to brief JSON | `app/ai_opportunity_ideation/brief.py` |
| Update system/top-up messages with diversity quotas | `app/ai_opportunity_ideation/service.py` |
| Raise default `max_ideas` to **75** (optional config) | `app/config.py`, `.env.example` |

### Phase B — Parser enforcement (optional safety net)

| Change | File |
|--------|------|
| Post-parse category balancer / reject excess handling per product | `app/ai_opportunity_ideation/parser.py` |
| Warn when mix deviates &gt;10% from targets | `parser.py` + run metadata |

### Phase C — Vertical profile alignment

| Change | File |
|--------|------|
| Rebalance `peptides.py` `ideation_themes` and `entity_expansion_map` toward mechanism/comparison | `app/opportunities/verticals/peptides.py` |

### Phase D — Validation

Re-run ideation for Example Lab with `force_refresh=true`; classify with same heuristic as trace doc; compare to acceptance criteria below.

---

## Acceptance criteria (post-implementation, Example Lab, 50–75 ideas)

| Category | Expected count |
|----------|---------------:|
| Product/science articles | **15–25** |
| Comparison/relationship | **10–15** |
| Mechanism/background | **8–12** |
| Handling/storage/reconstitution | **8–12** (not 30+) |
| FAQ/resource/calculator | **3–7** |

**Fail if:** &gt;20 handling/storage/reconstitution ideas, or &lt;8 science/overview ideas, or &lt;8 comparison/relationship ideas.

---

## Part 5 — Draft revised prompt text (v2, not applied)

Save as future `ai_opportunity_ideation.yaml` **version 2**. Uses `priority_reason` for rationale (existing schema field); alias `rationale` in docs only unless schema extended.

```yaml
id: ai_opportunity_ideation
version: 2
description: Diverse catalog-aware article opportunity ideation
model_task: CLASSIFICATION
required_variables:
  - opportunity_ideation_brief_json
  - min_ideas
  - max_ideas
template: |
  Generate high-quality SEO article opportunities for this website.

  You receive a compact site brief JSON. Use only fields present in the brief.

  ## Volume
  Generate between {{ min_ideas }} and {{ max_ideas }} opportunities.
  This count is mandatory. Do not stop early.

  ## Category diversity (mandatory quotas)
  Distribute opportunities approximately as follows:
  - 30–40% product/science research overviews (what the product is, research context, catalog role)
  - 20–25% comparisons and product-relationship articles (vs, paired discussion, why concepts appear together)
  - 15–20% mechanism/background explainers (signaling, pathways, literature themes — RUO framing)
  - 15–20% practical lab workflow (storage, reconstitution, handling, documentation, inventory) — **cap: no more than 25% of total**
  - 5–10% FAQ, calculator, checklist, or resource support content

  Before finalizing, verify:
  - Handling/storage/reconstitution topics are **not** the majority.
  - At least 20% of ideas reference **two or more** products or concepts from the brief.
  - Each major `catalog_products` entry has **at least one science/research overview** (not only handling).
  - No more than **one** storage-focused and **one** reconstitution/handling-focused idea per catalog product (unless brief says catalog has >75 products).

  ## Catalog coverage
  When `catalog_products` has ≤75 items, every product must appear in at least one opportunity (`headline` or `related_products`).
  Coverage is a **minimum**, not a license to repeat the same handling angle for every SKU.

  Use `suggested_themes` and `theme_mix_targets` from the brief for angle ideas, but **do not** treat handling/storage as the default angle.

  ## Topic examples (steer toward these patterns)
  Science / overview:
  - What is BPC-157? Research overview and mechanisms discussed in literature (RUO)
  - GHK-CU and copper peptide research: what the literature discusses
  - MOTS-C and mitochondrial signaling: research context for laboratory readers (RUO)

  Comparison:
  - BPC-157 vs TB-500: why researchers compare them in discussion (RUO)
  - Retatrutide vs Tirzepatide: research landscape and naming context (RUO)
  - CJC-1295 DAC vs No DAC: what the labels mean for catalog selection (RUO)
  - Ipamorelin vs GHRP-6: how researchers distinguish secretagogue research materials (RUO)

  Product relationship (not combined-use advice):
  - BPC-157 and TB-500: why they are often discussed together in research forums (RUO)
  - Kisspeptin and GnRH signaling: related research themes researchers track (RUO)

  Mechanism / background:
  - Kisspeptin and GnRH signaling: background for peptide research readers (RUO)
  - AMPK and metabolic signaling: primer for MOTS-C and AICAR research context (RUO)

  Practical lab (limited share):
  - Bacteriostatic water storage checklist for peptide reconstitution workflows (RUO)
  - Reconstitution documentation fields labs should record (RUO)

  Avoid:
  - 30+ near-duplicate storage/reconstitution/handling variants
  - Comparisons that are only about storage rotation or inventory unless explicitly a logistics guide
  - Generic glossary spam unrelated to catalog products
  - Topics unrelated to catalog, niche, or competitor gaps in the brief
  - Duplicating titles in `existing_page_titles`

  ## recommendation_type
  - create (default) | refresh | expand | follow_up

  ## Safety (mandatory)
  - Research/laboratory/RUO framing when brief indicates peptides or regulated research context
  - No medical claims, dosing, treatment, clinical outcomes, or human/veterinary use
  - Relationship articles: discuss co-mention in research discourse only — **do not** imply recommended combined protocols
  - Headlines: SEO-friendly, not clickbait; abstracts 1–2 sentences
  - Include `safety_notes` when RUO applies

  Site brief JSON:
  {{ opportunity_ideation_brief_json }}

output_contract: |
  Return strict JSON only:
  {
    "opportunities": [
      {
        "headline": "...",
        "abstract": "...",
        "search_intent": "informational|comparison|how_to|faq|calculator|research_overview|product_handling|storage|reconstitution|mechanism|product_relationship",
        "content_type": "guide|comparison|faq|calculator_support|research_overview|how_to|troubleshooting|mechanism_explainer|relationship",
        "recommendation_type": "create|refresh|expand|follow_up",
        "related_products": ["..."],
        "related_topics": ["..."],
        "target_audience": "...",
        "priority_reason": "...",
        "safety_notes": ["..."]
      }
    ]
  }

  `priority_reason` is the rationale (why this idea fits the site and search intent).
safety_rules:
  - Never generate article body text.
  - Never include medical or dosing advice in headlines or abstracts.
```

### Proposed `PEPTIDE_SUGGESTED_THEMES` reorder (brief.py)

```python
PEPTIDE_SUGGESTED_THEMES = [
    "research overviews",
    "mechanism and background explainers",
    "comparison articles",
    "product relationship articles",
    "FAQ and guide articles",
    "lab calculations",
    "storage",
    "reconstitution",
    "handling",
]
```

### Proposed brief addition: `theme_mix_targets`

```json
{
  "science_overview_pct": [30, 40],
  "comparison_relationship_pct": [20, 25],
  "mechanism_pct": [15, 20],
  "handling_storage_pct": [15, 20],
  "faq_resource_pct": [5, 10],
  "max_handling_storage_pct": 25,
  "min_multi_product_pct": 20
}
```

### Proposed system message (service.py)

```text
You generate diverse SEO article opportunities for research-oriented ecommerce sites.
Enforce category mix quotas in the user prompt. Handling/storage must not exceed 25% of ideas.
No medical claims. No human consumption or dosing. JSON only.
```

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Model ignores quotas | Parser-side cap on handling per product; run warnings |
| Safer science angles drift into claims | Keep safety regex; reviewer stage unchanged |
| Lower idea count if model self-censors | Top-up rounds with explicit deficit category ("need 10 more comparison ideas") |
| Schema drift (`mechanism` intent) | Extend `SEARCH_INTENTS` / `CONTENT_TYPES` in `models.py` when implementing |

---

## Summary

| Item | Action |
|------|--------|
| Trace | [`AI_IDEATION_PROMPT_TRACE.md`](../debug/AI_IDEATION_PROMPT_TRACE.md) |
| Root cause | Handling-first themes + catalog multiplication + storage/reconstitution intents |
| Fix | Prompt quotas + brief theme reorder + optional parser enforcement |
| Draft prompt | Above (v2, not applied) |
