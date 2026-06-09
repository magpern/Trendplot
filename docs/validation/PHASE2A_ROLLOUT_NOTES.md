# Phase 2A Extension — Rollout Notes

**Date:** 2026-06-01
**Status:** Ready for controlled enablement (default-OFF)
**Reference:** `docs/validation/PHASE2A_EXTENSION_VALIDATION_REPORT.md`

---

## What this feature does

`ENTITY_RELEVANCE_SCORING_ENABLED=true` activates a batched AI scoring layer that runs during workspace analysis. For each analysis run, it:

1. Collects the candidate entity/topic set from all pipeline sources (niche profile, competitor snapshots, market candidates, editorial concepts).
2. Scores each entity against the **specific** workspace context (domain, name, niche, known entities, competitor domains) using the light model.
3. Hard-filters entities below a relevance floor, and applies a type+provenance-aware down-rank to product sub-brands and competitor-only assets.
4. Writes the result into the existing `niche_relevance` field on `OpportunityCandidate` — no new fields, no schema changes.

When disabled (the default), behavior is **identical** to the pre-Phase-2A deterministic pipeline.

---

## How to enable

Set in `.env` or environment:

```
ENTITY_RELEVANCE_SCORING_ENABLED=true
```

All other settings have working defaults. Only override if you have a specific need:

| Variable | Default | Notes |
|---|---|---|
| `ENTITY_RELEVANCE_MODEL` | *(empty = `openai_light_model`)* | Falls back to `gpt-4o-mini`. Override for a different model tier. |
| `ENTITY_RELEVANCE_BATCH_SIZE` | `25` | Entities per model call. At ~13 s/batch, 25 is safe within the 60 s timeout. |
| `ENTITY_RELEVANCE_TIMEOUT_SECONDS` | `60.0` | Per-batch timeout. Fail-open on breach. |
| `ENTITY_RELEVANCE_CACHE_TTL_SECONDS` | `604800` | 7 days. Aligns to `reassessment_interval_days`. |
| `ENTITY_RELEVANCE_FILTER_THRESHOLD` | `0.25` | Hard-filter floor (relevance). |
| `ENTITY_RELEVANCE_DOWNRANK_THRESHOLD` | `0.60` | Below this → down-rank band. |
| `ENTITY_RELEVANCE_TOPIC_THRESHOLD` | `0.35` | Editorial-topic floor for topic-gated types (company, SKU, generic). |
| `ENTITY_RELEVANCE_DOWNRANK_PENALTY` | `0.35` | Score penalty for type-driven down-ranks (product SKU, own-site mislabelled competitor). |
| `ENTITY_RELEVANCE_MAX_ENTITIES_PER_RUN` | `150` | Hard cap; overflow falls back to deterministic (fail-open). |

`OPENAI_API_KEY` must already be set (required for analysis regardless of this flag).

---

## Expected cost

Measured on the five validation workspaces (cold cache, `gpt-4o-mini`):

| Workspace type | Entities | Cost (cold) | Cost (warm) |
|---|---|---|---|
| Dense (SaaS, Publisher) | 150 | ~$0.005 | ~$0 |
| Ecommerce | 122 | ~$0.004 | ~$0 |
| Research | 103 | ~$0.004 | ~$0 |
| Local / sparse | 32 | ~$0.001 | ~$0 |
| **Total (5 workspaces)** | | **~$0.019** | **~$0** |

The cache (keyed by workspace domain + entity, 7-day TTL) achieves 100% hits on re-analysis within a week. Steady-state cost for a workspace re-analyzed weekly is effectively zero — only new or changed entities trigger model calls.

Latency: 65–100 s per workspace (off the hot path; runs during analysis, not at request time).

---

## Rollback procedure

**Instant, zero-downtime.**

1. Set `ENTITY_RELEVANCE_SCORING_ENABLED=false` (or unset it — the default is `false`).
2. Restart the worker, or wait for the next analysis cycle.

The system returns bit-for-bit to the pre-Phase-2A deterministic behavior. No database migration required; no data to undo. The in-process cache is discarded on restart.

If you want to force a fresh pipeline rebuild after rollback, trigger `/refresh-opportunity-intelligence` on each workspace — this takes seconds and requires no AI calls when the flag is off.

---

## Validated quality improvement

From the validation A/B (OFF vs ON, same 5 workspaces, same inputs):

- All 7 named semantic-residual entities removed from or pushed out of top-25 recommendations.
- **Zero allow-list false positives** (Thoughtworks, NOMATIC, GDPR, capsule wardrobe, BPC-157, etc. all intact).
- No publishable regression on any workspace.
- Plausible explainability rate: 0.96 → 1.00; MI-led CREATE: 0.96 → 1.00.
- Example Lab (control) unchanged.
- Deterministic fallback verified under a real timeout scenario (exit 0, correct behavior).

---

