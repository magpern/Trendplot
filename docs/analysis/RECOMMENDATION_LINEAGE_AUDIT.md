# Recommendation Lineage Audit

**Date:** 2026-06-02  
**Site:** Example Lab — `https://www.example.com/`  
**Workspace:** `2a71aaf6-cc69-4663-be7f-7b13e50c3722`  
**Analysis job:** `98d47dd8-c8e3-4d3e-bbe5-96b2182720ed`  
**Tool:** `scripts/trace_recommendation_lineage.py`

---

## Pipeline overview

```text
Crawl
  → Website analysis (v6: extraction only; ideation stripped)
  → Site Strategy Profile (persisted artifact)
  → Opportunity engine (deterministic candidates from crawl signals)
  → Market intelligence / Editorial opportunity generator (EOG)
  → AI Editorial Strategist (compact profile → ideas)
  → Opportunity Intelligence (OI) ranking → ~80 recommendations
  → AI Recommendation Reviewer (compact profile relevance gate)
  → Final queue (CREATE / MONITOR / IGNORE)
```

Trace dimensions per topic:

```text
source → extraction → opportunity candidate → OI ranking → final recommendation
```

---

## Off-topic topics (Bookshelf, Adhesives, Facebook)

### Current database state

Trace run on 2026-06-02: **none** of these topics appear in the final recommendation queue, analysis opportunities, strategist ideas, editorial concepts, or market candidates for the latest Example Lab job.

| Topic | Final queue | Strategist | EOG | Market | OI opportunities |
|-------|-------------|------------|-----|--------|------------------|
| Bookshelf | — | — | — | — | — |
| Adhesives | — | — | — | — | — |
| Facebook | — | — | — | — | — |

These titles were observed in **earlier** Example Lab runs (documented in `docs/analysis/RECOMMENDATION_SCORING_AUDIT.md` and cross-vertical validation reports) before scoring fixes and this prompt refactor.

### Why they reached recommendations (historical path)

Documented root cause from `RECOMMENDATION_SCORING_AUDIT.md`:

1. **Extraction noise** — Crawl/entity extraction surfaced generic nouns from page copy, competitor pages, or boilerplate (e.g. social links → “Facebook”, unrelated product copy → “Adhesives”, layout/UI terms → “Bookshelf”, “Characteristics”).

2. **Website analysis overload (v4/v5)** — Single prompt attempted classification *and* 25–75 editorial seeds, diluting product focus and allowing non-catalog entities into `opportunities[]`.

3. **Editorial opportunity generator (EOG)** — Template titles such as “Introduction to {entity} for New Readers” and “Understanding the Scientific Interest Around {entity}” applied to **any** extracted entity, including junk nouns.

4. **Market / competitor bridge** — Weak substring niche checks (`niche in topic`) gave off-topic rows floor scores; competitor dedupe attached **external evidence**, unlocking CREATE via `has_external_evidence` even when business alignment was low.

5. **OI ranking** — Editorial + competitor-backed rows outranked niche-profile product rows that lacked external API demand signals.

6. **Reviewer (if enabled)** — Could demote but did not prevent upstream generation; fail-open on timeout/disabled.

Example historical titles:

- *Introduction to Bookshelf for New Readers* — EOG template + spurious “Bookshelf” entity from crawl noise  
- *A Practical Guide to Adhesives* — Generic noun extracted; editorial bridge marked `create`  
- *Understanding the Scientific Interest Around Facebook* — Social/platform token from footer/competitor HTML treated as content entity  

### After refactor

- Website analysis **does not** emit article seeds (`strip_ideation_from_extraction`).  
- Strategist receives **known_products** from Site Strategy Profile, not raw crawl dumps.  
- Prompt explicitly avoids platform/generic topics unless site-relevant.  
- Scoring gates (`_niche_qualified_for_create`, `_site_aligned_create`) already demote weak alignment (see scoring audit).

---

## Product topics (BPC-157, GHK-CU, MOTS-C, Kisspeptin)

### Current database traces (2026-06-02)

| Topic | Final queue | Primary source_type | EOG concepts | WA opportunities | Strategist ideas |
|-------|-------------|---------------------|--------------|------------------|------------------|
| **BPC-157** | ✓ CREATE + MONITOR | `editorial_opportunity` | 3 (incl. “What Is BPC-157?”) | 5+ | 0 stored |
| **GHK-CU** | ✓ MONITOR | `niche_profile` | 0 | 5+ | 0 stored |
| **MOTS-C** | ✓ MONITOR | `niche_profile` | 0 | 5+ | 0 stored |
| **Kisspeptin** | ✓ CREATE + MONITOR | `editorial_opportunity` | 3 | 5+ | 0 stored |

