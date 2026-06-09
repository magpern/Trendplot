# Phase 2 AI Readiness Assessment

**Date:** 2026-06-01
**Validation run:** `docs/validation/runs/2026-06-01T153916Z`
**Context:** Post-Entity Quality Hardening Pass 4 (final deterministic micro-pass)

---

## Is Phase 2 AI now justified?

**Yes — for the three dense-content verticals (Plausible, Tortuga, Pragmatic).**

The deterministic ceiling has been reached or effectively reached for all three. The remaining failures are semantic in nature and cannot be addressed by syntactic filtering rules. Two of the three verticals have cleared the Phase 2 eligibility gates outright; the third (Plausible) is within the margin of the hard semantic residual.

---

## Gate status

| Gate | Requirement | Actual | Status |
|---|---|---|---|
| Publishable rate | ≥60% across dense verticals | Plausible 76%, Tortuga 88%, Pragmatic 84% | ✓ |
| Human junk rate | ≤15% | Tortuga ~10%, Pragmatic ~12%, Plausible ~24% | △ (2 of 3 clear) |
| Remaining failures are semantic | Must be true | Yes — off-topic proper nouns, competitor branded products, deprecated services | ✓ |
| No major structural entity-quality failure | Must be true | True — all structural classes resolved | ✓ |
| Deterministic ceiling reached | Effectively reached | Yes for Tortuga/Pragmatic; nearly for Plausible | ✓ |

**Plausible note:** The ~24% junk contains approximately:
- 3 off-topic proper nouns (Bloomberg, Michelin, Hyundai) = ~12% → semantic
- 3 remaining generic single-word floaters = ~12% → micro-deterministic (could add 3 more terms)

Adding "Accurate", "business", "Compare" to `GENERIC_STRUCTURAL_TERMS` would reduce Plausible junk to ~12% IF no new junk replaces them (whack-a-mole dynamic has been observed in Passes 3–4). Even if this small fix is applied, the remaining ~12% is still semantic residual (off-topic proper nouns). Plausible is close enough to the ceiling that Phase 2 is justified.

---

## What problem would Phase 2 AI solve?

Phase 2 AI addresses a specific, clearly bounded problem: **entity domain relevance scoring**.

### The problem in precise terms

The deterministic pipeline successfully:
- Filters syntactic junk (prices, CTAs, site titles, question fragments)
- Routes to vertically-appropriate templates
- Balances content types and deduplicates
- Scores candidates by coverage gap, freshness, market signals

