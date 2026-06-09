# Multi-Vertical Validation Report

**Date:** 2026-06-01
**Objective:** Determine whether the deterministic EOG/OI recommendation engine generalizes beyond the peptides workspace — i.e. validate **Trendplot**, not Example Lab.
**Scope of code change in this pass:** Part 1 deterministic cleanup only (typo gate, fragment filtering, coverage-source filtering). No AI, no providers, no architecture, no gate changes. `EDITORIAL_GENERATOR_AI_ENABLED` remains disabled.

---

## ⚠ Headline finding: multi-vertical validation is BLOCKED by data availability

The database contains **exactly one** analyzable workspace:

| Workspace | URL | Niche | Status | Recs |
| --- | --- | --- | --- | --- |
| Example Lab | https://www.example.com/ | peptides (research/regulated) | analyzed | 80 |

A scan of `analysis_jobs` (14 rows) returns only two URLs ever analyzed: `https://www.example.com/` and the placeholder `https://example.com/`. There are **no** software/SaaS, local-business, ecommerce, or content-site workspaces in the database.

Per the task constraints ("Avoid creating fake workspaces. Use existing data if available. If insufficient workspaces exist: document the limitation."), no synthetic workspaces were fabricated. Standing up real additional verticals would require running the full website-analysis pipeline (live crawl + OpenAI website analysis) against new domains — outside the deterministic scope of this pass and still yielding only hand-picked single examples.

**Consequence:** the cross-vertical comparison, failure-pattern generalization, and the central generalization claim **cannot be evidenced** from current data. This report documents the single-vertical result and states explicitly what is missing.

---

## 1. Workspaces tested

| # | Workspace | Vertical bucket | GSC | External market providers |
| --- | --- | --- | --- | --- |
| 1 | Example Lab (peptides) | Research / regulated | off | off (internal-context only) |

Target mix from the validation plan (≥7 workspaces, ≥4 verticals, ≥2 without GSC): **not met** (1 workspace, 1 vertical).

## 2. Per-workspace metrics — Example Lab

Final run after Part 1 cleanup: `docs/validation/runs/2026-06-01T120021Z/`.

| Metric | Value |
| --- | --- |
| Recommendations (total) | 80 (create 19, monitor 60, merge 1) |
| Top-25 actions | create 19, monitor 6 |
| **Publishable rate (top 25, human est.)** | **~68–72%** |
| **Junk rate** | **0% automated / ~4% human** (1 item: `bactriostatic` typo) |
| **Content-type diversity (creates)** | **4 types** — educational_guide 6, beginner_guide 6, glossary 6, faq 1 |
| **Max content-type share** | **24%** |
| Market-led CREATE share | 100% |
| Explainability pass (automated) | 100% |
| False "competitor evidence" | 0/80 |
| Funnel (signals→candidates→recs) | 500 → 500 → 80 |

Content-type distribution (top-25 creates): `educational_guide 24%, beginner_guide 24%, glossary 24%, faq 4%`, remainder monitors. Titles vary by format (*"How Researchers Approach BPC-157"*, *"Introduction to angiogenesis for New Readers"*, *"What Is autophagy? Research Overview"*, *"CJC-1295 Frequently Asked Questions"*).

### Recommendation-quality progression (Example Lab, all deterministic passes)

| Run | Stage | Content types | Max share | Junk (human) | Publishable |
| --- | --- | --- | --- | --- | --- |
| `083533Z` | pre-Pass-1 | 1 | 100% | ~44% | ~36% |
| `112607Z` | Pass 1 | ~2 | ~60% | ~24% | ~50% |
| `114544Z` | Pass 2 | 4 | 28% | ~12% | ~64–72% |
| **`120021Z`** | **Validation-Expansion Part 1** | **4** | **24%** | **~4%** | **~68–72%** |

## 3. Cross-workspace comparison

**Not possible (N=1).** A cross-vertical comparison requires ≥2 verticals; only peptides is available. No medians, deltas, or variance across verticals can be computed.

## 4. Failure patterns (single workspace only)

| Pattern | Status after Part 1 | Notes |
| --- | --- | --- |
| Content-type monoculture | Fixed | 4 types, 24% max (was 100% glossary) |
| Brand/nav as CREATE | Fixed | brand is a monitor; nav reframing removed |
| Audience-suffix seeds (`{niche} guide for {audience}`) | Fixed | construction removed upstream |
| Coverage nav labels (`Monitor: Shop`) | Fixed | coverage source now fragment/nav filtered |
| Orphan fragments (`cellular` from "cellular stress") | Fixed | dropped at entity ingress and EOG seed ingress |
| Generic structural tokens (`Product`, `Research`, `Laboratory`, `customer`…) | Fixed | shared `is_generic_fragment` |
| False competitor evidence | Fixed | gated on real competitor lineage |
| **Typo entities (`bactriostatic`)** | **Residual** | plausible misspelling; see §5 |

## 5. Common deterministic weaknesses (remaining)