### Why products **did** reach the queue

1. **Niche profile** — `workspace_niche_profiles.known_products` includes BPC-157, GHK-CU, MOTS-C, Kisspeptin, Retatrutide (from crawl + analysis extraction).

2. **Deterministic opportunity engine** — Generates product-anchored templates: “{Product} Compared With Adjacent Research Topics”, mechanism explainers, etc.

3. **EOG** — Strong alignment for catalog products → high `niche_relevance` → CREATE for BPC-157, Kisspeptin.

4. **OI** — Product entities score well on niche/business alignment; site-aligned CREATE path applies.

### Why some products were MONITOR not CREATE

- GHK-CU, MOTS-C: present via **niche_profile** source with moderate scores (~0.41–0.43); no EOG finalist at top rank.  
- Competing editorial concepts and duplicate angle templates split score mass.  
- Pre-refactor: external-evidence gate favored competitor/editorial merges over pure niche-profile rows (partially fixed in scoring rebalance).

### Why products did **not** always become strategist-stored ideas

`ai_editorial_strategist_ideas` table shows **0 rows** for Example Lab in this trace — strategist either disabled, failed, or not re-run after recent changes. Final queue still populated via EOG + niche profile + opportunity engine (strategist is additive, not sole source).

Post-refactor: strategist runs on compact profile and should produce product-anchored ideas (storage, FAQ, comparisons) that feed editorial concepts on next analyze.

---

## Site Strategy Profile vs observed queue

Persisted profile (niche fallback, pre full v6 re-analyze):

- **known_products:** BPC-157, GHK-CU, MOTS-C, Kisspeptin, Retatrutide, CJC-1295, …  
- **primary_niche:** peptides  
- **content_inventory_summary:** legacy string referencing “215 topical article opportunities” (pre-v6 artifact; will update on next analyze)

Profile products **align** with CREATE/MONITOR recommendations. Junk entities (Bookshelf, Adhesives, Facebook) are **absent** from both profile and current queue.

---

## Comparison summary

| | Off-topic (Bookshelf, Adhesives, Facebook) | Products (BPC-157, GHK-CU, MOTS-C, Kisspeptin) |
|---|------------------------------------------|--------------------------------------------------|
| In Site Strategy Profile | No | Yes |
| In crawl product signals | Spurious / noise | Strong (product pages) |
| In niche profile | No | Yes |
| EOG template match | Yes (historical — any entity) | Yes — research templates |
| OI CREATE (historical) | Yes — competitor/editorial path | Mixed — editorial + niche_profile |
| OI CREATE (current trace) | **No** | Yes (BPC-157, Kisspeptin CREATE) |
| Strategist stored ideas | No | No (strategist not persisted this run) |

---

## Metrics (Example Lab, current queue sample)

Measured on mock compact-strategist output (`STRATEGIST_CONTEXT_AB.json`):

| Metric | Value |
|--------|-------|
| `product_alignment_rate` | 0.875 |
| `category_alignment_rate` | 0.438 |
| `off_topic_rate` | 0.0 |

Live strategist `--live` run after next full analyze recommended to confirm OpenAI output matches mock alignment.

---

## Recommendations

1. **Re-run Analyze Website** on Example Lab to populate v6 extraction + fresh Site Strategy Profile (without legacy “215 opportunities” summary).  
2. **Enable strategist** and verify `ai_editorial_strategist_ideas` rows for product FAQs/comparisons.  
3. **Re-run lineage script** after analyze to confirm off-topic topics stay absent and strategist ideas appear for BPC-157 / Kisspeptin.

Raw trace JSON: `docs/analysis/RECOMMENDATION_LINEAGE_TRACE.json`

---

## Conclusion

**A) Prompt responsibilities simplified and strategist input tightened**

Off-topic recommendations originated from **entity extraction noise + combined WA/EOG ideation + weak OI gates**, not from catalog products. Product topics reached the queue through **niche profile and EOG** with correct alignment. The refactor removes WA-side ideation and routes ideation through compact profile → strategist, addressing the core mismatch: *the system already discovered products; it did not use them effectively for ideation.*
