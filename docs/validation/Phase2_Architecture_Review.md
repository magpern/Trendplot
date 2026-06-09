# Phase 2 Architecture Review

**Date:** 2026-06-01
**Status:** Architecture review only — no implementation, no production code.
**Author:** Claude Code (Opus)
**Inputs:** `ENTITY_QUALITY_HARDENING_PASS_4_REPORT.md`, `PHASE2_READINESS.md`, `DETERMINISTIC_CEILING_REVIEW.md`, current pipeline source (`app/opportunity_intelligence/`, `app/market_intelligence/`, `app/editorial_opportunity/`, `app/config.py`).

---

## 0. Executive recommendation

> **A) Build Phase 2 Entity Relevance Scoring.**

The deterministic pipeline has plateaued (76–88% publishable on dense verticals). Every remaining failure class is an **entity-level domain-relevance** failure: a syntactically valid proper noun or product name that simply does not belong to the workspace's niche (Bloomberg/Michelin/Hyundai on a web-analytics site; InfoQ Newsletter/Photostream on a software-engineering blog; Travel Together Lite/Daily Carry Pro sub-brands on a bags site).

The smallest AI layer that addresses this is a **single relevance scorer** `(niche_profile, candidate_entity) → relevance ∈ [0,1] + one-line reason`, run **once per analysis** as a batched classification over the unique candidate-entity set, **cached** by `(niche_profile_hash, entity)`, and consumed by the existing pipeline through the **`niche_relevance` field that already exists** on `OpportunityCandidate`. This is the narrowest possible intervention: it changes no architecture, adds no provider, touches one scoring signal, and is fully gated behind a default-off flag.

Options B (opportunity scoring), C (editorial refinement), and D (hybrid) are **rejected** as larger than the validated problem. The residual is not "good entity, weak title" (C) and not "the whole opportunity object is wrong" (B) — it is precisely "wrong entity selected," which A targets directly and nothing else does more cheaply.

---

## Part 1 — Root cause analysis of the residual failures

### Method

I classified each surviving failure (from Pass 4 top-25 analysis) by the *type of understanding required to filter it*, and tested each against the deterministic filter's structural assumptions.

### 1.1 The five failure classes

| # | Class | Examples | Site | Deterministically solvable? |
|---|---|---|---|---|
| 1 | **Structural** | prices, CTAs, nav, site titles, FAQ/sentence/comparison/question fragments, generic structural terms | (all) | **Solved** — Passes 1–4 |
| 2 | **Semantic relevance** | Bloomberg, Michelin, Hyundai | Plausible | No |
| 3 | **Editorial relevance** | product sub-brands (Travel Together Lite, Daily Carry Pro); "Tortuga" as its own FAQ topic | Tortuga | No |
| 4 | **Freshness relevance** | Photostream (deprecated Apple service) | Pragmatic | No |
| 5 | **Competitor relevance** | InfoQ Software Architects' Newsletter, "The InfoQ" | Pragmatic | No |

**Class 1 is closed.** Everything else is open and shares one root cause: *the entity is well-formed but does not belong to this workspace's domain.* The deterministic filter (`is_entity_quality_junk`) reasons about the **shape** of a string; these failures are about its **meaning relative to a niche**.

### 1.2 Per-class analysis

#### Class 2 — Semantic relevance (Bloomberg / Michelin / Hyundai)

