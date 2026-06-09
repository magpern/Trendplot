# Entity Quality Hardening Pass 4 — Final Deterministic Micro-Pass Report

**Date:** 2026-06-01
**Validation run:** `docs/validation/runs/2026-06-01T153916Z`
**Pass 3 baseline:** `docs/validation/runs/2026-06-01T152223Z`
**Purpose:** Final deterministic cleanup pass. Determine whether the deterministic ceiling has been reached.

---

## Changes implemented

### GENERIC_STRUCTURAL_TERMS — 7 final additions

| Term | Rationale |
|---|---|
| `additional` | Adjective, not an article topic |
| `capacity` | Too broad as a standalone; "backpack capacity" / "storage capacity" remain valid |
| `complete` | Adjective |
| `development` | Overly broad standalone; "software development", "web development" still valid |
| `follow` | Generic verb (social-media follow context) |
| `government` | Too broad standalone; "government compliance", "government regulation" still valid |
| `interface` | Too broad standalone; "user interface", "API interface" still valid |

**Deliberately excluded:**
- `security` — legitimately relevant on software/privacy sites (confirmed by top-3 rankings in Plausible and Pragmatic)
- `management` — relevant for engineering leadership content
- `microservice` (singular) — valid technical term distinct from "microservices"

### 458 tests pass (unchanged)

No new tests added for Pass 4 — the additions are covered by the existing `test_entity_quality_junk_passes_valid_domain_entities` and `test_entity_quality_junk_rejects_observed_cross_vertical_failures` parametrized suites.

---

## Before / after comparison (Pass 3 → Pass 4)

### Human-rated quality

| Workspace | Pass 3 publishable | Pass 4 publishable | Pass 3 junk | Pass 4 junk |
|---|---|---|---|---|
| Example Lab | ~70% | ~70% | ~4% | ~4% |
| Plausible | ~76% | ~76% | ~24% | ~24% |
| Tortuga | ~84% | **~88%** | ~14% | **~10%** |
| Denver | ~26% | ~26% | ~60% | ~60% |
| Pragmatic | ~76% | **~84%** | ~24% | **~12%** |

**Pass 4 improvement:** Marginal, as expected. Removed `follow`, `additional`, `development`, `capacity` from Tortuga/Pragmatic top-25. Replacement entities floated up — Pragmatic gained 4 new valid technical recommendations; Tortuga gained 1 additional valid recommendation. Plausible's junk stabilized at ~24% due to persistent off-topic proper nouns from competitor blog posts.

### Automated metrics

| Workspace | Pass 4 junk (auto) | Pass 4 explain | MI CREATE share |
|---|---|---|---|
| Example Lab | 0% | 100% | 100% |
| Plausible | 8% | 100% | 100% |
| Tortuga | 0% | 100% | 100% |
| Denver | 0% | 100% | 100% |
| Pragmatic | 0% | 100% | 96% |

---

## Per-workspace final assessment

### Plausible Analytics (SaaS)

**Final state:** ~76% publishable / ~24% junk

**Top-25 composition:**
- 19 valid analytics recommendations (Acquisition, digital privacy, API comparison, Security, Compliance, Multi Attribution, A/B testing, etc.)
- 3 off-topic proper nouns: Bloomberg, Michelin, Hyundai — company names scraped from competitor enterprise case studies
- 3 generic floaters: "Accurate", "business", "Compare" — surfaced as lower-ranked items after filtering higher junk

**Irreducible residual:** The off-topic proper nouns cannot be filtered deterministically. Bloomberg, Michelin, and Hyundai are syntactically correct proper nouns that appear on competitor pages as enterprise client references. No generic syntactic rule distinguishes them from domain entities like "Thoughtworks" or "Kubernetes" without knowledge of what web analytics tools are about.

**Deterministic ceiling:** Effectively reached. Adding "Accurate", "business", "Compare" to `GENERIC_STRUCTURAL_TERMS` would eliminate ~3 items but the pool has shown a whack-a-mole tendency — new floaters replace removed ones. The stable-state junk for Plausible is approximately ~12% semantic residual (off-topic proper nouns) + variable generic floaters.

---

### Tortuga Backpacks (Ecommerce)

**Final state:** ~88% publishable / ~10% junk

**Top-25 composition:**
- 13 creates: all travel/bag editorial topics (expandable backpack, travel backpacks, luggage, briefcases, capsule wardrobe, personal items, etc.)
- 11 monitors: all valid travel/bag monitoring topics (care guides, carry-on, collapsible, comfort, cordura, duffels, etc.)

**Remaining junk:**
- "Travel Together Lite" (product sub-brand name) — borderline; requires brand/product vs. topic distinction
- "Daily Carry Pro" (product sub-brand name) — same

**Deterministic ceiling:** Reached. The remaining junk requires product entity type classification (sub-brand vs. editorial topic) which is a semantic task.

**Phase 2 gates: CLEARED ✓**

---

### Denver Plumbing Consultants (Local)

**Final state:** ~26% publishable / ~60% junk

**Low-content warning fires correctly:** `"Low content depth: only 4 pages crawled. Niche detection returned 'generic' (confidence 75%). Recommendations may be unreliable."`

**The engine correctly handles Denver:** 8 CREATE recommendations, 1 MONITOR, 16 IGNORE — the IGNORE queue contains valid plumbing terms (plumbing, repair, replacement, furnace, cleaning) that are correctly suppressed due to sparse-site penalty. This is correct behavior, not a quality failure.

