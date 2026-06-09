# Entity Quality Hardening Pass 1 — Report

**Date:** 2026-06-01
**Validation run:** `docs/validation/runs/2026-06-01T143722Z/` (clean re-run after stale data purged)
**Baseline run:** `docs/validation/runs/2026-06-01T125750Z/` (pre-hardening cross-vertical run)
**Scope:** Deterministic only. `EDITORIAL_GENERATOR_AI_ENABLED` remains disabled. No OI/EOG architecture changes. No provider additions.

---

## Summary of changes implemented

### 1. New entity quality filters (`app/market_intelligence/filters.py`)

| Filter | Function | Caught in cross-vertical baseline |
|---|---|---|
| Price / promo value | `is_price_or_promo()` | "$15/month", "150/year", "2 MONTHS FREE", "20% OFF" |
| CTA / marketing sentence | `is_cta_phrase()` | "Ready to simplify?", "Get started", "Don't have an InfoQ account?", "Unlock the full InfoQ experience" |
| Competitor UI / taxonomy | `is_competitor_ui_text()` | "Articles about Microservices", "Podcasts about Service Mesh", "Subscribe to read" |
| Possessive/conjunction fragment | `is_possessive_or_conjunction_fragment()` | "your time", "and your visitors'", "our analytics" |
| Overly long entity (>55 chars) | `is_overly_long_entity()` | "Travel Backpack Pro 40L by Tortuga Award-Winning Carry On Bag" (62 chars) |
| Combined gate | `is_entity_quality_junk()` | Single top-level call replacing ad-hoc individual checks |
| Extended NAV_LABEL_BLOCKLIST | — | "Shopping Bag", "Best Sellers", "Bundle and Save", "Trending", "About Me", "What We Do" |
| Extended GENERIC_STRUCTURAL_TERMS | — | "according", "available", "beginner", "builder", "content", "official", "trending", "implementation", "provider/providers" |
| All-caps acronym exception | `is_navigation_label()` | Exempts "API", "SEO", "SQL" from the short-token nav gate |

### 2. Applied filters at all ingress points

| Ingress point | Change |
|---|---|
| `market_intelligence/providers/internal_context.py` | Entity, pain point, trend, competitor, coverage loops → `is_entity_quality_junk()` |
| `market_intelligence/providers/competitor.py` | Theme extraction → `is_entity_quality_junk()` |
| `opportunity_intelligence/discovery.py` | `_from_niche_profile`, `_from_existing_opportunities`, `_from_coverage`, `_from_competitors` → `is_entity_quality_junk()` |
| `editorial_opportunity/title_guards.py` | `is_weak_seed_topic` → `is_entity_quality_junk()` |

### 3. Minimum content gate

- New config: `MIN_ANALYSIS_PAGES_FOR_CREATE_RECOMMENDATIONS=8` (default)
- `OpportunityIntelligenceService.build_recommendations` accepts `analysis_page_count` and `min_pages_for_create`
- When page count < threshold, all CREATE candidates receive a -0.18 score penalty and `sparse_site_warning` metadata
- Autopilot service resolves page count from `analysis_pages` table and passes it to OI

### 4. Template routing by vertical/niche (`app/editorial_opportunity/generator.py`)

New `niche_category(niche: str) -> str` function routes to templates by vertical:

| Niche category | Detected from | Template style |
|---|---|---|
| `research_regulated` | peptides, pharmaceutical, biomedical… | Existing research templates (unchanged) |
| `software_saas` | software, saas, analytics, tech, devops… | "How X Works", "Getting Started with X", "An Overview of X" |
| `ecommerce` | fashion, retail, backpacks, apparel… | "X Buying Guide", "How to Choose X", "X: What to Know Before You Buy" |
| `local_services` | plumbing, HVAC, roofing, landscaping… | "Common X Problems", "When to Call a Professional for X", "A Homeowner's Guide to X" |
| `content_publisher` | news, media, publishing, newsletter… | "X Explained", "Understanding X", "Key Lessons from X" |
| `generic` | unknown/low-confidence niche | Conservative neutrals ("A Practical Guide to X", "Introduction to X") |

