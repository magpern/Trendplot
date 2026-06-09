# Cross-Vertical Validation Report

**Date:** 2026-06-01
**Validation run ID:** `2026-06-01T125750Z`
**Scope:** Deterministic EOG/OI only. `EDITORIAL_GENERATOR_AI_ENABLED` remains disabled throughout. No architecture changes. No OI/EOG logic modified.

---

## 1. Executive verdict

**Cross-vertical generalization: FAILED.**

The deterministic EOG/OI engine, which performs well on the Example Lab peptide research workspace, produces output that is **predominantly unpublishable** on SaaS, ecommerce, local business, and content publisher verticals. Human-rated junk rates are 72–88% across all four new workspaces. The automated junk detection (NAV_BLOCKLIST) is blind to the dominant failure modes — it reports 0–4% junk while the human rate is 10–20× higher.

The root cause is not editorial phrasing or voice. It is **structural**: entity extraction on non-research websites ingests marketing copy, pricing values, navigation labels, CTA sentences, product names, and competitor UI text as domain entities. These invalid entities propagate through EOG, producing title templates applied to non-topics ("A Practical Guide to 150/year", "How Researchers Approach Shopping Bag", "Monitor: for").

Phase 2 AI refinement is not justified. The failure precedes the editorial layer.

---

## 2. Workspaces tested

| # | Workspace | Vertical | URL | Pages | Niche | Market signals | Recs |
|---|---|---|---|---|---|---|---|
| 1 | Example Lab *(reference)* | Research / peptides | example.com | — | peptides | 500 | 80 |
| 2 | Plausible Analytics | SaaS / software | plausible.io | 9 | software | 213 | 80 |
| 3 | Tortuga Backpacks | Ecommerce | tortugabackpacks.com | 16 | fashion | 112 | 80 |
| 4 | Denver Plumbing | Local business | denverplumbingconsultants.com | **4** | **generic** | 54 | **45** |
| 5 | Pragmatic Engineer | Content publisher | blog.pragmaticengineer.com | 16 | software | 234 | 80 |

---

## 3. Per-workspace metrics table

### Automated metrics (from validation script)

| Workspace | Total recs | Creates | Monitors | Concepts | Finalists | Junk (auto) | MI CREATE % | Explain % |
|---|---|---|---|---|---|---|---|---|
| Example Lab | 80 | 19 | 60 | 500 | 56 | 0% | 100% | 100% |
| Plausible | 80 | 64 | 0 | 237 | 165 | **4% (1 NAV)** | 100% | 100% |
| Tortuga | 80 | 39 | 0 | 114 | 85 | 0% | 100% | 100% |
| Denver | 45 | 14 | 11 | 42 | 39 | 0% | 100% | 100% |
| Pragmatic Eng | 80 | 64 | 0 | 183 | 135 | 0% | 100% | 100% |

### Human review metrics (top-25 manual assessment)

| Workspace | Publishable est. | Human junk | Strongest rec | Weakest rec | Dominant failure |
|---|---|---|---|---|---|
| Example Lab *(ref)* | ~68–72% | ~4% | BPC-157 guides, peptide glossary | `bactriostatic` (typo) | Plausible-misspelling (1 item) |
| Plausible | **~16–24%** | **~76–84%** | "What Is Compliance? Research Overview", "API comparison" | "A Practical Guide to 150/year", "Introduction to 2 MONTHS FREE" | Price/CTA fragments as topics |
| Tortuga | **~16–24%** | **~72–80%** | "Travel Backpacks" overview, "briefcases" guide | "How Researchers Approach Shopping Bag", "according" | Nav labels / product names as topics |
| Denver | **~8–16%** | **~80–88%** | "A Practical Guide to maintenance", "troubleshooting" | "Monitor: for", "Monitor: glossary", "Introduction to generic" | Generic single-word fragment topics |
| Pragmatic Eng | **~16–24%** | **~72–80%** | "Thoughtworks" overview, "When should we use Microservices?" | "Introduction to Don't have an InfoQ account?", "READ ME FIRST" | Competitor UI text scraped as entities |

---

## 4. Cross-vertical comparison