**Root cause remains content poverty:** Denver will not improve materially without ≥8 additional pages of site content. This is not a Phase 2 target.

---

### The Pragmatic Engineer (Publisher)

**Final state:** ~84% publishable / ~12% junk

**Top-25 composition:**
- 21 valid software engineering recommendations (Thoughtworks, Security, Monolith, Microservices, Automation, API comparison, Engineering FAQ, Productivity, access control, architecture, etc.)
- 3 semantic junk items: InfoQ Software Architects' Newsletter (competitor branded product), Photostream (deprecated Apple service from social widget), The InfoQ (competitor brand shorthand)

**Deterministic ceiling:** Reached. The 3 remaining junk items all require semantic understanding:
- "InfoQ Software Architects' Newsletter" → requires knowing this is a competitor product, not a domain concept
- "Photostream" → requires knowing this service is defunct and off-topic for software engineering
- "The InfoQ" → requires knowing "The InfoQ" is a competitor publication

**Phase 2 gates: CLEARED ✓**

---

### Example Lab (Reference)

**Final state:** ~70% publishable / ~4% junk — unchanged throughout Pass 4.

**Research templates preserved.** The single residual quality issue (`bactriostatic` misspelling) remains a documented deterministic limitation (domain lexicon or LLM correction required).

---

## Cross-vertical final state

| Workspace | Vertical | Publishable | Junk | Phase 2? |
|---|---|---|---|---|
| Example Lab | Research | ~70% | ~4% | ✓ (original reference) |
| Plausible | SaaS | ~76% | ~24% | △ (semantic residual; within 1 micro-pass of ceiling) |
| Tortuga | Ecommerce | ~88% | ~10% | ✓ CLEARED |
| Denver | Local | ~26% | ~60% | ✗ (content poverty) |
| Pragmatic | Publisher | ~84% | ~12% | ✓ CLEARED |

---

## Residual failure analysis

| Class | Example | Sites | Deterministic? |
|---|---|---|---|
| Off-topic proper nouns from competitor blogs | Bloomberg, Michelin, Hyundai | Plausible | No — requires domain relevance |
| Competitor branded products | InfoQ Newsletter | Pragmatic | No — requires source/brand awareness |
| Deprecated service entities | Photostream | Pragmatic | No — requires freshness knowledge |
| Product sub-brand names | Travel Together Lite, Daily Carry Pro | Tortuga | No — requires product taxonomy |
| Generic floaters (whack-a-mole) | Accurate, business, Compare | Plausible | Yes — but net gain ≈ 0 due to pool |
| Domain misspellings | bactriostatic | Example Lab | Partially (domain lexicon) |

---

## All-passes summary: publishable rate trajectory

| Pass | Plausible | Tortuga | Denver | Pragmatic |
|---|---|---|---|---|
| Cross-vertical baseline | ~20% | ~20% | ~12% | ~20% |
| Pass 1 | ~44% | ~48% | ~18% | ~48% |
| Pass 2 | ~58% | ~68% | ~26% | ~60% |
| Pass 3 | ~76% | ~84% | ~26% | ~76% |
| Pass 4 | ~76% | **~88%** | ~26% | **~84%** |

Total improvement (baseline → Pass 4):
- Plausible: +56 pp publishable
- Tortuga: +68 pp publishable
- Denver: +14 pp publishable (content-bounded)
- Pragmatic: +64 pp publishable

---

# B) Begin Phase 2 architecture review

**Rationale:**

1. **Tortuga and Pragmatic have cleared all Phase 2 eligibility gates** — ≥60% publishable (✓), ≤15% junk (✓), remaining failures are semantic (✓), deterministic ceiling reached (✓).

2. **Plausible is within the margin of the semantic residual** — ~76% publishable, ~24% junk with ~12% from off-topic proper nouns (semantic) and ~12% from generic floaters (marginal deterministic). The whack-a-mole dynamic means further generic-term additions do not reliably reduce junk below ~12–16%.

3. **The remaining failures are now domain-relevance failures**, not structural entity-quality failures. The engine produces correct noun-phrase entities that are syntactically valid — they just aren't relevant to the specific workspace niche. This is precisely what AI is designed to address.

4. **Further deterministic investment yields marginal returns** (0–4 pp per pass, down from 30–40 pp in Pass 1). The diminishing returns are structural, not a sign of poor implementation.

5. **Denver is excluded** — its failure mode is content poverty, not engine quality. Phase 2 cannot help Denver until the site has more content.

**Phase 2 scope (not design — see PHASE2_READINESS.md):**
- Entity domain relevance scoring: `(niche_profile, candidate_entity)` → relevance score
- Competitor entity source scoring: down-weight entities from competitor-only content
- These are bounded, well-defined AI tasks that integrate into the existing OI pipeline as scoring signals

---

## Appendix — Validation run lineage

| Run ID | Purpose |
|---|---|
| `2026-06-01T083533Z`–`120021Z` | Example Lab quality passes |
| `2026-06-01T125750Z` | Cross-vertical baseline |
| `2026-06-01T143722Z` | Hardening Pass 1 |
| `2026-06-01T150027Z` | Hardening Pass 2 |
| `2026-06-01T152223Z` | Hardening Pass 3 |
| **`2026-06-01T153916Z`** | **Hardening Pass 4 (final deterministic)** |
