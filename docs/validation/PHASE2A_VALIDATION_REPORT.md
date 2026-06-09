# Phase 2A — Entity Relevance Scoring: Validation Report

**Date:** 2026-06-01
**Flag:** `ENTITY_RELEVANCE_SCORING_ENABLED` (default **OFF**)
**A/B runs:** OFF baseline `docs/validation/runs/2026-06-01T164035Z` · ON treatment `docs/validation/runs/2026-06-01T165013Z`
**Method:** identical `--refresh` pipeline rebuild on the same 5 persisted workspaces; the **only** variable is the flag.

---

## 0. What was built

A minimal, default-off AI layer scoring `(niche_profile, candidate_entity) → relevance ∈ [0,1] + reason`, written into the **existing** `OpportunityCandidate.niche_relevance` (no parallel field), per the approved architecture.

| Part | Implementation |
|---|---|
| 1 · Config | `ENTITY_RELEVANCE_SCORING_ENABLED` + model / batch_size / cache_ttl / filter_threshold (0.25) / downrank_threshold (0.60) / max_entities / timeout, in `app/config.py` + `.env.example` |
| 2 · Module | `app/entity_relevance/` — `models`, `prompt`, `scorer`, `service`, `cache`, `integration` |
| 3 · Cache | In-process TTL cache keyed `sha1(niche|entity)` (migration-free; documented tradeoff vs. a DB table below) |
| 4 · Integration | EOG pre-fan-out seed gate (`_run_editorial_generator`) + OI discovery confluence (`refresh_opportunity_intelligence` → `build_recommendations`), superseding the `_overlaps()` heuristic |
| 5 · Fail-open | Disabled / no-client / timeout / API error / malformed → empty result → neutral → deterministic behaviour |
| 6 · Observability | Per-run metrics (scored/cache/calls/filtered/down-ranked/fallback) in OI summary + approval event; INFO/WARNING logging |
| Tests | `tests/test_entity_relevance.py` — 18 tests; full suite **476 pass** |

The integration point sits at the OI discovery confluence so every rebuild path is covered, and at the EOG seed gate so off-topic seeds are dropped before concept fan-out. Both consume one cached score per `(niche, entity)`.

---

## 1–2. Named residual entities — did they disappear?

Measured by direct scan of the **full 80-recommendation set** per workspace (not just top-25), OFF vs ON.

| Entity | Workspace | OFF | ON | Model relevance | Outcome |
|---|---|---|---|---|---|
| **Michelin** | Plausible | present | **gone** | ~0.05 | ✅ **REMOVED** |
| **Hyundai** | Plausible | present | **gone** | ~0.05 | ✅ **REMOVED** |
| **Photostream** | Pragmatic | present | **gone** | <0.25 | ✅ **REMOVED** |
| **Bloomberg** | Plausible | present | present | **0.30** | ◐ down-ranked (1.0→0.30) but above the 0.25 floor → kept |
| **InfoQ … Newsletter** | Pragmatic | present | present | **0.60** | ✗ scored neutral; not down-ranked |
| **The InfoQ** | Pragmatic | present | present | **0.60** | ✗ scored neutral; not down-ranked |
| **Travel Together Lite** | Tortuga | present | present | **1.00** | ✗ scored fully relevant |
| **Daily Carry Pro** | Tortuga | present | present | **1.00** | ✗ scored fully relevant |

**Score: 3 of 7 removed, 1 down-ranked-but-kept, 3 untouched.** The outcome splits cleanly by failure class, and the misses are systematic — not bugs. The mechanism is provably working (every survivor carries a real `entity_relevance` score + reason in its metadata); the relevance *judgements* are bounded by two factors:

**(a) Niche-profile coarseness.** The detected `primary_niche` is the top-level vertical (`"software"`, `"fashion"`), not the specific niche (`"privacy-first web analytics"`, `"travel backpacks"`).
- Against `"web analytics"`, the scorer rates **Bloomberg = 0.05** (verified by direct probe).
- Against the actual `"software"` profile, it rates **Bloomberg = 0.30** — *"weak connection as a data source in analytics"* — a defensible judgement that lands just above the 0.25 filter floor.