### 5. Tests

210 tests pass (`tests/test_entity_quality_filters.py` adds 80 new tests for Pass 1 filters).

---

## Before / after comparison

### Automated metrics

| Workspace | Before junk (auto) | After junk (auto) | Before explain | After explain |
|---|---|---|---|---|
| Example Lab | 0% | 0% | 100% | 100% |
| Plausible | 4% | 8%* | 100% | 100% |
| Tortuga | 0% | 4% | 100% | 96% |
| Denver | 0% | 0% | 100% | 100% |
| Pragmatic | 0% | 0% | 100% | 100% |

*Plausible automated junk rose from 4% to 8% because the NAV_LABEL detector now catches 2 items the old detector missed. The human junk rate fell sharply (see below).

### Human-rated quality

| Workspace | Vertical | Before publishable | After publishable | Before junk | After junk |
|---|---|---|---|---|---|
| Example Lab | Research/peptides | ~70% | ~70% | ~4% | ~4% |
| Plausible | SaaS/software | ~20% | ~44% | ~80% | ~48% |
| Tortuga | Ecommerce | ~20% | ~48% | ~76% | ~44% |
| Denver | Local business | ~12% | ~16-20% | ~84% | ~72% |
| Pragmatic | Publisher | ~20% | ~48% | ~76% | ~40% |

---

## Per-workspace assessment

### Plausible Analytics (SaaS)

**Before top-5:** "A Practical Guide to 150/year", "Introduction to 2 MONTHS FREE", "Current Research Areas Involving 15/month", "Ready to simplify your analytics?" (CTA), "How Researchers Approach Shopping Bag"

**After top-5:** "How Where your data disappears Works", "Getting Started with Acquisition", "What Is Understand?", "An Overview of digital privacy", "Getting Started with This is how the gap shows up in real life"

**Removed:** All price fragments, all CTA phrases, all competitor UI text (InfoQ account prompts, Articles about X taxonomy labels). Research templates replaced with software-appropriate templates.

**Strongest recommendations after hardening:** "What Is ANALYTICS?", "What Is Security?", "An Overview of ANALYTICS comparison", "How Behaviour Works", "An Overview of API comparison", "What Is Compliance?"

**Weakest recommendations after hardening:** "How Where your data disappears Works" (sentence fragment as topic), "What Is Understand?" (verb as topic), "Getting Started with This is how the gap shows up in real life" (long sentence fragment)

**Dominant remaining failure pattern:** Sentence fragments from marketing copy that are ≤5 words or start with question words not in the possessive filter ("Where", "How", "Can"). The entity extractor is still pulling incomplete sentences from the website text.

---

### Tortuga Backpacks (Ecommerce)

**Before top-5:** "How Researchers Approach Shopping Bag", "Introduction to Best Sellers for New Readers", "What Is Apparel? Research Overview", "How Researchers Approach Unsure Which Bag is Right For You?"

**After top-5:** "What Is Travel Together Lite?", "How to Choose Expandable Backpack", "Introduction to Daily Carry Pro: A Buyer's Guide", "Backpack Frequently Asked Questions", "What Is Travel Backpacks?"

**Removed:** "Shopping Bag" and "Best Sellers" (now in NAV_LABEL_BLOCKLIST), "Unsure Which Bag is Right For You?" (CTA question), "Bundle and Save" (nav label), "Best-Selling" (nav label). Research templates replaced with buyer-guide templates.

**Strongest recommendations after hardening:** "How to Choose Expandable Backpack", "What Is Travel Backpacks?", "Personal Items: What to Know Before You Buy", "Introduction to Backpacks: A Buyer's Guide", "What Is Luggage?", "briefcases Buying Guide", "How to Choose capsule wardrobes"

