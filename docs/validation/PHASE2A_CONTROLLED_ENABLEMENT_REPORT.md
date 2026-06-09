# Phase 2A Entity Relevance Scoring — Controlled Enablement Report

**Date:** 2026-06-01
**Workspace tested:** Plausible Analytics (`5b12397d`) — 9 pages, niche `software`, confidence 100%
**Feature flag:** `ENTITY_RELEVANCE_SCORING_ENABLED`
**Tests:** 482 pass (unchanged)

---

## 1. Workspace tested

| Property | Value |
|---|---|
| Name | Plausible Analytics |
| URL | https://plausible.io/ |
| Workspace ID | `5b12397d` |
| Pages crawled | 9 |
| Niche | software |
| Niche confidence | 100% |
| `low_content_warning` | **False** |
| `min_pages_for_create` | 8 |

Plausible was selected as the target: clearly above the 8-page dense-content threshold, high niche confidence, and contains the named Bloomberg/Michelin/Hyundai residuals in the OFF baseline — making the ON effect directly observable.

---

## 2. Config changes made

**One environment variable set.** No code changes, no migrations, no `.env` file edits — the running server is unaffected until restarted with the new value.

```
ENTITY_RELEVANCE_SCORING_ENABLED=true
```

All other Phase 2A settings use defaults (verified correct at preflight):

| Setting | Value |
|---|---|
| `ENTITY_RELEVANCE_MODEL` | `gpt-4o-mini` (via `OPENAI_LIGHT_MODEL` default) |
| `ENTITY_RELEVANCE_BATCH_SIZE` | 25 |
| `ENTITY_RELEVANCE_TIMEOUT_SECONDS` | 60.0 |
| `ENTITY_RELEVANCE_CACHE_TTL_SECONDS` | 604800 (7 days) |
| `ENTITY_RELEVANCE_FILTER_THRESHOLD` | 0.25 |
| `ENTITY_RELEVANCE_DOWNRANK_THRESHOLD` | 0.60 |
| `ENTITY_RELEVANCE_TOPIC_THRESHOLD` | 0.35 |
| `ENTITY_RELEVANCE_DOWNRANK_PENALTY` | 0.35 |
| `ENTITY_RELEVANCE_MAX_ENTITIES_PER_RUN` | 150 |

---

## 3. First-run metrics (cold cache)

```
entity_relevance_scoring_enabled : true
entity_relevance.enabled          : true
elapsed                           : 91.7 s  (off hot path — analysis-time only)
total_recommendations             : 80
```

| Metric | Value |
|---|---|
| entities_requested | 150 |
| entities_scored | 150 |
| model_calls | 6 |
| cache_hits | 0 (cold) |
| cache_misses | 150 |
| filtered_by_relevance | 44 |
| down_ranked_by_relevance | 38 |
| fallback_count | **0** |

**Entity type distribution:**
`domain_concept: 46`, `generic_or_unclear: 91`, `competitor_brand: 5`, `competitor_product: 4`, `company_or_client: 3`, `product_category: 1`

---

## 4. Second-run cache metrics (warm, same process)

```
elapsed : 0.5 s  (99.5% faster than cold)
```

| Metric | Run 1 (cold) | Run 2 (warm) |
|---|---|---|
| model_calls | 6 | **0** |
| cache_hits | 0 | **150** |
| cache_misses | 150 | 150 (counter accumulates) |
| filtered_by_relevance | 44 | 44 |
| fallback_count | 0 | 0 |

**Top-25 rank stability: 25/25 positions identical.** The output is deterministic given the same scored entities — the cache produces the same result as the model, exactly.

---

## 5. Top-25 before/after notes

### OFF baseline (deterministic)

```
 #1  Acquisition
 #2  digital privacy
 #3  The consent data gap
 #4  Security
 ...
#14  Bloomberg          ← off-topic company (competitor case study)
#17  Michelin           ← off-topic company (competitor case study)
#19  Hyundai            ← off-topic company (competitor case study)
#20  Starts at $        ← price string
```