| Metric | Example Lab | Plausible | Tortuga | Denver | Pragmatic Eng | Gate |
|---|---|---|---|---|---|---|
| Human publishable rate | ~70% | ~20% | ~20% | ~12% | ~20% | ≥60% |
| Human junk rate | ~4% | ~80% | ~76% | ~84% | ~76% | ≤10% |
| Max content-type share (auto) | 24% | — | — | — | — | ≤40% |
| Automated junk rate | 0% | 4% | 0% | 0% | 0% | proxy only |
| Market-led CREATE share | 100% | 100% | 100% | 100% | 100% | ≥50% |
| Explainability pass rate | 100% | 100% | 100% | 100% | 100% | ≥80% |
| Niche detection correct | ✓ peptides | ✓ software | △ fashion* | **✗ generic** | ✓ software | — |

*"fashion" is debatable for travel backpacks; may be acceptable.

**Every generalization gate fails on human review.** The automated gates pass uniformly — this is evidence that the automated detection does not measure what matters.

---

## 5. Best-performing vertical

**Plausible Analytics (SaaS)** and **The Pragmatic Engineer (Publisher)** are roughly tied for best outside Example Lab. Both show a handful of publishable concepts in the top-25:

- Plausible: "What Is Compliance? Research Overview", "API comparison", "What Is Dashboard?"
- Pragmatic: "When should we use Microservices?", "Is High Quality Software Worth the Cost?", "What Is Automation?"

These verticals produce ~4–6 publishable titles per 25. The remaining ~19–21 are built on extracted fragments, price strings, or competitor navigation text.

**Rationale for ranking these as "best":** they have dense enough content that at least some real domain entities (Compliance, API, Microservices, Automation) survive extraction alongside the noise.

---

## 6. Worst-performing vertical

**Denver Plumbing Consultants (local business).**

- Only 4 pages crawled (sparse content site).
- Niche detection failed: returned `generic` instead of `plumbing`.
- 45 total recommendations (vs 80 for all other dense sites).
- The engine reached into the monitor queue and produced single-word monitoring topics: "Monitor: for", "Monitor: glossary", "Monitor: available", "Monitor: drain".
- The word "for" as a monitored topic is the canonical failure: a stop-word passed through the entity extractor and the orphan filter.
- Human publishable rate: ~8–16% (2–4 titles out of 25).

This vertical exposes a **minimum viable content threshold** that the engine currently lacks. Below ~8–10 content pages, entity quality degrades to the point where the pipeline produces meaningless output.

---

## 7. Does deterministic quality generalize?

**No.**

The quality seen on Example Lab (68–72% publishable, ~4% junk, 4 content types, domain-coherent entities) does **not** generalize to the four new verticals. The cross-vertical human junk rate is 72–88%. The cross-vertical publishable rate is 8–24%.

Architectural intent (vertical-agnostic pipeline) is correct — there are no hardcoded niche branches. However, architecture does not guarantee quality when the upstream data (entity extraction) produces fundamentally different inputs across verticals.

The performance gap is not due to the EOG/OI scoring logic. It is due to what enters the engine as seed entities.

---

## 8. Common failure modes across all new verticals

These patterns appear in all four new workspaces:

