# Recommendation Scoring Audit

**Date:** 2026-06-02  
**Scope:** Opportunity Intelligence ranking and CREATE / REFRESH / MONITOR / IGNORE assignment  
**Validation site:** Example Lab-style research peptide supplier (fixture-based; no site-specific allowlists)

---

## Executive conclusion

**A) Recommendation ranking/action assignment fixed**

Root cause was generic scoring and action gates that allowed **competitor/editorial backlog items with weak niche alignment** to become **CREATE**, while **niche-profile entities with strong site alignment** were demoted to **MONITOR** because they lacked third-party demand APIs.

---

## Part 1 — Explainability tooling

### Per-recommendation payload

Each recommendation now includes `metadata.explainability`:

```json
{
  "title": "Create coverage for BPC-157 Research Peptide",
  "topic": "BPC-157 Research Peptide",
  "action": "create",
  "final_score": 0.712,
  "niche_relevance": 0.94,
  "business_relevance": 0.87,
  "coverage_gap": 0.65,
  "competitor_evidence": 0.0,
  "external_demand": 0.0,
  "entity_relevance": null,
  "has_external_evidence": false,
  "source_type": "niche_profile",
  "confidence": 0.82,
  "demand_score": 0.31,
  "action_reason": "Strong niche and business relevance with a coverage gap supports CREATE without external demand.",
  "rank_reason": "Ranked at 0.71 from niche relevance 0.94, business relevance 0.87, coverage gap 0.65, site niche entity."
}
```

### Audit API

```text
GET /autopilot/workspaces/{workspace_id}/recommendations/audit
```

Returns `summary`, `top_create` (20), `top_monitor` (20), and full `items` with explainability fields.

### Code

| Module | Purpose |
|--------|---------|
| `app/opportunity_intelligence/explainability.py` | `build_recommendation_explainability`, `build_recommendation_audit_report` |
| `app/opportunity_intelligence/niche_alignment.py` | Generic niche/entity alignment scoring |
| `app/opportunity_intelligence/service.py` | Attaches explainability during `_recommend` |

---

## Part 2 — CREATE vs MONITOR diagnostics (traced, not guessed)

### Why BPC-157 / GHK-CU / Research Peptides became MONITOR (before fix)

**Code path:**

1. `discovery._from_niche_profile` → `source_type: niche_profile`, `coverage_gap: 0.65`, high entity alignment.
2. `demand.enrich_candidate` → `has_external_evidence: false` (niche profile is internal).
3. `score_candidate` → **−0.12** penalty for missing external evidence.
4. `decide_action` branch at `coverage_gap >= 0.62`:
   - `_market_backed_create` → false (not editorial/market).
   - `_site_aligned_create` → **false** (not implemented before fix).
   - `_internal_create_exception` → false (`confidence` ~0.82 but `coverage_gap` 0.65 < 0.92).
   - `has_external_evidence` → false → **`monitor`**.

**Result:** Correct niche entities were known to the system but blocked from CREATE solely by the external-evidence gate.

### Why Facebook / Adhesives / Characteristics became CREATE (before fix)

**Code path:**

1. `editorial_concepts_to_opportunity_candidates` → `action_hint: create`, default `niche_relevance: 0.62–0.76` via weak substring check (`niche in topic`).
2. `_dedupe_candidates` merges editorial row with `competitor` row on same topic → competitor evidence attached.
3. `demand.enrich_candidate` → competitor signal marked **external** → `has_external_evidence: true`.
4. `_market_backed_create` → **true** because `editorial_concept_id` alone counted as “persisted signal” (bug).
5. Even after signal fix, merged competitor evidence unlocked CREATE via `has_external_evidence` with **floor niche scores** (`max(base, alignment)` kept weak topics at 0.62).

**Result:** Off-topic competitor/editorial topics outranked core niche entities.

---

## Part 3 — Architecture validation

### Intended behavior

```text
Analyze target website → niche/business → competitors → coverage gaps → site-relevant recommendations
```

### What was wrong

| Signal | Intended role | Actual effect (before) |
|--------|---------------|-------------------------|
| Niche profile entities | Primary CREATE candidates | Demoted to MONITOR (no external API) |
| Editorial backlog | Site-aligned content concepts | CREATE even when topic unrelated to niche |
| Competitor topics | Gap hints, not article drivers | Treated as external demand; unlocked CREATE |
| `editorial_concept_id` | Traceability | Incorrectly treated as market proof |