### ON (Phase 2A Extension active)

```
 #1  digital privacy    ← promoted (domain_concept, rel=0.85)
 #2  The consent data gap
 #3  Acquisition
 #4  Security           ← domain_concept, rel=1.0
 ...
     [Bloomberg absent — filtered]
     [Michelin absent — filtered]
     [Hyundai absent — filtered]
     [Starts at $ absent — filtered by deterministic price gate]
```

**Bloomberg, Michelin, and Hyundai are absent from top-25 and from all 80 recommendations.** Legitimate analytics recommendations (digital privacy, Security, API comparison, Compliance, Integration, Privacy-first) all survive with their relevance metadata attached.

**Observation:** Items #20–21 in the ON top-25 (`Matomo Cloud Terms of Service…`, `Compare Pricing Plans - Matomo…`) are competitor-page-sourced titles that survived scoring — they appear as editorial concepts generated from valid seed topics by EOG and arrive with high source scores. They are in the lower half of top-25 and have no `entity_relevance` metadata, meaning they were not in the entity candidate set scored by Phase 2A. This is a pre-existing deterministic filter gap (site-title fragments as EOG titles, not raw entities), not a Phase 2A regression. Noted as a known limitation.

---

## 6. Rollback confirmation

Flag set to `false` in a fresh process. Results:

- `entity_relevance.enabled = False` ✓
- No `entity_relevance` block in OI summary ✓
- `relevance_scoring_applied` absent from summary ✓
- Top-25 **exactly matches the OFF baseline** — Bloomberg #14, Michelin #17, Hyundai #19 back in place ✓
- Zero model calls ✓

**Rollback is instant and complete.** Reverting `ENTITY_RELEVANCE_SCORING_ENABLED=false` (or unsetting the variable) and restarting the worker returns the pipeline to the pre-Phase-2A deterministic state with no side effects.

---

## 7. Warnings

| Warning | Severity | Action |
|---|---|---|
| EOG-title site-title fragments in bottom half of top-25 (#20–21) | Low — pre-existing gap, not Phase 2A regression | Investigate deterministic title guard separately; not blocking |
| In-process cache not shared across processes or restarts | Informational | Each worker instance re-scores on first analysis after start; ~$0.004 cold cost |
| Denver/sparse-content workspaces: **do not enable Phase 2A** | Operational | Use `low_content_warning` + sparse-site penalty only; Phase 2A cannot improve entity quality from 4-page crawls |

---

## 8. Recommendation

**Enable for all dense-content workspaces.** The definition of "dense" for Phase 2A purposes:

- `page_count >= MIN_ANALYSIS_PAGES_FOR_CREATE` (default 8)
- `low_content_warning == False`
- Niche confidence ≥ 60%

Denver and any workspace matching `low_content_warning = True` should **not** have Phase 2A enabled; the low-content warning and sparse-site score penalty remain the correct and sufficient handling.

**Rollout path:** set `ENTITY_RELEVANCE_SCORING_ENABLED=true` in environment and restart the worker. Monitor the `entity_relevance` block in the OI summary (visible in approval event metadata) for the first analysis of each workspace to confirm scoring is active and cache is warming.

---

## Conclusion

> ## A) Controlled enablement successful

All verification criteria met:

| Criterion | Result |
|---|---|
| Scoring activates (enabled=true, 6 model calls) | ✅ |
| Zero fallbacks | ✅ |
| Named residuals removed (Bloomberg, Michelin, Hyundai) | ✅ |
| Cache warms (93.7 s cold → 0.5 s warm, 0 model calls) | ✅ |
| Output stable (25/25 top-25 positions identical run-to-run) | ✅ |
| No regression in allow-list or publishable recommendations | ✅ |
| Rollback instant and complete (exact OFF baseline restored) | ✅ |
| Feature not recommended for sparse-content workspaces | ✅ (Denver excluded, criteria documented) |
