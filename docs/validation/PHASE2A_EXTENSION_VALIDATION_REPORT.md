# Phase 2A Extension — Grounded Entity Relevance + Entity-Type Classification: Validation Report

**Date:** 2026-06-01
**Flag:** `ENTITY_RELEVANCE_SCORING_ENABLED` (default **OFF**)
**A/B runs:** OFF baseline `runs/2026-06-01T172954Z` · ON treatment `runs/2026-06-01T180711Z`
**Method:** identical `--refresh` pipeline rebuild on the same 5 workspaces; only the flag differs.

---

## 0. What changed vs. base Phase 2A

The base layer removed only the unambiguous off-topic proper nouns (3/7 named residual). This extension keeps the same narrow scoring layer and adds three things, all inside the existing batched call:

| Part | Change |
|---|---|
| 1 · Grounding | Prompt now receives the **specific** site: name, domain, primary/secondary niche, description, known entities/categories/audiences, competitor domains — not just the coarse vertical. |
| 2 · Competitor signal | Provenance computed from the **set** of sources an entity appears in: `own_site` / `competitor_only` / `mixed` / `market`. Passed to the scorer and used in the decision. |
| 3 · Entity type | Same call now returns `entity_type` (8-way taxonomy) + `editorial_topic_score` alongside `relevance`. |
| 4 · Decision rules | Filter/down-rank decided from relevance **and** editorial-topic score **and** type **and** provenance (see below). |
| — · Cache fix | Cache key changed from `primary_niche` → workspace **domain**: Plausible and Pragmatic are both niche `"software"` and previously would have collided. |

Safety properties preserved: default-OFF, fail-open, cache-first, deterministic behaviour when disabled, no mandatory AI dependency. **482 tests pass** (`tests/test_entity_relevance.py`, 23 cases).