1. **Plausible-looking misspellings are not deterministically detectable.** `bactriostatic` (for "bacteriostatic") survives. The orthographic gate (`is_implausible_token`) is intentionally conservative — a general English dictionary would *wrongly reject* valid domain entities (`angiogenesis`, `autophagy`, `BPC-157`), which are precisely not dictionary words. Reliable correction needs a **domain lexicon** (future deterministic option) or an **LLM** (Phase 2). This is the canonical residual.
2. **Templated phrasing.** Titles are now format-diverse but still pattern-generated (*"How Researchers Approach X"*, *"Introduction to X for New Readers"*). Varying *voice/angle* within a format is not something deterministic rules improve meaningfully.
3. **CREATE breadth vs diversity tradeoff.** The per-topic content-type balancer yields ~19 strong, diverse creates (down from 63 repetitive ones); other formats remain in the finalist backlog. Intended, but worth revisiting if more CREATE volume is wanted.

## 6. Vertical-specific weaknesses

**Cannot be assessed.** Vertical-specific failure modes (e.g. nav-label risk on ecommerce, thin content on local services, authority clusters on B2B/SaaS) require those verticals in the dataset. The peptides workspace exercises only the research/regulated path. The architecture contains **no niche-specific branches**, so there are no *known* vertical-specific code paths — but absence of vertical-specific logic is not the same as evidence of vertical-specific quality.

## 7. Does EOG generalize? — Architecture vs evidence

Distinguish two claims:

| Claim | Verdict | Basis |
| --- | --- | --- |
| The architecture is **vertical-agnostic by construction** | **Yes** | All filters/scoring are generic; no hardcoded niche terms; content types are intent-driven from data; `is_generic_fragment`/orphan/variant rules are lexical, not niche-specific. |
| The engine **empirically produces similar quality across multiple verticals** | **Not demonstrated** | Only one vertical (peptides) has data. No cross-vertical evidence exists. |

The design *should* generalize, but "should" is a prior, not a measurement.

## 8. Remaining deterministic opportunities

- **Domain-lexicon typo gate** (deterministic, no LLM): validate single-token entities against a niche-derived term frequency / known-entity corroboration list rather than a general dictionary. Would address `bactriostatic` without over-filtering.
- **Coverage/competitor source parity:** extend orphan-fragment filtering to the competitor and trend candidate sources for consistency (low impact on current data).
- **CREATE-breadth knob:** optionally allow 2 balanced formats per top topic when more volume is desired.

## 9. Has the deterministic ceiling been reached?

- **For a single vertical, on measurable axes: effectively yes.** Diversity (4 types, 24% max), junk (0% automated / ~4% human), evidence honesty, and ranking collapse are all resolved. The remaining within-vertical residual (`bactriostatic`) is a known data-quality edge case, not a systemic flaw.
- **Cohort-wide: unknown.** The ceiling cannot be declared reached across verticals because the cohort does not exist yet.

## 10. Is Phase 2 AI now justified?

**No — the precondition is not met.** Phase 2 may be recommended *only if* multi-vertical validation is **successful**. It has not been **run**, because the data does not exist. We cannot certify generalization, so we cannot certify that the remaining gaps are "primarily editorial phrasing/angle/voice" across verticals. Phrasing nuance is the most likely next lever *on the one workspace we have*, but generalizing that conclusion is unproven.

---

## Critical question — answered explicitly

> **Have we demonstrated that deterministic EOG quality generalizes across multiple verticals?**

**No.**

What we have: strong, repeatable quality on **one** vertical (peptides) after four deterministic passes — diverse content types, ~0–4% junk, honest evidence, ~68–72% publishable, no single content type >40%.

What is missing to answer "yes":
1. **≥2 additional verticals** with data (target buckets: SaaS/software, local business, ecommerce, content site). None exist in the database.
2. **Comparable runs** (same analyze → market → EOG → OI pipeline) per vertical.
3. **Cross-vertical metrics**: publishable rate, junk rate, content-type diversity, and failure-tag distribution computed per vertical and compared (medians/variance).
4. **At least 2 workspaces without GSC** and a mix of business models, per the validation plan.

Until those exist, generalization is an architectural expectation, not a validated result.

---

## Phase 2 Decision

# A) Continue deterministic work

**Rationale:** The explicit gate for Option B — *successful multi-vertical validation* — cannot be satisfied with current data, so B is not eligible regardless of how good the single-vertical result is. The correct next investments are deterministic and data-gathering, not AI:

1. **Acquire ≥2–3 additional vertical workspaces** (real sites across SaaS/local/ecommerce/content) and run the validation script per vertical.
2. **Add the domain-lexicon typo gate** (deterministic) to close the `bactriostatic` class without over-filtering domain entities.
3. **Re-run cross-vertical validation** and populate §3/§6 with real comparison data.

Only after multi-vertical validation **passes** — and if the residual complaints are then genuinely about phrasing/angle/voice rather than filtering/dedupe/data-quality — should EOG Phase 2 AI refinement be designed. We are not there: not because the deterministic system is weak, but because generalization is **unproven for lack of data**, and one residual defect class (typos) still has a deterministic remedy (a lexicon) that has not been tried.

---

## Appendix — validation run lineage (no historical runs modified)

| Run ID | Purpose |
| --- | --- |
| `2026-06-01T083533Z` | Baseline EOG Phase 1 (pre-quality-passes) |
| `2026-06-01T112607Z` | EOG Quality Pass 1 |
| `2026-06-01T114544Z` | EOG Quality Pass 2 |
| `2026-06-01T115905Z` | Validation-Expansion Part 1 (coverage + entity-level fixes) |
| `2026-06-01T120021Z` | Validation-Expansion Part 1 final (seed-level orphan filter) — metrics in §2 |