**Weakest recommendations after hardening:** Competitor site titles with pipes and emojis (#18–25): "Shop Backpacks, Travel Luggage and More | NOMATIC", "Apparel Bundle Builder 🔧 NOMATIC", "Aer | The best travel gear for wherever life takes you."

**Dominant remaining failure pattern:** Full competitor site/page titles with "|" separators and emojis — these are under 55 chars and are not in the blocklists. A pipe/separator filter would address these in Pass 2.

---

### Denver Plumbing Consultants (Local business)

**Before top-5:** "Understanding the Scientific Interest Around beginner", "Introduction to buyer education for New Readers", "What Is Website? Research Overview", "Current Research Areas Involving bbb comparison"

**After top-5:** "Key Things to Know About beginner", "Introduction to buyer education", "What Is Website?", "Understanding bbb comparison", "Introduction to morrison"

**Changes noted:** Research templates replaced with generic/conservative templates (niche still detected as "generic"). Sparse-site penalty applied — total recommendations reduced to 27 (vs 45 before), and lower-confidence topics pushed to "ignore" action.

**Strongest recommendations after hardening:** "What Is maintenance?", "What Is troubleshooting?", "Key Things to Know About repairs" — plus the monitor/ignore queue contains valid plumbing topics (drain, repair, replacement, furnace) that are correctly conservative.

**Weakest recommendations after hardening:** "What Is generic?" (the word "generic"), "Introduction to morrison" (a person's name from testimonials), "Key Things to Know About beginner" (still appearing — see §8 below)

**Dominant remaining failure pattern:** LLM-extracted meta/structural words and names from sparse website content. The Denver site has insufficient content for reliable entity extraction. The sparse-site gate correctly penalizes CREATEs and redirects to IGNORE actions, but cannot eliminate junk entities that entered via the LLM analysis step.

---

### The Pragmatic Engineer (Publisher)

**Before top-5:** "Introduction to content for New Readers", "What Is Thoughtworks? Research Overview", "A Practical Guide to InfoQ Software Architects' Newsletter", "Current Research Areas Involving about me", "Introduction to Don't have an InfoQ account? for New Readers"

**After top-5:** "What Is Thoughtworks?", "Getting Started with InfoQ Software Architects' Newsletter", "An Overview of When should we use Microservices?", "How Does My Bus Look Big in This? Works", "Productivity Frequently Asked Questions"

**Removed:** "Articles about Microservices" (taxonomy label), "Podcasts about Service Mesh" (taxonomy label), "Don't have an InfoQ account?" (competitor account prompt), "Unlock the full InfoQ experience" (paywall prompt). Research templates replaced with software-appropriate templates.

**Strongest recommendations after hardening:** "What Is Thoughtworks?", "An Overview of When should we use Microservices?", "Is High Quality Software Worth the Cost?", "API comparison", "What Is Automation?", "break a Monolith into Microservices: A Practical Guide", "extract a data-rich service from a monolith" — 7 genuinely publishable technical topics.

**Weakest recommendations after hardening:** "Getting Started with About the Author" (competitor bio navigation), "How The InfoQ Works" (competitor brand name as topic), "What Is Photostream?" (social widget scraped from blog)

**Dominant remaining failure pattern:** Competitor article titles and biographical/navigation elements ("About the Author", article headlines like "Does My Bus Look Big in This?") that are scraped as entities from competitor blog posts and not recognizable as non-topics by deterministic rules alone.

---

### Example Lab (Reference — unchanged)

No changes to Example Lab logic or data. Output is stable at ~70% publishable, ~4% junk, 6 content types represented. Research templates are correctly preserved for the research_regulated niche category.

---

## Cross-vertical comparison after hardening

| Metric | Example Lab | Plausible | Tortuga | Denver | Pragmatic | Gate |
|---|---|---|---|---|---|---|
| Human publishable rate | ~70% | ~44% | ~48% | ~16-20% | ~48% | ≥60% |
| Human junk rate | ~4% | ~48% | ~44% | ~72% | ~40% | ≤10% |
| Research templates absent from non-research | N/A | ✓ | ✓ | ✓ | ✓ | ✓ |
| Template vertical-match | ✓ research | ✓ software | ✓ ecommerce | △ generic | ✓ software | — |
| Sparse site penalty triggered | — | — | — | ✓ | — | — |

---

## Template routing assessment

**Are research templates gone from non-research verticals?** Yes.

- Plausible: "How Researchers Approach X", "Understanding the Scientific Interest Around X", "Current Research Areas Involving X" — eliminated. Replaced with "Getting Started with X", "An Overview of X", "How X Works".
- Tortuga: Research templates eliminated. Replaced with "How to Choose X", "X Buying Guide", "X: What to Know Before You Buy".
- Denver: Research templates eliminated. Generic-niche templates used ("Key Things to Know About X", "What Is X?", "Introduction to X").
- Pragmatic Engineer: Research templates eliminated. Software templates used ("Getting Started with X", "An Overview of X", "What Is X?").

**Are ecommerce/local/software templates appropriate?**
- Ecommerce (Tortuga): buyer-guide templates are topically appropriate and significantly better than "How Researchers Approach Shopping Bag".
- Software (Plausible, Pragmatic): software templates are appropriate in style; the remaining quality issue is entity selection, not template language.
- Local (Denver): generic templates are conservative and appropriate for a sparse/uncertain niche.

---

## Sparse-site behavior

**What happened to Denver?**
- Total recommendations: 27 (down from 45 in the pre-hardening run)
- Actions: 11 CREATE, 1 MONITOR, 13 IGNORE
- The sparse-site penalty (-0.18 score) downgraded CREATE confidence and shifted many topics to IGNORE
- The remaining CREATEs (#1–11) are still not high quality, but the volume of aggressive creates is reduced
- **Assessment:** The sparse-site gate is working as intended — it correctly signals low confidence and reduces CREATE volume. The underlying problem (poor entity quality from a sparse LLM analysis) cannot be resolved by a scoring penalty alone.

**Minimum viable content observation:** Denver had 4 crawled pages. At 4 pages, entity extraction by the LLM is too thin to produce reliable topics. The correct fix is to surface a user-facing warning when `analysis_page_count < MIN_ANALYSIS_PAGES_FOR_CREATE_RECOMMENDATIONS`, advising the operator to add more content before expecting high-quality recommendations.

---

## Known remaining failure classes (for Pass 2)

The following failure types were NOT eliminated by Pass 1 and represent the next priority:

| Class | Examples | Count in top-25 |
|---|---|---|
| Sentence fragments with "Where/How/When/Can" starts | "Where your data disappears", "Can I downgrade at any time?" | 4–6 per SaaS workspace |
| Competitor article titles | "Does My Bus Look Big in This?", "The Root Cause: The Perceptual Gap" | 2–3 per publisher workspace |
| Competitor nav/page titles with pipe/em-dash | "Aer \| The best travel gear...", "Peak Design \| Official Site" | 5–8 per ecommerce workspace |
| Competitor bio/meta elements | "About the Author", "Photostream" | 2–3 per publisher workspace |
| Product sub-brand names | "Travel Together Lite", "Daily Carry Pro", "Award-Winning" | 2–4 per ecommerce workspace |
| LLM-extracted structural words via question wrapping | "beginner" (entered as "what is beginner" signal, bypasses some filters) | 1–3 per sparse workspace |

**Root cause of question-wrapping bypass:** The `InternalContextMarketProvider` generates a `glossary_need` signal with `topic=f"what is {label}"` for each entity. "what is beginner" is not caught by `is_entity_quality_junk` (it's a 3-word phrase, not a price/CTA/nav/fragment). In EOG, `strip_question_stem("what is beginner")` → "beginner", and `is_weak_seed_topic("beginner")` catches it in `generate_concepts_for_seed`. However, the `is_weak_seed_topic` check in the EOG service loop (before calling `generate_concepts_for_seed`) checks the ORIGINAL topic "what is beginner" which passes — there is a filter gap between the service-level check and the generator-level check. A concept should not be generated when `strip_question_stem(topic)` yields a weak seed; the service-level check should apply the strip first.

**Fix for Pass 2 (deterministic):** In `EditorialOpportunityService.generate_for_workspace`, change the service-level seed check to apply `strip_question_stem` before `is_weak_seed_topic`:
```python
stripped = strip_question_stem(normalize_topic_label(topic))
if is_weak_seed_topic(stripped, ...):
    continue
```

---

## Decision

**Has the deterministic ceiling been reached for multi-vertical?**

Not yet. The main structural entity failures (prices, CTAs, competitor UI prompts) are eliminated. A new tier of failures emerged: sentence fragments, competitor article titles, site-title strings with pipes. These are the next structural bottleneck. They are detectable without AI (pipe/separator detection, sentence-starting-question filter, length+separator combined rule).

**Is Phase 2 AI refinement now justified?**

No.

| Gate | Requirement | Actual after Pass 1 | Pass? |
|---|---|---|---|
| Publishable rate | ≥60% across verticals | 16–48% (3 of 4 new verticals under 60%) | ✗ |
| Human junk rate | ≤10–15% across verticals | 40–72% | ✗ |
| Failures are editorial phrasing/voice | Must be true | False — sentence fragments and competitor scrapes are structural | ✗ |
| No major structural entity-quality issue | Must be true | False — pipe/separator titles, question-fragment bypass remain | ✗ |

Example Lab remains the only workspace with quality suitable for Phase 2 consideration, and it was already there. No new vertical has crossed the Phase 2 threshold.

---

# A) Continue deterministic work

**Rationale:** Pass 1 achieved a 20–30 percentage-point improvement in publishable rate and a similar reduction in junk across the 3 denser new verticals. The remaining failures are a clearly identified second structural tier with deterministic solutions:

1. **Pipe/separator filter**: Reject entities containing `|` or ` — ` (em-dash with spaces) — catches competitor site titles
2. **Sentence-question filter (extended)**: Extend the possessive fragment check to all words ≤6 that start with interrogative words ("Where", "Can", "Do", "Is", "How", "What") — note "What Is X" is already handled by strip_question_stem
3. **Competitor article title detection**: Multi-word entities that are full sentences (contain a subject, verb, object structure or are clearly article headlines) — heuristic: contains a finite verb not in the domain
4. **Question-wrapping bypass fix**: Apply `strip_question_stem` before `is_weak_seed_topic` in the EOG service loop (1-line fix)
5. **Denver minimum content warning**: Surface a UI warning when `page_count < threshold`, so operators know their recommendations are low-confidence

These are all deterministic, low-risk changes. Only after Pass 2 hardening — and if the resulting cross-vertical publishable rate reaches ≥60% on ≥3 verticals with junk ≤15% — should Phase 2 AI design be considered.

---

## Appendix — Validation run lineage

| Run ID | Purpose |
|---|---|
| `2026-06-01T083533Z` | Example Lab baseline |
| `2026-06-01T112607Z` | EOG Quality Pass 1 |
| `2026-06-01T114544Z` | EOG Quality Pass 2 |
| `2026-06-01T115905Z` | Validation-Expansion Part 1 |
| `2026-06-01T120021Z` | Validation-Expansion Part 1 final |
| `2026-06-01T125750Z` | Cross-vertical baseline (pre-hardening) |
| `2026-06-01T142902Z` | Post-hardening run 1 (stale data present) |
| **`2026-06-01T143722Z`** | **Post-hardening final (clean state, all 5 workspaces)** |

No previous run files were modified.