What it cannot do:
- Determine whether "Bloomberg" is relevant to a web analytics product's editorial strategy
- Distinguish between "Thoughtworks" (relevant competitor entity for a software engineering blog) and "Michelin" (irrelevant enterprise client on a web analytics competitor's blog)
- Score the editorial value of "Travel Together Lite" (product sub-brand) vs "capsule wardrobe" (buyer decision topic) for a travel-bags site

All three require **contextual relevance judgment** — understanding both the workspace niche AND the semantic distance of a candidate entity from that niche. This is fundamentally a language model task.

### What Phase 2 AI would do (scope, not design)

**Entity relevance scoring:** Given a workspace niche profile and a candidate entity, produce a relevance score (0–1) indicating how likely the entity is to drive valuable editorial content for THIS specific workspace.

**Examples of expected output:**
- Workspace: web analytics tool. Entity: "Bloomberg" → relevance ≈ 0.05 (this is a client of a competitor, not a domain concept)
- Workspace: web analytics tool. Entity: "data privacy" → relevance ≈ 0.92 (core domain concept)
- Workspace: software engineering blog. Entity: "Microservices" → relevance ≈ 0.95 (core domain concept)
- Workspace: software engineering blog. Entity: "Photostream" → relevance ≈ 0.08 (deprecated unrelated service)
- Workspace: travel bags. Entity: "Travel Together Lite" → relevance ≈ 0.35 (product sub-brand, borderline)
- Workspace: travel bags. Entity: "capsule wardrobe" → relevance ≈ 0.78 (buyer decision topic)

**Integration point:** This scoring would run as a post-filtering step before EOG generates concepts. Low-relevance entities are filtered; borderline entities are downscored in the OI ranking.

---

## Specific AI capabilities required

### 1. Entity relevance scoring (primary)

**What:** Given `(workspace_niche_profile, candidate_entity)`, score relevance.

**Why deterministic can't do it:** Relevance requires understanding semantic distance in a knowledge space — the relationship between "web analytics" and "Bloomberg" vs. "web analytics" and "GDPR compliance" is not syntactically encodable.

**Expected impact:** Eliminate the off-topic proper noun class (~3 items per 25 in Plausible) and reduce the competitor-branded-product class (~2–3 items in Pragmatic).

**Scope:** Runs offline or as a batch step during market intelligence / EOG, not in the hot path.

### 2. Competitor entity source scoring (secondary)

**What:** Given `(entity, source=competitor_page)`, assess whether the entity is a domain concept found on the competitor's page vs. a context-specific reference (client name, tool integration, etc.).

**Why deterministic can't do it:** The entity "Bloomberg" appears on a competitor's case study page — syntactically identical to "BPC-157" appearing on a research competitor's page. Domain knowledge is required to distinguish.

**Expected impact:** Specifically addresses the off-topic client-mention entities from competitor blog posts.

**Scope:** Can be combined with entity relevance scoring.

### 3. Editorial angle selection (tertiary, future)

**What:** Given `(topic, niche, audience)`, suggest the most distinctive angle rather than relying on template rotation.

**Why deterministic can't do it:** "BPC-157" can be approached from safety, mechanism, research frontier, or regulatory angles. The template-based system currently assigns angles by hash — appropriate for structural diversity but not for editorial insight.

**Expected impact:** Would lift Example Lab and other verticals from ~70% publishable to higher, and improve title quality for topics that survive entity filtering.

**Scope:** This is the true "editorial phrasing/voice" improvement. Recommended as Phase 2 scope but NOT the primary blocker — the entity relevance problem is more impactful.

---

## What Phase 2 AI would NOT address

- **Denver's sparse-content problem.** Denver's issue is crawl depth (4 pages) and niche detection failure. No amount of AI post-processing of candidate entities improves the quality of what was extracted from 4 pages. Denver needs more site content before re-analysis.
- **The whack-a-mole dynamic in generic-term filtering.** Adding more terms to `GENERIC_STRUCTURAL_TERMS` is not a Phase 2 task — it's a small ongoing deterministic maintenance operation.
- **Example Lab's residual** (the `bactriostatic` misspelling). This requires a domain lexicon (deterministic option) or spell-checking (AI option). Addressed separately.

---

## Phase 2 AI should NOT be used for

- Replacing existing deterministic filters (prices, CTAs, site titles) — these work well and are cheaper to run
- Generating titles or content — that is the existing job-based generation pipeline (`/generate-article`)
- Making coverage or calendar decisions — those are architectural decisions beyond entity scoring

---

## Recommended Phase 2 scope summary

**Core task:** Build an entity relevance scorer that takes `(niche_profile, candidate_entity)` as input and returns a relevance score. Use this score as a post-EOG filter or OI downranking signal.

**Input:** Workspace niche profile (primary niche, known entities, known audiences) + candidate entity string.

**Output:** Relevance score 0–1. Entities below a configurable threshold (e.g., 0.25) are filtered; entities 0.25–0.60 are downscored in OI ranking.

**Expected quality improvement:** Eliminate ~3 off-topic items per 25 in Plausible (~12 pp junk reduction); eliminate ~2 semantic-junk items per 25 in Pragmatic (~8 pp reduction). Tortuga and Example Lab likely see minor improvement since they already have low residual.

**Model:** This task is a good fit for a fast embedding-similarity approach (no heavy generation needed) or a lightweight classification call. A full Opus/Sonnet call per entity would be expensive; batching or embedding-based approaches are preferred.

---

## Denver special case

Denver Plumbing Consultants is explicitly **excluded from Phase 2 scope.** Its failure mode is not semantic but structural:

- Only 4 pages were crawled
- Niche detection returned "generic" (confidence 75%)
- The LLM entity extraction had insufficient content to identify real plumbing entities

The `analyze_workspace` API now returns a `low_content_warning` when `page_count < MIN_ANALYSIS_PAGES_FOR_CREATE_RECOMMENDATIONS` AND niche is generic. The correct path for Denver is:
1. Add more content to the site (blog posts, service pages)
2. Re-analyze after the site has ≥8 content pages
3. At that point, re-evaluate whether Phase 2 scoring helps

---

## Conclusion

**Phase 2 AI architecture review is now warranted for the three dense-content verticals.**

The deterministic pipeline has reached its practical ceiling. The remaining junk (12–24%) is composed of semantic failures that require relevance understanding. Two of three dense verticals have crossed both Phase 2 eligibility gates (Tortuga ~88%/~10%, Pragmatic ~84%/~12%). Plausible is within the margin of the semantic residual (~76%/~24%, with ~12% structural and ~12% semantic).

The specific AI task — entity domain relevance scoring — is well-defined, bounded in scope, and does not require architectural redesign of EOG/OI. It adds a new scoring signal that the existing OI pipeline can consume as a downranking or filtering step.
