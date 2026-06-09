# Comparison matrix quality results

**Date:** 2026-06-06  
**Reference articles:** CJC-1295 No DAC + IPA vs CJC-1295; Retatrutide vs Tirzepatide

---

## Root cause

The original matrix builder (`_snippet_for_subject` in `article_composition.py`) failed in three ways:

1. **Shared fallback** — when a sentence did not contain the full subject string, both columns fell back to `_snippet_for_keywords()`, which returned the **first** keyword-matching sentence for the entire article.
2. **Paragraph copying** — cells were truncated article sentences (up to 140 characters), not distilled distinctions.
3. **Comparison prose structure** — comparison articles often discuss both targets in the same paragraph, so subject-string matching produced the same excerpt for both columns.

**Trace path:** `content_type: comparison` → `build_type_structured_elements()` → `_build_comparison_matrix()` → `_snippet_for_subject()` → identical fallback sentence for left and right.

---

## Fix

New module `app/review/comparison_matrix.py`:

| Input source (priority) | Use |
|-------------------------|-----|
| `key_takeaways` | Contrast clauses (`while`, `whereas`) |
| `definition_boxes` | Term-level distinctions |
| `opportunity_context` / `science_depth_targets` | Brief-level comparison targets |
| Section headings + prose | Signal-based phrase extraction only |

Rules:

- Max **18 words** per cell
- Cells must differ and match topic signals
- Domain-aware fallbacks (`peptide_endocrine` vs `metabolic`)
- Weak / duplicate matrices are replaced (`matrix_cells_are_distinct`)

---

## Before / After — CJC-1295

### Before

| Topic | CJC-1295 No DAC + IPA | CJC-1295 |
|-------|------------------------|----------|
| Exposure profile | The practical answer is simple: CJC-1295 No DAC + IPA is not just a renamed version of CJC-1295. In research framing, it usually means a short-acting GHRH-side agent paired with ipamorelin... | The practical answer is simple: CJC-1295 No DAC + IPA is not just a renamed version of CJC-1295. In research framing, it usually means a short-acting GHRH-side agent paired with ipamorelin... |
| Receptor themes | *(same paragraph repeated)* | *(same paragraph repeated)* |

### After

| Topic | CJC-1295 No DAC + IPA | CJC-1295 |
|-------|------------------------|----------|
| Exposure profile | Shorter pulse-oriented exposure | Extended exposure profile |
| Receptor themes | GHRH + ghrelin-axis context | Primarily GHRH analog context |
| Sampling focus | Early pulse-sensitive windows | Broader time-course windows |
| Interpretation focus | Signal coordination | Exposure persistence |

---

## Before / After — Retatrutide vs Tirzepatide

### Before (fallback bleed from peptide template)

| Topic | Retatrutide | Tirzepatide |
|-------|-------------|-------------|
| Receptor themes | GHRH + ghrelin-axis context | Primarily GHRH analog context |

### After

| Topic | Retatrutide | Tirzepatide |
|-------|-------------|-------------|
| Exposure profile | Broader multi-receptor metabolic window | Dual incretin-centered window |
| Receptor themes | GLP-1 + GIP + glucagon tri-agonist | Dual GLP-1/GIP agonist |
| Sampling focus | Hepatic and energy-balance endpoints | Glycemic and weight endpoints |
| Interpretation focus | Pathway balance across three receptors | Incretin synergy framing |

---

## Validation

| Article | Cells distinct | ≤18 words/cell | No duplicated paragraphs |
|---------|----------------|----------------|--------------------------|
| CJC-1295 comparison | Yes | Yes | Yes |
| Retatrutide vs Tirzepatide | Yes | Yes | Yes |

**Artifacts**

- `docs/validation/COMPARISON_MATRIX_VERIFICATION.json`
- `tests/test_comparison_matrix.py`

**Re-run**

```bash
python scripts/verify_comparison_matrix.py
python -m pytest tests/test_comparison_matrix.py -q
```

---

## Files changed

| File | Change |
|------|--------|
| `app/review/comparison_matrix.py` | **New** — distinction-focused matrix builder |
| `app/review/article_composition.py` | Delegate to new builder; replace weak matrices |
| `tests/test_comparison_matrix.py` | **New** — matrix distinction regression tests |
| `scripts/verify_comparison_matrix.py` | **New** — live comparison validation |