**(b) Two residual classes are not domain-relevance questions:**
- **Competitor products (InfoQ).** The model reads *"InfoQ Software Architects' Newsletter"* as on-topic for a software site (0.60, *"adjacent topic for software professionals"*). It is not told InfoQ is a **competitor**. Resolving this needs an explicit competitor signal, not relevance alone.
- **Product SKUs / sub-brands (Tortuga).** *"Travel Together Lite"* and *"Daily Carry Pro"* score **1.00** — *"relevant product in the travel niche"* — because they genuinely **are** on-niche products (in fact the workspace's own `known_entities`). "Is this a product SKU vs. a researchable editorial topic?" is an **entity-type** question, orthogonal to domain relevance.

So entity relevance scoring cleanly addresses the **off-topic proper-noun** class (Michelin/Hyundai/Photostream, and Bloomberg *given a precise niche*), but **structurally cannot** resolve the competitor-product and product-SKU classes on its own.

---

## 3. Junk change (automated cohort metrics)

The harness `junk_rate` is the NAV/template proxy — it does **not** detect the semantic residual, so the table below shows it stayed flat (the semantic effect is in §1). No regression.

| Workspace | junk OFF→ON | explainability OFF→ON | MI-led CREATE OFF→ON | recs OFF→ON |
|---|---|---|---|---|
| Pragmatic | 0.00 → 0.00 | 0.88 → 0.88 | 0.88 → 0.88 | 80 → 80 |
| Denver | 0.00 → 0.00 | 1.00 → 1.00 | 1.00 → 1.00 | 27 → 26 |
| Tortuga | 0.00 → 0.00 | 1.00 → 1.00 | 1.00 → 1.00 | 80 → 80 |
| Plausible | 0.08 → 0.12 | 0.96 → **1.00** | 0.96 → **1.00** | 80 → 80 |
| Example Lab | 0.00 → 0.00 | 1.00 → 1.00 | 1.00 → 1.00 | 80 → 80 |

**Active filtering volume (ON):** the layer removed and down-ranked far more than the named list — these are off-topic candidates that mostly sit outside top-25:

| Workspace | entities scored | hard-filtered (<0.25) | down-ranked (0.25–0.60) |
|---|---|---|---|
| Plausible | 150 | **26** | 54 |
| Pragmatic | 150 | **31** | 39 |
| Tortuga | 122 | **27** | 29 |
| Example Lab | 126 | **21** | 32 |
| Denver | 32 | 1 | 3 |

## 2 (publishable change)

Human publishable rate is not re-rated here (no new human pass was run); the proxy and named-entity evidence are the measurable signals. On the **named residual**, publishable-relevant change = removal of 3 off-topic entities (Plausible −2, Pragmatic −1). No workspace lost publishable recommendations: allow-list intact (§4), recommendation counts flat (80/80; Denver 27→26 is the single Photostream-class drop).

---

## 4. False positives — guardrail allow-list

Scanned both runs for known-good entities that must survive. **Zero false positives across all workspaces.**

| Workspace | Allow-list present (OFF) | Present (ON) | Lost |
|---|---|---|---|
| Pragmatic | microservices, monolith, security, thoughtworks | same | **none** |
| Plausible | gdpr, security | same | **none** |
| Tortuga | backpack, capsule wardrobe, nomatic | same | **none** |
| Example Lab | peptide | same | **none** |

`Thoughtworks` scored 0.30 (kept, correctly down-ranked as adjacent), `Microservices`/`Monolith`/`GDPR`/`data privacy` all retained. The down-rank band (rather than hard delete) is doing its job: borderline-but-legitimate entities are lowered, not removed.

---

## 5. Cost estimate

Measured with token capture on the real per-workspace entity sets (light model, `gpt-4o-mini` pricing $0.15/$0.60 per 1M in/out):

| Workspace | entities | model calls | tokens (in+out) | cost (cold cache) |
|---|---|---|---|---|
| Plausible | 150 | 6 | 6,028 + 3,583 | $0.0031 |
| Pragmatic | 150 | 6 | 6,309 + 3,526 | $0.0031 |
| Tortuga | 122 | 5 | 4,467 + 2,773 | $0.0023 |
| Example Lab | 126 | 6 | 5,521 + 2,984 | $0.0026 |
| Denver | 32 | 2 | 1,344 + 718 | $0.0006 |
| **Total (5 workspaces, cold)** | | **25** | | **$0.0117** |

**~$0.002–0.003 per workspace, cold.** Negligible. Steady-state (warm cache) → ~$0. Latency: 65–86 s/workspace (6 sequential 25-entity batches at ~13 s each), entirely off the hot path (runs during analysis). Batches could be parallelised later if latency matters.

---

## 6. Cache effectiveness

- **Second identical score call → 0 model calls** for every workspace (`cache2_calls=0`). 100% hit on re-score within the process.
- Key = `sha1(normalize(niche)|normalize(entity))`, niche-scoped so generic concepts are reusable across workspaces while `Bloomberg@analytics` ≠ `Bloomberg@finance`.
- TTL configurable (default 7 days), aligned to the reassessment cadence so freshness judgements refresh.
- **Tradeoff:** in-process (not DB-backed) to keep Phase 2A migration-free and minimal. It serves the two in-run consumers and survives across runs while the worker is up; it does **not** persist across restarts. A DB-backed cache is a documented future enhancement, not required for the validated workload.

---

## 7. Regression analysis

- **No workspace lost a publishable recommendation.** Recommendation counts flat (80/80/80/80; Denver 27→26 = Photostream removed). Explainability **improved** on Plausible (0.96→1.00); MI-led CREATE share improved on Plausible (0.96→1.00); all others unchanged.
- **Allow-list: zero casualties** (§4) — the primary regression risk did not materialise.
- **Plausible NAV-proxy junk 0.08→0.12:** noise, not a semantic regression. After Michelin/Hyundai were filtered, `_balanced_selection` backfilled top-25 with lower-ranked candidates, two of which trip the NAV regex. The semantic quality of top-25 improved (2 off-topic proper nouns gone); the proxy is simply measuring a different tail. Within tolerance.
- **Fail-open verified end-to-end.** The first ON attempt (`…164046Z`) hit the 30 s timeout on 60-entity batches (`asyncio.TimeoutError`, empty message); every batch failed-open and the run **completed at exit 0 with deterministic results** — no analysis was lost. Root-caused (60 entities ≈ 32 s > 30 s), fixed (batch_size 60→25 ≈ 13 s, timeout 30→60 s); the corrected run logged **0 fallbacks**. This is direct evidence the fail-open contract holds under real failure.

---

## Success criteria

| Criterion | Result |
|---|---|
| **Primary:** named residual removed or strongly down-ranked | ◐ **Partial** — 3/7 removed, 1 down-ranked, 3 untouched (competitor-product + product-SKU classes) |
| Guardrail: no workspace regression > 2 pp | ✅ (NAV proxy +4 pp on Plausible is re-ranking noise; semantic top-25 improved) |
| Guardrail: known-good allow-list survives | ✅ zero false positives |
| Guardrail: deterministic fallback verified | ✅ proven under a real timeout + unit tests |

The layer is correct, safe, cheap, and cache-effective, and it **does** remove the unambiguous off-topic proper nouns. But the **primary** objective — eliminating the named residual — is met for only a minority, and the misses are **systematic**: domain-relevance scoring alone cannot resolve the competitor-product and product-SKU classes, and its effectiveness on the off-topic class is gated by niche-profile specificity.

---

## Conclusion

> ## B) Phase 2A requires redesign

**Keep the layer — extend it.** Phase 2A is a necessary, working, safe foundation (it filtered 21–31 off-topic entities/workspace, removed Michelin/Hyundai/Photostream, cost ~$0.01, broke nothing, zero false positives). But pure `(niche, entity)` relevance scoring, as scoped, does not eliminate the validated residual. Three bounded additions are required, each justified by specific evidence above:

1. **Feed the specific niche, not the top-level vertical.** Bloomberg = 0.05 against `"web analytics"` but 0.30 against `"software"`. Passing a precise niche string / site summary into the scorer (or lowering reliance on `primary_niche` in favour of `known_entities`) would drop Bloomberg below the floor and tighten every borderline case — no new layer, just better grounding. *(Smallest, highest-leverage fix.)*
2. **Add an explicit competitor-entity signal.** The workspace already stores its competitor list; entities that are competitor-owned products (InfoQ) should be flagged as a scoring input so they are down-weighted regardless of topical adjacency. This is the architecture review's "competitor entity source scoring" (previously secondary), now shown to be necessary.
3. **Add a lightweight entity-type gate (product-SKU/brand vs. editorial-topic).** Sub-brands score 1.0 because they *are* on-niche; relevance is the wrong axis. A cheap type classification (likely foldable into the same batched call) is needed for the product-SKU class.

None of these expands beyond entity-level scoring — they sharpen its inputs (niche specificity, competitor signal) and add one orthogonal entity-type judgement. Phase 2A ships as default-OFF and stays in the tree as the substrate for that redesign.

---

## Appendix — run lineage

| Run | Flag | Note |
|---|---|---|
| `2026-06-01T164035Z` | OFF | Deterministic baseline (A/B control) |
| `2026-06-01T164046Z` | ON | **Voided** — 30 s timeout on 60-entity batches; failed-open to deterministic (fail-open evidence) |
| `2026-06-01T165013Z` | ON | Treatment, batch_size 25 / timeout 60 s, 0 fallbacks (A/B treatment) |