- **Why deterministic filtering cannot safely solve it.** These are correctly-formed capitalized proper nouns scraped from competitor enterprise case studies ("Bloomberg uses Matomo"). Syntactically they are *identical* to legitimate domain entities: `Thoughtworks` (valid for Pragmatic), `NOMATIC` (valid competitor brand for Tortuga), `Kubernetes` (valid concept). Any blocklist or pattern broad enough to catch "Bloomberg" also catches the legitimate ones. There is **no syntactic signal** separating "irrelevant company name" from "relevant domain brand."
- **Why AI might solve it.** A model with world knowledge knows that Bloomberg is a financial-media company unrelated to *web analytics*, while it knows Matomo/Fathom *are* analytics tools. Relevance is a position-in-knowledge-space judgment — exactly what language models encode.
- **Risk of AI false positives.** The model could down-score a *legitimate but unfamiliar* domain entity (a niche tool the model hasn't seen, a new product). Mitigation: relevance is a **down-ranking signal**, not a hard delete, for the borderline band — and the niche profile (known_entities, primary_niche) is given to the model as grounding so it scores *relative to this workspace*, not against generic priors.

#### Class 3 — Editorial relevance (product sub-brands)

- **Why deterministic can't.** "Travel Together Lite" and "Daily Carry Pro" are valid noun phrases under the 55-char gate, not questions/CTAs/titles. Distinguishing a *product SKU/sub-brand* (not an editorial topic) from a *buyer-decision topic* ("capsule wardrobe", "carry-on rules") requires understanding that the former names a specific product line and the latter names a researchable subject.
- **Why AI might.** The model can recognize "X Lite"/"X Pro" naming as product-tier branding and judge editorial usefulness ("would a buyer search this as a topic?").
- **Risk of false positives.** Could mistake a genuine category name that happens to look brand-like. Low impact here because these land in the borderline band, not hard-delete.

#### Class 4 — Freshness relevance (Photostream)

- **Why deterministic can't.** "Photostream" is a clean 12-char proper noun. Knowing it refers to a *deprecated* Apple service that is off-topic for software engineering requires temporal/world knowledge a syntactic rule cannot hold, and a hand-maintained blocklist would never generalize across verticals.
- **Why AI might.** Knowledge-cutoff awareness lets the model flag defunct/off-topic services.
- **Risk of false positives.** Model knowledge staleness could wrongly flag a *current* product as defunct. Mitigation: treat freshness as one contributor to the relevance score, not an independent kill switch; keep it in the down-rank band.

#### Class 5 — Competitor relevance (InfoQ Newsletter / "The InfoQ")

- **Why deterministic can't.** "InfoQ Software Architects' Newsletter" is a valid possessive noun phrase. A rule matching "proper-noun + Newsletter" would also kill "Pragmatic Engineer Newsletter" (the workspace's *own* product) and "Kubernetes Newsletter" (a legitimate concept). The discriminator is *provenance*: this entity appears **only** in competitor crawl, never in the workspace's own content.
- **Why AI might.** Given the niche profile + the entity's source provenance, the model can judge "this is a competitor's branded product, not a domain concept for *this* site."
- **Risk of false positives.** Down-scoring a competitor-named concept that is nonetheless a legitimate shared-domain topic. Mitigation: provenance (competitor-only vs. on-site) is already computable deterministically and can be passed as a feature, so the model is *informed*, not guessing.

### 1.3 Summary of Part 1

All open failures reduce to one question the deterministic engine structurally cannot answer:

> *"Is this well-formed entity actually about what this workspace is about?"*

That is a single, bounded, semantic question. It argues for the **narrowest** possible AI layer: an entity relevance scorer — not opportunity rewriting, not editorial generation.

---

## Part 2 — Candidate Phase 2 designs

The four options are evaluated against the **validated residual** (Part 1), not against hypothetical future needs.

### Option A — Entity Relevance Scoring

- **Input:** `(workspace, niche_profile, candidate_entity)`
- **Output:** `relevance ∈ [0,1]` + short reason
- **Where:** at discovery ingress / before EOG concept generation — i.e., the same chokepoints where `is_entity_quality_junk()` already runs.
- **What it kills:** Classes 2, 3, 4, 5 directly. It operates on the *atom* (the entity) where every residual failure lives.
- **Consumes via:** the **existing `niche_relevance` field** on `OpportunityCandidate` (currently set by the `_overlaps()` heuristic), plus an optional hard-filter threshold.

### Option B — Opportunity Relevance Scoring

- **Input:** `(workspace, candidate_opportunity)` — the fully-formed opportunity (topic + title + angle + content type + evidence)
- **Output:** `relevance ∈ [0,1]`
- **Where:** post-EOG, post-OI, scoring the assembled recommendation.
- **Assessment:** Strictly *superset* of A. The relevance defect always originates in the entity; by the time it is an opportunity object, the same Bloomberg seed has already been expanded into N concepts (EOG emits 5–12 per seed). Scoring at the opportunity layer means paying to score the **fan-out** rather than the **seed** — more items, higher cost, and you've already spent EOG compute on junk you'll then discard. It catches nothing on this residual that A doesn't catch earlier and cheaper.

### Option C — Editorial Refinement

- **Input:** `(candidate_opportunity)`
- **Output:** improved title / angle
- **Assessment:** **Solves a different problem.** C assumes the entity is right and the *phrasing* is weak. The validated residual is the opposite: the phrasing is fine, the *entity is wrong*. Refining "InfoQ Software Architects' Newsletter" into a prettier title makes a junk recommendation more convincing — actively harmful for this residual. C is a legitimate *future* quality lever (it would lift the ~70% Example Lab ceiling by varying angles beyond hash-assigned templates), but it does not address Phase 2's blocker.

### Option D — Hybrid (A + C, or A + B)

- **Assessment:** A real long-term shape, but larger than the validated problem *today*. Hybrid only earns its complexity once A is shipped and measured. Bundling C/B now violates the "smallest layer that solves the validated residual" constraint and multiplies cost, validation surface, and rollback complexity.

### Comparison matrix

| Criterion | A · Entity relevance | B · Opportunity relevance | C · Editorial refinement | D · Hybrid |
|---|---|---|---|---|
| **Addresses validated residual** | ✅ Directly (all of classes 2–5) | ◐ Yes but downstream of where junk originates | ❌ No (wrong problem) | ✅ (via its A component) |
| **Expected quality gain** | High: −12 pp Plausible junk, −8 pp Pragmatic junk | Similar ceiling, reached less efficiently | ~0 on residual; helps phrasing only | Highest, but most from A |
| **Complexity** | Low — one scorer, one existing field | Medium — scores rich objects, new schema | Medium — generation + safety review | High |
| **Cost** | Lowest — 1 batched call/run on unique entities; cached | Higher — scores post-EOG fan-out (5–12× entities) | High — generative tokens per opportunity | Highest |
| **Explainability** | High — per-entity reason feeds existing `reasons[]` | Medium — relevance of a composite is harder to attribute | Low — generated text needs its own QA | Medium |
| **Validation difficulty** | Low — reuses existing top-25 harness; entity in/out is binary-checkable | Medium — must judge composite quality | High — subjective title quality | High |
| **Operational risk** | Low — down-rank signal, default-off, instant rollback | Medium — sits in hotter path | Medium-High — generative drift, can publish worse copy | High |
| **Reversibility** | Flag off → exact pre-Phase-2 behavior | Flag off, but schema/coupling lingers | Flag off, but content already shaped | Partial |

**Conclusion of Part 2:** A is the smallest layer that fully covers the validated residual. B is A done less efficiently; C solves a different problem; D is premature. **Proceed with A.**

---

## Part 3 — Architecture proposal (Option A)

### 3.1 Where it sits in the pipeline

```
Website
  → Entity Extraction        (LLM extracts entities → niche_profile.known_entities, market signals)
  → Market Intelligence       (clusters, market_opportunity_candidates)
  → [★ ENTITY RELEVANCE SCORING ★]   ← NEW: scores the unique candidate-entity set
  → EOG                       (expands only sufficiently-relevant seeds into concepts)
  → OI                        (discovery → score_candidate consumes relevance via niche_relevance)
  → Publishing
```

The scorer sits **between Market Intelligence and EOG**, with its output **also** read at OI discovery time. This placement is deliberate:

- **Before EOG** so we do not spend concept-generation compute fanning out a junk seed (Bloomberg → 5–12 concepts).
- **Read again at OI discovery** because OI pulls candidates from *several* ingresses beyond EOG (niche_profile, existing opportunities, coverage, competitor snapshots — see `discovery.py`). A single cached score per `(niche_profile_hash, entity)` serves both consumers.

### 3.2 Inputs

A single batched request per analysis run:

```
{
  "niche_profile": {
    "primary_niche": "<str>",
    "known_entities":  [<str>, …],   // anchors: what this site IS about
    "known_categories":[<str>, …],
    "known_audiences": [<str>, …],
    "confidence": <float>
  },
  "entities": [
    { "label": "<entity>",
      "provenance": "on_site" | "competitor_only" | "trend" | "mixed",   // deterministic, precomputed
      "source_types": [<str>, …] }                                       // from discovery source mix
  ]
}
```

`provenance` and `source_types` are **already derivable deterministically** (discovery knows each candidate's `source_type`; competitor-only vs on-site is a set difference). Passing them as features lets the model resolve Class 5 (competitor relevance) without guessing.

### 3.3 Outputs

```
{
  "scores": [
    { "label": "Bloomberg",
      "relevance": 0.04,
      "reason": "Financial-media company; unrelated to web analytics. Appears only in competitor case studies." },
    { "label": "data privacy",
      "relevance": 0.93,
      "reason": "Core concern of privacy-first analytics buyers." }
  ],
  "model": "<light-model-id>",
  "scored_at": "<iso8601>"
}
```

### 3.4 Scoring model

**Primary: one batched lightweight-LLM classification call per analysis run.**

- One call scores the **entire unique-entity set** for a workspace (dozens of strings), not one call per entity. This keeps cost and latency flat regardless of candidate volume.
- Use the existing **light model tier** (`openai_light_model`, already configured with cost fields in `config.py`). No new provider — reuse the established OpenAI client.
- The niche profile is the grounding context, so the model scores *relative to this workspace*, not against generic web priors.

**Optional optimization (later, not required for v1): embedding pre-filter.** Embed the niche profile once and each unique entity once; cosine-similarity gives a cheap first pass. Embeddings alone are *insufficient* for this residual — "Bloomberg" sits moderately near "business/analytics" in embedding space and would not cleanly separate — so embeddings can **shortlist** but the LLM call makes the call on the ambiguous middle band. Defer until cost data justifies it.

**Decision bands (configurable):**

| Relevance | Action |
|---|---|
| `< 0.25` (hard floor) | **Filter** the entity before EOG (treated like `is_entity_quality_junk`) |
| `0.25 – 0.60` (borderline) | **Keep but down-rank**: write the score into `OpportunityCandidate.niche_relevance` so `score_candidate` (weight 0.10) naturally lowers it; attach the reason |
| `> 0.60` | Pass through; `niche_relevance` set from score |

This replaces the crude `_overlaps()` 0.78/0.62 heuristic in `_from_niche_profile` with a grounded value, and feeds the *same field the scorer already weights* — **zero scoring-formula changes required.**

### 3.5 Caching strategy

- **Cache key:** `sha1(normalized(primary_niche) + "|" + normalized(entity_label))`.
- **Why it works:** entities recur heavily across re-analyses of the same workspace; the niche profile changes rarely. Cross-workspace reuse is intentional for generic concepts ("data privacy" scored for "web analytics" is reusable), keyed on niche so "Bloomberg @ web-analytics" and "Bloomberg @ finance-blog" stay distinct.
- **Store:** a small `entity_relevance_scores` table (workspace-agnostic, niche-keyed) or a JSON-column cache keyed as above; TTL aligned to `reassessment_interval_days` (7) so deprecated-service judgments refresh as model knowledge updates.
- **Effect:** steady-state, only *new* entities hit the model — most runs cost ~0 incremental calls.

### 3.6 Cost controls

- **One batched call per run** (not per entity). With the light model and the existing cost fields, a 50-entity batch is a few thousand tokens — fractions of a cent.
- **Cache-first:** unchanged entities never re-scored.
- **Hard cap:** `entity_relevance_max_entities_per_run` (e.g. 150) — beyond it, fall back to deterministic-only for the overflow (fail-open, see 3.7).
- **Off the hot path:** runs during analysis/market intelligence, not at request time.
- **Default OFF:** flag-gated like every other AI layer (`market_ai_strategist_enabled` precedent), so there is zero cost until explicitly enabled per environment.

### 3.7 Failure handling (fail-open)

The scorer is an *enhancement*, never a dependency. On any failure (timeout, API error, malformed output, flag off, cache+API both unavailable):

- **Fall back to current behavior**: `niche_relevance` reverts to the `_overlaps()` heuristic, no entity is filtered on relevance grounds, and the pipeline proceeds exactly as it does today.
- A missing score is treated as `relevance = neutral` (no down-rank, no filter) — the system **never** degrades below the current deterministic ceiling.
- Malformed/partial batch responses are reconciled by label; unscored labels are left neutral.

### 3.8 Observability

- **Per-run metrics:** entities scored, cache hit rate, model calls, tokens, entities hard-filtered, entities down-ranked, fallbacks triggered.
- **Auditability:** persist `{entity, relevance, reason, model, scored_at}`; surface the reason in the recommendation's existing `reasons[]` / `explanation` so a filtered/down-ranked entity is **explainable to the user** ("De-prioritized: financial-media company unrelated to web analytics").
- **Regression guard:** log every entity that moved from "kept" to "filtered" between runs, so a model change that starts eating legitimate entities (Thoughtworks, NOMATIC) is visible immediately.

---

## Part 4 — Validation plan

### 4.1 How we prove Phase 2 improves quality

By re-running the **existing cross-vertical validation harness** (`scripts/run_opportunity_quality_validation.py`) on the same five workspaces, flag-off vs flag-on, and comparing the identical metrics already tracked in `docs/validation/runs/`. The residual is concrete and named, so success is **checkable item-by-item**, not just in aggregate.

### 4.2 Baseline metrics (frozen from Pass 4 run `2026-06-01T153916Z`)

| Workspace | Publishable | Junk | Named residual to eliminate |
|---|---|---|---|
| Plausible | ~76% | ~24% | Bloomberg, Michelin, Hyundai |
| Tortuga | ~88% | ~10% | Travel Together Lite, Daily Carry Pro |
| Pragmatic | ~84% | ~12% | InfoQ Newsletter, Photostream, The InfoQ |
| Example Lab | ~70% | ~4% | (control — expect no regression) |
| Denver | ~26% | ~60% | (excluded — content poverty, not in scope) |

### 4.3 Success metrics

**Primary (must hit):**
- Plausible junk: ~24% → **≤14%** (eliminate the 3 off-topic proper nouns).
- Pragmatic junk: ~12% → **≤6%** (eliminate InfoQ Newsletter, Photostream, The InfoQ).
- The **named** residual entities are absent from top-25 in the flag-on run.

**Guardrail (must not violate):**
- No publishable-rate regression > **2 pp** on any workspace.
- **Zero** false-positive removals from a fixed allow-list of known-good entities: `Thoughtworks`, `Microservices`, `Monolith`, `NOMATIC`, `GDPR`, `data privacy`, `Kubernetes`, `Security`, `Plausible`, `Tortuga` (the workspace's own brand), etc.
- Example Lab (control) unchanged within ±2 pp.

**Secondary:**
- Explainability pass rate stays 100% (every filtered/down-ranked entity carries a reason).
- Cache hit rate ≥ 80% by the second run of a workspace.

### 4.4 A/B comparison

- **Same inputs, same seed:** run the harness twice on identical persisted analysis data — once `ENTITY_RELEVANCE_SCORING_ENABLED=false`, once `true`. Deterministic upstream means the **only** delta is the relevance layer.
- **Diff artifact:** produce a per-workspace `relevance_ab_diff.json`: entities filtered, entities down-ranked (with before/after rank), entities unchanged. This is the audit trail proving the layer touched exactly the intended items.
- **Human spot-check:** the existing top-25 human-rating pass on the flag-on run, focused on the diff set.

### 4.5 Rollback criteria

Roll back (flip flag to `false` — instantaneous, no data migration) if **any** of:

1. Any guardrail allow-list entity is filtered or down-ranked below threshold (false positive on a known-good).
2. Publishable rate regresses > 2 pp on any workspace.
3. Per-run cost or latency exceeds budget (cap breached repeatedly).
4. Fallback rate > 10% of runs (scorer unreliable → no value, only risk).

Because the layer only *writes an existing field* and *optionally filters*, rollback is a single env var and the system returns bit-for-bit to the Pass 4 deterministic behavior.

---

## Part 5 — Implementation roadmap

### 1. Executive recommendation
Build **Option A — Entity Relevance Scoring**: a flag-gated, default-off, batched, cached `(niche_profile, entity) → relevance + reason` scorer that writes into the existing `OpportunityCandidate.niche_relevance` field and optionally hard-filters below a floor. Smallest AI layer that resolves all validated residual failure classes (2–5).

### 2. Preferred architecture
- Sits between Market Intelligence and EOG; result reused at OI discovery.
- One batched light-model call per run; cache keyed `(niche_hash, entity)`; fail-open to current heuristic.
- Consumes through existing scoring (`niche_relevance`, weight 0.10) — **no scoring-formula or schema redesign**.
- Three bands: hard-filter `<0.25`, down-rank `0.25–0.60`, pass `>0.60` — all thresholds configurable.

### 3. Alternatives rejected
- **B (Opportunity scoring):** superset of A, applied to EOG fan-out → more items, higher cost, junk scored after compute already spent. No incremental coverage on this residual.
- **C (Editorial refinement):** solves phrasing, not entity selection; would polish junk recommendations. Valid future lever for the Example Lab angle ceiling, not the Phase 2 blocker.
- **D (Hybrid):** premature; only justified after A is measured.

### 4. Estimated implementation effort
- **Small–Medium.** New module `app/entity_relevance/` (scorer + cache + prompt), one config flag block, one cache table/migration, wiring at two existing call sites (`discovery.py` ingress, EOG seed gate), reuse of the existing OpenAI client and cost plumbing. No new provider, no new pipeline stage object, no API surface change.
- Test surface mirrors the existing entity-quality suites: parametrized known-good (allow-list must survive) + known-bad (named residual must be filtered) cases.

### 5. Expected quality gain
- Plausible junk ~24% → ~12–14% (publishable → ~84–86%).
- Pragmatic junk ~12% → ~4–6% (publishable → ~92%+).
- Tortuga: minor (removes the two sub-brands; already at ceiling).
- Example Lab/Denver: no change (control / out-of-scope).
- Net: closes the semantic gap the deterministic passes structurally could not.

### 6. Risks
| Risk | Severity | Mitigation |
|---|---|---|
| False positive on legitimate unfamiliar entity | Med | Down-rank band (not delete); niche-grounded prompt; guardrail allow-list in CI |
| Model knowledge staleness (freshness class) | Low | Freshness is one contributor, not a kill switch; TTL refresh |
| Cost creep on large entity sets | Low | Batched + cached + hard cap + default-off |
| Hidden coupling / hard to remove later | Low | Writes only an existing field; fail-open; single-flag rollback |
| Over-reach into generation | Med | Scope locked to scoring; C/B explicitly out of v1 |

### 7. Validation plan
Re-run the existing cross-vertical harness flag-off vs flag-on on the five workspaces; prove the named residual entities disappear from top-25, junk drops to target on Plausible/Pragmatic, and **no** guardrail allow-list entity is touched and no workspace regresses > 2 pp. Rollback is a single env var.

---

## Final decision

> ## A) Build Phase 2 Entity Relevance Scoring

**Rationale:** Every validated residual failure is an entity-level domain-relevance failure (Part 1). Entity relevance scoring is the *smallest* AI layer that addresses all of them, it plugs into a field the scoring engine already consumes (`niche_relevance`), it adds no provider and no new pipeline stage, it is fully cached and default-off, and it is provably reversible. Options B, C, and D are each strictly larger than the validated problem and are rejected on the "smallest layer that solves the residual" constraint.

**Out of scope for v1 (explicitly):** opportunity-object scoring, title/angle generation, any change to the deterministic filters, any change to the scoring weights, Denver's content-poverty problem, and the Example Lab angle-diversity ceiling. These remain candidates for a *later* phase once Entity Relevance Scoring is shipped and measured.
