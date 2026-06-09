# Generalization Readiness Report

**Date:** 2026-06-01
**Purpose:** Part 4 — state what evidence exists, what is missing, and what the minimum dataset is to justify each gate.

---

## 1. What evidence currently exists?

| Dimension | Evidence | Source |
|---|---|---|
| Engine produces output | Yes | 80 recommendations across create/monitor/merge |
| Content-type diversity | Yes — 4 types, max 24% share | Example Lab runs |
| Low automated junk rate | Yes — 0% automated | Example Lab `2026-06-01T120021Z` |
| Low human junk rate | Yes — ~4% (1 item: `bactriostatic`) | Human review of Example Lab top-25 |
| High publishable rate | Yes — ~68–72% estimated | Human review of Example Lab top-25 |
| Explainability | Yes — 100% automated pass | Example Lab run |
| Evidence honesty | Yes — 0 false competitor references | Example Lab run |
| Recommendation progression | Yes — 4 deterministic passes, measurable improvement | Run lineage in MULTI_VERTICAL report |
| Cross-vertical quality | **No** | Only one vertical in database |
| Vertical-specific failure modes | **No** | Cannot assess without multi-vertical data |
| GSC-off workspace behavior | **No** (Example Lab has no GSC, but all workspaces have no GSC — there is no contrast) | N/A |
| Sparse-niche behavior | **No** | Peptides is a medium-density niche |

---

## 2. What evidence is missing?

### Missing: cross-vertical quality data

The following buckets have zero workspaces and zero runs:

- SaaS / software
- Ecommerce / physical product
- Local business / lead-gen
- Content site / publisher
- B2B professional services

Without data from these buckets, the following questions cannot be answered:

- Does the nav-label filter generalize to ecommerce category pages?
- Does the orphan-fragment filter generalize to technical software entity graphs?
- Does the content-type balancer produce sensible output when niche entities are sparse (local business)?
- Is the junk rate consistently <10% across verticals, or is Example Lab an outlier?
- Is the publishable rate consistently >60% across verticals?

### Missing: variance measurement

With N=1, there is no variance. The metrics from Example Lab could represent:

- The typical output of the engine (i.e., it generalizes well), or
- An unusually good outcome for a structured research niche

A minimum of 3 workspaces is required to distinguish these hypotheses.

### Missing: sparse-signal path evidence

The Example Lab workspace has a well-crawled site with dense entity coverage. The engine's behavior when competitor crawls produce few pages, or when the niche has few internal entities, has not been observed.

---

## 3. Minimum dataset to justify: "Trendplot generalizes"

All of the following must be true:

- **≥3 additional verticals** with completed analysis runs (target: SaaS, ecommerce, local business)
- **Per vertical**: ≥1 workspace with `status = analyzed`, with a `top25_analysis.json` produced by the validation script
- **Cross-vertical metrics** (computed, not estimated):
  - Median publishable rate across all workspaces: **≥60%**
  - Median automated junk rate: **≤10%**
  - No single vertical with automated junk rate >20%
  - Content-type max share: **≤40%** in all workspaces
  - Market-led CREATE share: **≥50%** in all workspaces
- **Human review completed** for top-25 per workspace, using the same rubric applied to Example Lab
- **No systematic vertical-specific failure** that the deterministic engine cannot address

If any of the above conditions is not met, generalization remains an architectural expectation, not a validated result.

---

## 4. Minimum dataset to justify: "Begin EOG Phase 2 AI refinement"

Phase 2 AI refinement requires a *stronger* gate than generalization, because:

- AI refinement addresses phrasing/angle/voice — the residual complaint after the deterministic system is working
- If the engine has systematic deterministic failures in new verticals, those are not an AI problem — they are a filtering/scoring problem
- Building AI on top of an unvalidated deterministic base creates compounding uncertainty

The preconditions for Phase 2 are:

1. **Multi-vertical validation passed** (all conditions in §3 above met)
2. **The remaining failure class is genuinely editorial**, not structural: the dominant human-rated complaint across verticals must be phrasing/angle/voice, not wrong recommendations, wrong entities, or navigation artifacts
3. **The domain-lexicon typo gate** (deterministic remedy for `bactriostatic`-class misspellings) has been implemented and evaluated — this is a deterministic fix that should precede AI investment
4. At least one workspace where the human-rated publishable rate is **constrained by phrasing**, not by other factors (this distinguishes "AI would help" from "more rules would help")

**Current status:** Precondition 1 is not met (insufficient data). Precondition 3 is not met (lexicon not implemented). Phase 2 is not eligible.

---

## 5. Recommended next milestone

**Milestone: 3-vertical validation cohort**

Target completion: complete analysis and human review of 3 new workspaces (SaaS, ecommerce, local business) using the plan in [VALIDATION_DATASET_PLAN.md](VALIDATION_DATASET_PLAN.md).

Success criteria:
- All 3 workspaces reach `status = analyzed`
- Validation script produces `top25_analysis.json` for each
- Human review completed for each (top-25 rated publishable/junk/needs-edit)
- Cross-vertical metrics computed and recorded in a new validation run report

This milestone unblocks the generalization claim if all 3 pass the §3 thresholds, or identifies the first cross-vertical failure mode if they do not. Either outcome is progress.

---

## Decision

# A) Acquire validation data

**Rationale:**

The evidence base is one vertical. The generalization gate requires at minimum three. There is no shortcut: the claim "Trendplot generalizes" cannot be made from the data that currently exists, regardless of the quality of the single-vertical result.

The correct next investment is:

1. Onboard 3 real websites from distinct buckets (SaaS, ecommerce, local business)
2. Run the analysis pipeline for each
3. Run the validation script and complete human review
4. Compute cross-vertical metrics

Only after that is complete — and only if the metrics pass — is the generalization gate open. Only after the generalization gate is open, and the remaining failure class is confirmed to be editorial phrasing rather than structural filtering, should Phase 2 AI refinement be designed.

Option B (Phase 2 AI design) is not eligible. The precondition has not been met.