## When to enable

**Recommended for:** dense-content workspaces (≥ 8 crawled pages, confident niche detection). SaaS, ecommerce, publisher, and research verticals all benefit.

**Not recommended for (yet):**
- Workspaces with a `low_content_warning` (sparse site). The AI layer cannot improve what the entity extractor couldn't find in 4 pages. The low-content warning and sparse-site score penalty are the correct handling for these workspaces — see below.
- Workspaces where the niche profile has `confidence < 0.6`. The grounding context is too coarse to produce reliable relevance judgements.

---

## Operator / developer notes

### Sparse-content workspaces (e.g. Denver local)

The Phase 2A extension does **not** solve the Denver class of failures. Denver returns ~26% publishable not because of bad entity quality but because only 4 pages were crawled, the niche resolved as `"generic"`, and the LLM extracted structural noise instead of real plumbing entities.

The correct handling is already in place:
- `analyze_workspace` returns `low_content_warning` when `page_count < MIN_ANALYSIS_PAGES_FOR_CREATE` and niche is low-confidence.
- The OI service applies a `sparse_site` score penalty (−0.18 on CREATE scores) to suppress unreliable creates.
- The UI should surface the low-content warning to the user.

**Action for Denver:** add more site content (blog posts, service pages), then re-analyze. Phase 2A is not a substitute.

### Cache is in-process, not DB-backed

The current cache is process-local (Python dict, TTL-based). This was a deliberate Phase 2A choice to keep the implementation migration-free and minimal. Implications:

- Cache is **lost on worker restart**. The first analysis after restart incurs full cold cost (~$0.004 per workspace).
- In a multi-process or multi-instance deployment, each process maintains its own cache — no sharing. This is fine at current scale; if cost or latency becomes a concern at higher volume, a DB-backed or Redis cache is the documented next step.

### Model type labels are noisy

The entity-type taxonomy (8 types) works reliably in aggregate but individual labels are not stable across model calls. The decision logic deliberately uses **type + provenance + relevance + editorial-topic score together**, not type alone. Do not build hard rules on a specific entity type label in isolation.

### Provenance is computed from source sets, not the model

Provenance (`own_site` / `competitor_only` / `mixed` / `market`) is deterministically derived from which pipeline sources an entity appears in — not a model output. This is intentional: provenance is the most reliable discriminator (e.g. NOMATIC vs The InfoQ), and keeping it deterministic means it cannot drift or hallucinate.

---

## Known limitations

| Limitation | Impact | Path forward |
|---|---|---|
| In-process cache lost on restart | Cold cost (~$0.004/workspace) on first post-restart analysis | DB-backed cache (future) |
| Entity-type labels are noisy per-call | Handled by multi-signal decision logic; doesn't affect outcomes | Stable by design |
| Model knows ~Jan 2026; very new entities may score strangely | Rare; correctible via cache TTL refresh | None needed now |
| Dense niche profiles (150-entity cap) may leave some candidates unscored | Unscored = neutral = deterministic fallback; not a regression | Adjustable via `MAX_ENTITIES_PER_RUN` |
| Latency ~65–100 s per workspace | Off the hot path (analysis-time only); not user-facing | Parallelise batches (future) |

---

## Changelog entry

```
## Phase 2A Extension — Entity Relevance Scoring (2026-06-01)

Feature: ENTITY_RELEVANCE_SCORING_ENABLED (default false)

Adds a batched, cached, fail-open AI scoring layer that grades each candidate entity
against the specific workspace context (site name, domain, niche, known entities,
competitor domains) before it reaches the recommendation pipeline.

What it removes from recommendations:
- Off-topic company/client names scraped from competitor case studies
- Competitor-owned publications and product names (competitor_only provenance)
- Product sub-brands and SKUs that are not researchable editorial topics
- Deprecated or stale services

What it preserves:
- Domain concepts, product categories, buyer-decision topics
- Competitor brands the site itself engages (comparison content)
- All existing deterministic filters (unchanged)

Validated on 5 workspaces across 4 verticals:
- 7/7 named semantic-residual entities removed or out of top-25
- Zero allow-list false positives
- No workspace regression
- ~$0.004/workspace cold, ~$0 warm; 100% cache hit on re-analysis

Safe to enable via ENTITY_RELEVANCE_SCORING_ENABLED=true. Instant rollback by
reverting the flag.
```

---

## Conclusion

> ## A) Ready for controlled enablement

No blockers. The feature is default-OFF, fully reversible, zero-downtime, and validated across all target verticals. Enable per-environment with `ENTITY_RELEVANCE_SCORING_ENABLED=true`. Start with one dense-content workspace and verify the top-25 before rolling out broadly. Monitor the `entity_relevance` block in the OI summary (returned in the approval event metadata and the `/refresh-opportunity-intelligence` response) to confirm scoring is active and the cache is warming.