### F1 — Navigation labels and structural UI text as topics
- "Shopping Bag" (Tortuga #1), "Best Sellers" (Tortuga #2), "about me" (Pragmatic #4), "What we do" (Plausible #14)
- The existing NAV_BLOCKLIST catches "shop", "store", "contact" etc. but not open-ended nav labels extracted from header/footer text.

### F2 — Marketing and CTA copy as topics
- "Ready to simplify your analytics?" (Plausible #22), "Different. In a good way." (Plausible #24), "Unsure Which Bag is Right For You?" (Tortuga #4), "Bundle and Save" (Tortuga #17)
- CTA fragments are not currently in any filter.

### F3 — Pricing and promotional values as topics
- "15/month" (Plausible #8), "150/year" (Plausible #9), "2 MONTHS FREE" (Plausible #10)
- Pricing strings pass through entity extraction unchallenged.

### F4 — Generic single words below concept threshold
- "according" (Tortuga #15), "content" (Pragmatic #1), "beginner" (Denver #1), "generic" (Denver #12), "Official" (Tortuga #23), "Everyday" (Tortuga #20), "Trending" (Pragmatic #10)
- The single-token entity guard (`is_generic_fragment`) catches deterministic known-bad tokens but not arbitrary lowercase common words.

### F5 — Content-type templates misapplied to non-research entities
- Example Lab templates ("How Researchers Approach", "Understanding the Scientific Interest Around", "Current Research Areas Involving") produce absurd results when applied to non-research topics: "How Researchers Approach Shopping Bag", "Understanding the Scientific Interest Around according", "Current Research Areas Involving 15/month".
- These templates were calibrated for research/regulated niches. They generalize poorly to commercial and editorial verticals.

### F6 — Automated junk detection rate is too low (proxy gap)
- The automated `junk_rate` is 0–4% across all new workspaces. Human junk rate is 72–88%.
- The automated detector is useful for Example Lab-class failures (nav labels from a small blocklist) but does not measure the dominant failure modes (F1–F5 above).

---

## 9. Vertical-specific failure modes

### Ecommerce (Tortuga)
- **Product name injection**: Full product titles appear as topics — "Travel Backpack Pro 40L by Tortuga Award-Winning Carry On Bag" (rank 9). Product name/SKU scraping is not filtered.
- **Category and commerce navigation**: "Shopping", "Shopping Bag", "Best Sellers", "Collection", "Essentials", "Apparel" — ecommerce sites have rich category navigation that produces entity noise.
- **Competitor brand as topic**: "What Is NOMATIC? Research Overview" — NOMATIC is a competitor brand, correctly identified as entity, but wrongly templated as a glossary article. A competitor brand deserves a comparison article, not a "Research Overview".

### Local business (Denver)
- **Minimum content threshold breach**: 4 pages is insufficient for reliable entity extraction. The engine should gate analysis at a minimum page count and surface a warning to the user.
- **Niche detection failure at low content density**: `generic` niche returned at 0.75 confidence. Opportunity intelligence operating on a "generic" niche profile produces context-free recommendations.
- **Stop-word entities**: "for", "glossary", "available", "drain" — the last two are plausibly domain-relevant (drain, repair) but the first two are stop-words that should never appear as topics.

### SaaS / software (Plausible)
- **Pricing fragment entities**: Prices, subscription plans, and promotional CTAs are prominently displayed on SaaS landing pages and are extracted as entities.
- **Sentence fragments from marketing copy**: SaaS pages feature dense short copy phrases ("Where your data disappears", "This is how the gap shows up in real life") that look entity-like to the extractor.

### Content publisher (Pragmatic Engineer)
- **Competitor taxonomy as topics**: The infoq.com competitor site has structured content navigation ("Articles about Microservices", "Podcasts about Service Mesh", "Presentations about Microservices") — these are taxonomy labels scraped directly into recommendations.
- **Competitor registration UI**: "Don't have an InfoQ account?", "Unlock the full InfoQ experience" — competitor site login walls were scraped into the entity graph.
- **Competitor article titles as topics**: "Does My Bus Look Big in This?", "The Root Cause: The Perceptual Gap" — article titles from competitor pages were treated as domain entities and templated as new creation opportunities.

---

## 10. Has the deterministic ceiling been reached?

**No — for the wrong reason.**

The previous conclusion (after Example Lab passes) was that the deterministic ceiling had been reached *within a single vertical*. That conclusion was correct in its scope. This run confirms it cannot be generalized: the ceiling has not been reached *cohort-wide* because the engine degrades severely on non-research verticals.

The remaining work is not about squeezing marginal improvement from a well-functioning engine. It is about fixing a structural data quality problem: the entity extractor ingests the wrong inputs on web content that is not structured like a research/science website.

---

## 11. Is Phase 2 AI refinement now justified?

**No.**

Phase 2 AI refinement is designed to improve the *editorial quality* of recommendations that are structurally correct — phrasing, angle, voice. The recommendations on the new verticals are not structurally correct. The entities are wrong. Applying AI to "Introduction to 2 MONTHS FREE for New Readers" would produce a better-written recommendation for an unpublishable topic.

**Gate status (all must pass to qualify):**

| Gate | Requirement | Actual | Pass? |
|---|---|---|---|
| Publishable rate | ≥60% across verticals | ~8–24% | ✗ |
| Human junk rate | ≤10% across verticals | 72–88% | ✗ |
| Max content-type share | ≤40% | Not measured (all CREATE) | △ |
| Failures are editorial phrasing/voice | Must be true | **False — failures are structural** | ✗ |
| No major structural filtering/ranking issue | Must be true | **False — entity extraction fails** | ✗ |

No gate passes. Phase 2 is not eligible.

---

## 12. Recommended next milestone

**Milestone: Entity extraction hardening for non-research verticals**

The following deterministic fixes address the specific failure modes observed. All are implementable without AI:

### Priority 1 — Minimum content gate
- Block analysis (or surface a strong warning) when `analysis_pages` count < 8.
- For Denver-class sparse sites, return a "Insufficient content for reliable analysis" status rather than proceeding to recommendation generation on inadequate data.

### Priority 2 — Entity quality filters
- **Price/number filter**: Reject any candidate entity that matches `\d+[/€$£]\w*` or common pricing patterns ("X/month", "X/year", "X MONTHS FREE").
- **CTA/question filter**: Reject entities that are imperative sentences or questions (end with `?`, contain "Don't", "Ready to", "Start here").
- **Fragment-at-word-boundary filter**: Reject entities that are a single common English word with no capitalisation and no domain context (extend `is_generic_fragment` with a stop-word list).
- **Competitor UI filter**: Track whether an entity was extracted from the main site vs. competitor pages; apply stricter filtering to competitor-sourced entities to prevent registration prompts and taxonomy labels from entering the seed set.

### Priority 3 — Template generalization
- The research-specific templates ("How Researchers Approach", "Understanding the Scientific Interest Around", "Current Research Areas Involving") are inappropriate for non-research niches.
- Add niche-conditioned template selection: research/regulated → current templates; software/SaaS → "How to" / "Why" / "Complete Guide to"; ecommerce → buyer guides, comparisons; local → FAQ and service explainers.
- This change is deterministic (rule-based template mapping by detected niche type).

### Priority 4 — NAV_BLOCKLIST expansion
- Add commerce-specific terms: "shopping bag", "best sellers", "bundle and save", "collection", "essentials", "official".
- Add UI-specific terms: "account", "sign up", "unlock", "read me first", "trending".

### Priority 5 — Product name deduplication
- Detect when an entity is a full product name (contains brand name + SKU pattern + descriptors) and convert to a comparison-article candidate rather than a glossary or research article.

### Re-validation target after fixes
- Re-run analysis on the same 4 workspaces after deterministic entity fixes are applied.
- Human review of top-25 per workspace.
- Gate: ≥60% publishable on ≥3 of 4 new verticals before any further gate evaluation.

---

## Explicit answers

### Has Trendplot demonstrated cross-vertical generalization?

**No.**

Example Lab produces high-quality output (~70% publishable, ~4% junk). The four new verticals produce predominantly unpublishable output (8–24% publishable, 72–88% human junk). The failure mode is systematic (entity extraction), not random. Generalization has not been demonstrated.

---

# A) Continue deterministic work

**Rationale:** Phase 2 AI refinement requires (1) generalization validated, (2) remaining failures to be editorial in nature, and (3) deterministic remedies exhausted. None of these conditions are met. The failures observed are structural (wrong entities), not stylistic (wrong phrasing). There are at least four deterministic fixes with high expected impact (price filter, CTA filter, template selection by niche, NAV_BLOCKLIST expansion) that have not been implemented.

Option B is not eligible.

---

## Appendix — Validation run lineage

| Run ID | Purpose |
|---|---|
| `2026-06-01T083533Z` | Example Lab baseline (pre-quality passes) |
| `2026-06-01T112607Z` | Example Lab EOG Quality Pass 1 |
| `2026-06-01T114544Z` | Example Lab EOG Quality Pass 2 |
| `2026-06-01T115905Z` | Example Lab Validation-Expansion Part 1 |
| `2026-06-01T120021Z` | Example Lab Validation-Expansion Part 1 final |
| **`2026-06-01T125750Z`** | **Cross-vertical validation — 5 workspaces (Example Lab + 4 new)** |

No previous run files were modified.