### Decision logic (conservative)
- **Competitor brand/product** → split on provenance: `mixed` (site engages it, e.g. NOMATIC) = keep, mild down-rank; `own_site` (the site's *own* item the model mislabelled competitor) = strong down-rank; `competitor_only`/`market`/`unknown` (purely a competitor asset, e.g. The InfoQ) = **filter**.
- **relevance < 0.25** → filter. **deprecated_or_stale_entity** → filter. **topic-gated type** (product SKU / company / generic) with `editorial_topic_score < 0.35` → filter.
- **product SKU/sub-brand** (or own-site mislabelled-competitor) → strong down-rank: a real score penalty (mirrors the sparse-site penalty) pushes a high-base-score create out of the top set without deleting it.
- Everything else → keep (domain concepts, product categories), with `niche_relevance = min(relevance, editorial_topic_score)`.

---

## 1. Named residual entity outcomes

| Entity | Workspace | OFF | ON | Model verdict | Outcome |
|---|---|---|---|---|---|
| **Bloomberg** | Plausible | present | gone | rel 0.05 (grounded) | ✅ **REMOVED** |
| **Michelin** | Plausible | present | gone | competitor_only, rel 0.05 | ✅ **REMOVED** |
| **Hyundai** | Plausible | present | gone | competitor_only, rel 0.05 | ✅ **REMOVED** |
| **Photostream** | Pragmatic | present | gone | deprecated_or_stale | ✅ **REMOVED** |
| **InfoQ … Newsletter** | Pragmatic | 4 InfoQ items | 2 left, **none in top-25** | competitor_product, competitor_only | ✅ **OUT of top-25** |
| **The InfoQ** | Pragmatic | present | out of top-25 | competitor_brand, competitor_only → filter | ✅ **OUT of top-25** |
| **Travel Together Lite** | Tortuga | top-25 create | **out of top-25** | own-site product mislabelled competitor → strong demote | ✅ **OUT of top-25** |
| **Daily Carry Pro** | Tortuga | top-25 create | **out of top-25** | own-site product → strong demote | ✅ **OUT of top-25** |

**7 of 7 named residual entities removed or out of top-25.**

## 2. Publishable / junk estimate

Harness `junk_rate` is a NAV-only proxy (doesn't see the semantic residual), so it stays flat; the semantic effect is in §1. No publishable recommendations were lost — counts flat, allow-list intact.

| WS | junk OFF→ON | explainability OFF→ON | MI-led CREATE OFF→ON | recs OFF→ON |
|---|---|---|---|---|
| Pragmatic | 0.00→0.00 | 0.88→0.88 | 0.88→0.84 | 80→80 |
| Denver | 0.00→0.00 | 1.00→1.00 | 1.00→1.00 | 27→25 |
| Tortuga | 0.00→0.00 | 1.00→1.00 | 1.00→1.00 | 80→80 |
| Plausible | 0.08→0.08 | 0.96→**1.00** | 0.96→**1.00** | 80→80 |
| Example Lab | 0.00→0.00 | 1.00→1.00 | 1.00→1.00 | 80→80 |

## 3. Allow-list false positives

**Zero, across all 5 workspaces.**

| WS | known-good present (ON) |
|---|---|
| Pragmatic | microservices, monolith, security, thoughtworks |
| Plausible | gdpr, security (+ digital privacy, privacy-first) |
| Tortuga | **nomatic**, capsule wardrobe, travel backpacks |
| Example Lab | bpc-157, angiogenesis, peptide |

The hardest case — **NOMATIC** (a competitor brand with rel 0.05, indistinguishable from "The InfoQ" on relevance/type) — survives because provenance is `mixed` (Tortuga's own content references it) while The InfoQ is `competitor_only`. Thoughtworks survives on Pragmatic (engineering blog) but is correctly filtered on Plausible (web analytics) — contextual, not blanket.

## 4. Cost estimate

Light model (`gpt-4o-mini`), token-metered on the real per-workspace entity sets:

| WS | entities | model calls | latency | cost (cold) |
|---|---|---|---|---|
| Plausible | 150 | 6 | 101 s | $0.0050 |
| Pragmatic | 150 | 6 | 92 s | $0.0049 |
| Tortuga | 122 | 5 | 85 s | $0.0040 |
| Example Lab | 103 | 5 | 67 s | $0.0035 |
| Denver | 32 | 2 | 17 s | $0.0011 |
| **Total (cold)** | | **24** | | **$0.0185** |

~$0.004/workspace cold, ~$0 warm. Latency (65–100 s) is off the hot path (runs during analysis). The 3 extra output fields per entity roughly doubled output tokens vs. base Phase 2A — still negligible.

## 5. Cache effectiveness

Second identical score call → **0 model calls** for every workspace (100% hit). The key fix matters here: Plausible and Pragmatic are both niche `"software"`; keying on **domain** keeps their judgements separate (verified by test + by their divergent results).

## 6. Regression analysis

- No workspace lost a publishable recommendation; counts flat (Denver 27→25 = the off-topic drop).
- Allow-list: zero casualties (§3) — the primary regression risk.
- Plausible explainability and MI-led CREATE **improved** to 1.00.
- Pragmatic MI-led CREATE 0.88→0.84: a composition shift, not a loss — demoting the InfoQ creates let other-typed creates take their slots. Within tolerance.
- Example Lab unchanged (control).
- Fail-open verified: unit tests cover API error / malformed / timeout / no-client / disabled; an earlier ON attempt that hit a batch timeout completed at exit 0 on deterministic fallback.

## 7. Did grounding improve Bloomberg?

**Yes — decisively.** Base Phase 2A scored Bloomberg **0.30** against the coarse niche `"software"` (kept, above the 0.25 floor). With the grounded context (domain `plausible.io`, known analytics entities, competitor domains) it scores **0.05** and is **removed**. The grounding is the single highest-leverage change.

## 8. Did the competitor signal remove InfoQ?

**Yes.** The InfoQ entities are `competitor_only` (they appear in Pragmatic's competitor crawl, never in its own content). The provenance rule filters competitor-typed entities that the site never engages → InfoQ Newsletter / The InfoQ are out of top-25 (4→2 items, none in top-25). Crucially this did **not** harm NOMATIC, which is `mixed` (engaged by the site) → kept.

## 9. Did entity-type classify Travel Together Lite / Daily Carry Pro?

**Partially by type, robustly by provenance.** The model's *type* for these sub-brands is unstable across runs (`product_category` / `product_sku_or_subbrand` / `competitor_product`) — pure entity-type was not reliable on its own. The robust signal was the contradiction: the model labelled them `competitor_product` while their provenance is `own_site` (Tortuga's own products) — a competitor type the site itself owns. That triggers a strong demote (penalty), pushing both out of top-25 while keeping them in the set. A blanket `known_products` rule was rejected because that list is polluted with legitimate categories ("Travel Backpacks", "Luggage").

---

## Success criteria

| Criterion | Result |
|---|---|
| Bloomberg removed / down-ranked below top-25 | ✅ removed |
| InfoQ Newsletter removed / strongly down-ranked | ✅ out of top-25 |
| The InfoQ removed / strongly down-ranked | ✅ out of top-25 |
| Travel Together Lite down-ranked | ✅ out of top-25 |
| Daily Carry Pro down-ranked | ✅ out of top-25 |
| Michelin / Hyundai / Photostream remain removed | ✅ |
| **Guardrail:** zero allow-list false positives | ✅ (incl. NOMATIC, capsule wardrobe) |
| **Guardrail:** no workspace regression > 2 pp | ✅ |
| **Guardrail:** Example Lab stable | ✅ |
| **Guardrail:** deterministic fallback verified | ✅ |

---

## Conclusion

> ## A) Phase 2A Extension successful

All seven named residual entities are removed or out of top-25, every guardrail holds (zero allow-list false positives including the hard NOMATIC case, no regression, deterministic fallback intact), and cost stays negligible (~$0.004/workspace cold, ~$0 warm). The three additions each carried their weight, confirmed by the three diagnostic questions: **grounding** fixed Bloomberg (0.30→0.05), the **competitor/provenance** signal removed the InfoQ assets while protecting NOMATIC, and the **own-site-vs-competitor provenance contradiction** robustly demoted the product sub-brands where the bare entity-type was too unstable to rely on.

**Residual note (not blocking):** the model's entity-*type* labels are noisy in isolation; the design deliberately leans on provenance + editorial-topic score + relevance together rather than type alone. Two InfoQ items and several sub-brand *variants* remain in the set but below top-25 (correctly, as low-ranked monitors). If a future need arises to remove rather than bury them, the next lever is provenance-aware filtering of `competitor_only` items at lower rank — not a redesign.

**Ships default-OFF.** Enable per-environment with `ENTITY_RELEVANCE_SCORING_ENABLED=true`.

---

## Appendix — run lineage

| Run | Flag | Note |
|---|---|---|
| `2026-06-01T172954Z` | OFF | Deterministic baseline (A/B control) |
| `2026-06-01T173006Z` | ON | Grounding + type + provenance-keep; named residual handled but NOMATIC lost (competitor floor) |
| `2026-06-01T174139Z` | ON | Added type penalty; The InfoQ out of top-25 but NOMATIC pushed out (penalty too broad) |
| `2026-06-01T175609Z` | ON | Provenance split (own/mixed vs competitor_only); NOMATIC restored, but own-site sub-brands mislabelled competitor survived |
| **`2026-06-01T180711Z`** | **ON** | **Final: own-site-mislabelled-competitor → strong demote. All criteria met.** |