Competitor evidence **was overpowering** niche/business relevance for action assignment, not just ranking weight.

---

## Part 4 — Scoring rebalance (generic, no peptide rules)

### `niche_alignment.py`

Token/entity overlap between topic and `primary_niche`, `known_entities`, `known_categories`. Used by editorial bridge, market bridge, competitor discovery, and niche profile candidates.

### `scoring.py`

- Increased `niche_relevance` weight (0.10 → 0.14); reduced `competitor_gap` (0.06 → 0.04) and raw `demand_score` (0.16 → 0.14).
- Removed external-evidence penalty for **niche_profile** rows with `niche_relevance >= 0.65`.
- Added **−0.15** penalty when `niche_relevance < 0.55`, `business_relevance < 0.62`, and source is editorial/market/competitor.

### `decisions.py`

| Gate | Change |
|------|--------|
| `_niche_qualified_for_create` | Blocks CREATE when niche/business below threshold |
| `_site_aligned_create` | **New:** niche_profile / existing_opportunity with strong alignment → CREATE without external APIs |
| `_market_backed_create` | Requires **non-empty** `source_signal_ids`, not metadata ID alone |
| `_external_demand_supports_create` | **New:** competitor-only external cannot CREATE unless niche ≥ 0.72 and business ≥ 0.68 |

### Bridges

`editorial_opportunity/bridge.py` and `market_intelligence/bridge.py` now derive relevance from `aligned_relevance_scores()` instead of substring heuristics.

---

## Part 5 — Action assignment review

| Question | Answer |
|----------|--------|
| Are relevant topics demoted because demand thresholds are too strict? | **Yes.** CREATE required `has_external_evidence` or extreme `_internal_create_exception`. Niche entities failed both. **Fixed** via `_site_aligned_create`. |
| Are coverage-gap topics forced into MONITOR? | **Yes**, when gap ≥ 0.62 but external proof missing. Site-aligned entities now exempt. |
| Do generic competitor topics bypass niche checks? | **Yes.** Dedupe merged competitor evidence; floor niche scores and competitor-as-external unlocked CREATE. **Fixed** via alignment scoring + `_external_demand_supports_create`. |
| Is entity relevance ignored during assignment? | Entity relevance (Phase 2A) still optional and pre-score only. Explainability surfaces `entity_relevance` when present; assignment uses updated niche alignment heuristics when Phase 2A is off. |

---

## Part 6 — Explainability UI

Analyze Website → **Diagnostics** tab shows collapsible **Recommendation scoring** cards (not shown on Summary or Recommendations tabs):

```text
Score: 0.71
Niche relevance: 0.94 · Business relevance: 0.87 · Coverage gap: 0.65
Competitor evidence: 0 · Demand evidence: 0
Reason: Strong niche and business relevance with a coverage gap supports CREATE without external demand.
```

---

## Part 7 — Tests

`tests/test_recommendation_scoring.py` covers:

1. Strong niche topic outranks generic competitor topic  
2. Strong business/niche can CREATE without external demand  
3. Weak niche cannot CREATE via competitor evidence alone  
4. Relevant entity not demoted when editorial backlog is off-topic  
5. Market-backed CREATE requires real signal IDs  
6. Explainability + audit report populated  
7. Existing editorial + web_search flow still produces CREATE  
8. Discovery includes niche profile entities  

---

## Part 8 — Expected post-fix behavior (Example Lab fixture)

| Topic | Before | After |
|-------|--------|-------|
| BPC-157 Research Peptide | MONITOR | CREATE |
| GHK-CU Research Peptide | MONITOR | CREATE |
| Research Peptides | MONITOR | CREATE |
| Facebook | CREATE | MONITOR |
| Adhesives | CREATE | MONITOR |
| Introduction to Analysis for New Readers | CREATE | MONITOR |

Re-run **Re-run recommendations** on an existing Example Lab analysis to refresh persisted rows.

---

## Files changed

- `app/opportunity_intelligence/decisions.py`
- `app/opportunity_intelligence/scoring.py`
- `app/opportunity_intelligence/niche_alignment.py`
- `app/opportunity_intelligence/explainability.py`
- `app/opportunity_intelligence/discovery.py`
- `app/opportunity_intelligence/service.py`
- `app/editorial_opportunity/bridge.py`
- `app/market_intelligence/bridge.py`
- `app/api/routes.py` (audit endpoint)
- `app/analyze_ui.py` (Diagnostics explainability)
- `tests/test_recommendation_scoring.py`
