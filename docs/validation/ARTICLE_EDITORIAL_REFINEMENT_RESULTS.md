# Article editorial refinement results

**Date:** 2026-06-05  
**Reference article:** BPC-157 research overview: signaling, epithelial repair hypotheses, and literature context  
**Scope:** Render-surface leakage, product reference copy, compliance deduplication, science-depth briefing, supplier-language reduction

---

## Summary

| Issue | Before | After |
|-------|--------|-------|
| Schema leakage (`Content Markdown`) | Object fields rendered as `**Content Markdown**` headings | Prose extracted without schema artifact labels |
| Product CTA | `Product reference` + generic supplier wording | Natural editorial sentence + link, no machine heading |
| Compliance repetition | Same uncertainty caveat in context, sections, and safety | One retained caveat; duplicates removed post-generation |
| Science brief depth | `science_focus` + related topics only | `science_depth_targets` with pathways, themes, models, evidence |
| Supplier language (science articles) | Could appear in body when model drifted | Stripped post-generation for science editorial types |
| Internal `heading` object fields | `**Heading**` + duplicate section title text | Content inlined; outer renderer supplies h2 only |

---

## Part 1 — Render-surface leakage

### Before

```text
Research Context

Content Markdown

BPC-157 is discussed in preclinical repair literature...
```

### After

```text
Research Context

BPC-157 is discussed in preclinical repair literature...

Evidence limitations

Human translation remains limited.
```

**Fix:** `_prose_from_mapping()` in `article_schema.py` treats `content_markdown` and other schema keys as content carriers, not reader-facing headings.

**Regression test:** `tests/test_article_normalization_regression.py::test_content_markdown_object_does_not_leak_schema_label`

---

## Part 2 — Product reference rendering

### Before (publishable HTML)

```html
<h2>Product reference</h2>
<p>Review the relevant product or category page for specifications, documentation, and research-use context.</p>
```

### After (publishable HTML)

```html
<p>Researchers interested in BPC-157 materials can review the BPC-157 product page for specifications and supporting documentation.</p>
<p><a href="https://www.example.com/product/bpc-157/">BPC-157</a></p>
```

**Fix:** `_publishable_product_reference()` in `article_renderer.py` — no CTA heading on publishable surface.

---

## Part 3 — Compliance repetition

### Before (example)

- `research_context`: "Mechanism remains unsettled across model systems."
- `sections[0]`: "Evidence remains limited in preclinical models."
- `limitations_and_safety`: "Evidence remains limited and readers should be cautious..."

### After

- `limitations_and_safety`: retains primary disclaimer + **one** uncertainty sentence
- Duplicate "evidence remains limited" removed from sections/context

**Fix:** `app/review/compliance_redundancy.py` → `reduce_compliance_repetition()` wired in `jobs.py` via `apply_editorial_post_processing()`.

**Regression test:** `tests/test_compliance_redundancy.py::test_reduce_compliance_repetition_keeps_one_uncertainty_warning`

---

## Part 4 — Science-depth briefing

Science-focused ideation opportunities now include:

```json
{
  "science_focus": true,
  "science_depth_targets": {
    "major_pathways": ["GLP-1 signaling", "GIP receptor biology"],
    "recurring_literature_themes": ["signaling biology discussed in research literature"],
    "experimental_models": ["preclinical and in vitro models discussed in literature"],
    "controversies": ["distinctions researchers draw between related compounds or categories"],
    "evidence_strengths": ["pathway-level observations from preclinical studies"],
    "evidence_limitations": ["limited human clinical translation", "model-dependent interpretation"]
  }
}
```

Passed to article generation via `opportunity_context_json` and honored in `article_generation.yaml`.

---

## Part 5 — Science editorial commerce-language filter

Post-generation strip removes buyer/shopper/purchasing/supplier-evaluation/catalog-selection sentences when `content_type` or `search_intent` is `research_overview`, `comparison`, `mechanism`, or `relationship` (or `science_focus: true`). **Buyer guides are exempt.**

**Regression tests:** `test_strip_buyer_language_for_comparison_article`, `test_strip_buyer_language_for_mechanism_article`, `test_buyer_guide_article_keeps_commerce_language`

### Before (comparison fixture)

```text
Buyers often compare catalog listings before selecting a peptide. CJC-1295 No DAC and Ipamorelin differ in receptor engagement.
```

### After

```text
CJC-1295 No DAC and Ipamorelin differ in receptor engagement.
```

---

## Part 6 — Heading object cleanup (CJC-1295 case)

### Before

```text
Research Context

**Heading**

Context for biomedical researchers

CJC-1295 No DAC and IPA are discussed in growth-hormone secretagogue literature.
```

### After

```text
Research Context

CJC-1295 No DAC and IPA are discussed in growth-hormone secretagogue literature.
```

---

## Part 7 — Live generation verification

`scripts/verify_science_article_language.py` generated comparison + mechanism articles (2026-06-05). Both passed with zero commerce-language hits and zero schema-label hits.

**Artifact:** `docs/validation/SCIENCE_ARTICLE_LANGUAGE_VERIFICATION.json`

---

## Files changed

| File | Change |
|------|--------|
| `app/article_schema.py` | Schema-safe prose normalization; `heading`/`summary`/`points` suppressed |
| `app/rendering/article_renderer.py` | Natural publishable product reference |
| `app/review/compliance_redundancy.py` | Compliance dedupe + science editorial commerce-language filter |
| `app/ai_opportunity_ideation/article_brief.py` | `science_depth_targets`, `is_science_editorial_article()` |
| `scripts/verify_science_article_language.py` | Live comparison + mechanism verification script |
| `docs/validation/SCIENCE_ARTICLE_LANGUAGE_VERIFICATION.json` | Generated article artifacts |
| `app/services/jobs.py` | Post-generation editorial processing |
| `app/prompts/templates/article_generation.yaml` | Science depth + anti-repetition guidance |
| `tests/test_article_normalization_regression.py` | Schema leakage + product CTA tests |
| `tests/test_compliance_redundancy.py` | **New** |
| `tests/test_article_render_surfaces.py` | Updated CTA expectation |
