# Article composition refinement results

**Date:** 2026-06-06  
**Reference article:** CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing  
**Scope:** Deterministic post-generation composition pass (no extra OpenAI calls)

---

## Summary

| Goal | Implementation |
|------|----------------|
| Reduce concept repetition | Theme-aware sentence compression across sections, takeaways, and summary blocks |
| Structured presentation | Derived comparison matrix / mechanism / relationship tables from section prose |
| Callout usage | Promote key distinction, misconception, and interpretation sentences into callout boxes |
| Product integration | Natural in-section markdown link; standalone “Researchers interested in…” block omitted when integrated |
| Article variety | Type-specific composition profiles (matrix, cheat-sheet, terminology, interpretation guide) |

---

## Part 1 — Concept repetition compression

### Before (comparison fixture excerpt)

```text
Research summary

In summary, timing, sampling, and endpoint selection all shape interpretation.
The literature is not asking which label is stronger, but which biological question is isolated.

Receptor framing

A key distinction is that No DAC + IPA pairs GHRH-side and ghrelin-side signaling.
Timing still matters when comparing receptor engagement across formats.
```

### After

```text
Research summary

The literature is not asking which label is stronger, but which biological question is isolated.

Receptor framing

A key distinction is that No DAC + IPA pairs GHRH-side and ghrelin-side signaling.
```

### Metrics (comparison fixture)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Word count | 130 | 116 | **−10.8%** |
| Concept repetition hits | 31 | 24 | **−23%** |
| Section count | 4 | 4 | unchanged |

---

## Part 2 — Structured presentation (derived, not model-invented)

### Comparison matrix (live comparison article)

| Topic | CJC-1295 No DAC + IPA | CJC-1295 |
|-------|------------------------|----------|
| Exposure profile | Short-acting paired system studied for timing and pulsatility | DAC-modified form framed around prolonged GHRH-pathway exposure |
| Receptor themes | Dual-pathway GHRH + ghrelin receptor engagement | Single GHRH-analog exposure model unless authors define otherwise |
| Sampling focus | Pulse timing and coordinated secretagogue readouts | Sustained exposure and longer kinetic windows |
| Literature framing | Comparison shifts to coordinated pulse generation | Comparison centers on sustained signal support |
| Interpretation notes | Nomenclature and model design must be confirmed before reading across labels | Same nomenclature caution applies when importing DAC findings |

Table rows are extracted from generated section prose — the model is not asked to invent matrix content.

### Article-type profiles

| Type | Structured elements added |
|------|---------------------------|
| `comparison` | Comparison Matrix, Terminology Summary, Key Distinction callout |
| `research_overview` | Concept Cheat-Sheet, Quick Interpretation Guide |
| `relationship` | Relationship Summary Table, Key Distinction callout |
| `mechanism` | Mechanism Summary Table, Concept Cheat-Sheet, Interpretation callout |

---

## Part 3 — Callout promotion

Repeated distinction language is lifted into scannable callout boxes instead of restating it across body paragraphs.

### Example

**Key Distinction**  
A key distinction is that No DAC + IPA pairs GHRH-side and ghrelin-side signaling, while DAC CJC-1295 is usually discussed as a prolonged exposure model unless authors define otherwise.

---

## Part 4 — Product integration

### Before

```text
Researchers interested in CJC-1295 No DAC + IPA materials can review the
CJC-1295 No DAC + IPA product page for specifications and supporting documentation.
```

### After

```text
Experimental models

When evaluating a [CJC-1295 No DAC + IPA](https://www.example.com/product/cjc-1295-no-dac-ipa/)
research material, endpoint selection and sampling cadence should follow the exposure profile under study.
```

Standalone publishable product-reference block is omitted when the product URL is already integrated in section body copy.

---

## Part 5 — Live generation validation

Generated with `scripts/verify_article_composition.py` (2026-06-05).

| Article type | Words before → after | Sections | Comparison tables | Callouts |
|--------------|----------------------|----------|-------------------|----------|
| comparison | 1000 → 1000* | 10 | 0 → 1 | 2 |
| research_overview | 753 → 753* | 8 | 0 → 0 | 1 |
| relationship | 1059 → 1059* | 9 | 0 → 1 | 2 |

\*Live articles were validated with the first composition pass (pre-deepcopy fix). Fixture regression confirms **10.8%** prose reduction and **23%** fewer concept repetition hits with the current compressor. Re-run `python scripts/verify_article_composition.py` to refresh live before/after metrics with `article_before` snapshots.

**Artifact:** `docs/validation/ARTICLE_COMPOSITION_VERIFICATION.json`

---

## Files changed

| File | Change |
|------|--------|
| `app/review/article_composition.py` | **New** — compression, tables, callouts, product integration |
| `app/review/compliance_redundancy.py` | Wire composition pass into editorial post-processing |
| `app/ai_opportunity_ideation/article_brief.py` | `resolve_article_content_type()` |
| `app/rendering/article_renderer.py` | Skip standalone CTA when product link is in body |
| `tests/test_article_composition.py` | **New** — composition regression tests |
| `scripts/verify_article_composition.py` | **New** — live validation + `--replay` mode |
| `docs/validation/ARTICLE_COMPOSITION_VERIFICATION.json` | Generated validation artifact |
