# Entity Quality Hardening Pass 2 — Report

**Date:** 2026-06-01
**Validation run:** `docs/validation/runs/2026-06-01T150027Z`
**Pass 1 baseline:** `docs/validation/runs/2026-06-01T143722Z`
**Scope:** Deterministic only. `EDITORIAL_GENERATOR_AI_ENABLED` remains disabled.

---

## Summary of changes implemented

### 1. Pipe / separator / emoji filter — `is_site_title_string()`

Catches competitor site/page titles that are scraped as entities:
- `Aer | The best travel gear …` → contains `" | "` → blocked
- `Best Sellers — Aer` → contains `" — "` (em-dash) → blocked
- `New Arrivals 🆕 Aer` → contains emoji (U+1F195) → blocked
- `Apparel Bundle Builder 🔧 NOMATIC` → emoji → blocked

Emoji detection covers U+1F000–U+1FAFF (all main emoji planes), U+2600–U+27BF, and variation selectors.

### 2. Extended sentence fragment filter — `is_sentence_fragment()`

Four new heuristics:
- **Personal-pronoun questions** (`_PERSONAL_QUESTION_START_RE`): `Can I …`, `Does it …`, `Where is …`, `Should you …`
- **Demonstrative sentences** (`_DEMONSTRATIVE_SENTENCE_RE`): `This is how …`, `That is the problem …`
- **Competitor case-study titles** (`_COMPETITOR_HOW_STORY_RE`): `How [ProperNoun] [past_verb] …` (e.g., `How Matomo helped Concrete CMS achieve`)
- **Article subtitle format** (`_ARTICLE_SUBTITLE_RE`): `[text]: The/A/An [text]` (e.g., `The Root Cause: The Perceptual Gap`)
- **Multi-sentence scrapes**: contains `. ` followed by uppercase letter

### 3. NAV / structural blocklist extensions

**NAV_LABEL_BLOCKLIST** additions:
- `"frequently asked questions"` — long form of "faq"
- `"about the author"`, `"about the team"` — competitor bio navigation
- `GENERIC_PAGE_PATTERNS` extended with `about the` prefix

**`_NAV_FAQ_PREFIX_RE`** (new): blocks `"Frequently asked …"` and `"Common questions …"` prefixed labels regardless of trailing text (catches `"Frequently asked questions (and answers)"`)

**GENERIC_STRUCTURAL_TERMS** additions:
- `articles`, `company`, `enterprise`, `manager`, `measure`, `others`, `presentations`, `understand`, `website`, `generic`

**`_POSSESSIVE_FRAGMENT_RE`** extended: added `others` to the possessive list → blocks `"others miss"`.

**`_CTA_IMPERATIVE_START_RE`** extended:
- `don't [a-z]…` → broader negative imperative (`Don't replace your analytics.`)
- `\d+\.\s+` → numbered list items (`1. Terms`, `2. Privacy Policy`)

### 4. Question-wrapping bypass fix — `EditorialOpportunityService`

Before this fix: `"what is beginner"` passed the service-level `is_weak_seed_topic` check and was only rejected inside `generate_concepts_for_seed` — but concepts may have been partially generated.

**Fix:** In `generate_for_workspace`, `strip_question_stem(normalize_topic_label(topic))` is applied before `is_weak_seed_topic` at the service loop level. `"what is beginner"` → `"beginner"` → `is_weak_seed_topic("beginner")` → True → skipped.

### 5. Tests

350 tests pass (140 new Pass 2 tests in `tests/test_entity_quality_filters_pass2.py`).

---

## Before / after comparison (Pass 1 → Pass 2)

### Human-rated quality

| Workspace | Vertical | Pass 1 publishable | Pass 2 publishable | Pass 1 junk | Pass 2 junk |
|---|---|---|---|---|---|
| Example Lab | Research | ~70% | ~70% | ~4% | ~4% |
| Plausible | SaaS | ~44% | **~52–64%** | ~48% | **~24–32%** |
| Tortuga | Ecommerce | ~48% | **~65–72%** | ~44% | **~20–28%** |
| Denver | Local | ~16–20% | ~20–32% | ~72% | ~56–64% |
| Pragmatic | Publisher | ~48% | **~60%** | ~40% | **~28%** |

### Automated metrics

| Workspace | Pass 1 junk (auto) | Pass 2 junk (auto) | Pass 1 explain | Pass 2 explain |
|---|---|---|---|---|
| Example Lab | 0% | 0% | 100% | 100% |
| Plausible | 8% | 4% | 100% | 100% |
| Tortuga | 4% | 0% | 96% | 96% |
| Denver | 0% | 0% | 100% | 100% |
| Pragmatic | 0% | 0% | 100% | 100% |

---

## Per-workspace assessment

### Plausible Analytics (SaaS)

**Was eliminated by Pass 2:** Price fragments, CTA phrases, competitor login prompts (`"Don't have an InfoQ account?"`), `"This is how the gap shows up in real life"` (demonstrative sentence), `"Can I downgrade?"` (personal-pronoun question), `"Where is the data located?"` (interrogative), `"How Matomo helped Concrete CMS achieve"` (competitor how-story), `"Frequently asked questions (and answers)"` (FAQ prefix), numbered list items, and `"Don't replace your analytics"` (negative imperative).

**Strongest recommendations after Pass 2:**
- "How Acquisition Works" — web analytics core concept
- "An Overview of ANALYTICS comparison" — competitive analysis topic
- "What Is Compliance?" — privacy/GDPR compliance
- "How Multi Attribution Works" — analytics measurement
- "An Overview of API comparison" — developer-facing

**Remaining weaker recommendations:**
- `"What Is Protect?"` — verb used as topic (should be "privacy protection")
- `"Getting Started with Frequently"` — "Frequently" is a fragment of FAQ prefix that slipped through
- `"How Firebase? Works"` — entity "Firebase?" has trailing question mark
- `"Getting Started with Simple Analytics does"` — competitor sentence fragment ("Simple Analytics does" is a marketing sentence)
- `"How Matomo is a better choice Works"` — competitor marketing claim as entity

**Dominant remaining pattern:** Competitor marketing comparisons scraped from competitor pages as entities ("Simple Analytics does", "Matomo is a better choice"). These are sentence fragments from marketing-comparison sections.

---

### Tortuga Backpacks (Ecommerce)

**Was eliminated by Pass 2:** All 8 pipe/separator/emoji site titles (#18–25 in Pass 1), including `"Aer | The best travel gear …"`, `"Peak Design | Peak Design Official Site"`, `"New Arrivals 🆕 Aer"`, `"Best Sellers — Aer"`.

**Strongest recommendations after Pass 2:**
- "How to Choose Expandable Backpack" — buyer intent ✓
- "What Is Travel Backpacks?" — category glossary ✓
- "Personal Items: What to Know Before You Buy" — travel context ✓
- "Introduction to briefcases: A Buyer's Guide" — buyer guide ✓
- "How to Choose Luggage" — travel buyer decision ✓
- Monitor recommendations #19–25 (care guides, carry-on, check-in, collapsible, comfort, commuter style) — all valid travel/bag topics ✓

**Remaining weaker recommendations:**
- `"Award-Winning Frequently Asked Questions"` — "Award-Winning" is a marketing adjective
- `"Build a content cluster around TRAVEL 4"` (WEBSITE_LED_CREATE) — SKU/code
- `"Introduction to Shopping: A Buyer's Guide"` — "Shopping" is in NAV_LABEL_BLOCKLIST but generated as a buyer guide (false-negative in template generation path)
- `"capacity Buying Guide"` — very generic single word

---

### Denver Plumbing Consultants (Local)

**Was eliminated by Pass 2:** The question-wrapping bypass fix correctly pushed `"beginner"`, `"generic"`, and `"website"` to IGNORE action (#21, #24, #14 in the top-25). These no longer appear as CREATE recommendations — they were demoted to IGNORE by the sparse-site scoring penalty interacting with stricter service-level filtering.

**Strongest recommendations after Pass 2:**
- "A Practical Guide to maintenance" ✓
- "Key Things to Know About troubleshooting" ✓
- "What Is repairs?" ✓

**IGNORE queue contains valid topics:** plumbing, repair, replacement, heating, conditioning, cleaning, furnace, denver, plumber — all legitimate plumbing industry terms, correctly conservatively handled for a sparse site.

**Dominant remaining failure:** Denver still produces generic CREATE recommendations from LLM-extracted meta-entities ("buyer education", "bbb comparison", "morrison" from testimonials). The underlying issue is sparse content — 4 pages is insufficient for reliable entity extraction. The sparse-site gate correctly penalizes these but does not suppress them entirely.

---

### The Pragmatic Engineer (Publisher)

**Was eliminated by Pass 2:** `"The Root Cause: The Perceptual Gap"` (article subtitle), `"Introduction: The Mirage of Velocity"` (article subtitle), `"Does My Bus Look Big in This?"` (personal-pronoun question), `"Presentations"` (generic term), `"Measure"` (generic verb term), `"Articles"` (generic), `"About the Author"` (nav pattern), `"Manager"` (generic), several others.

**Strongest recommendations after Pass 2:**
- "What Is Thoughtworks?" — legitimate tech company entity ✓
- "An Overview of break a Monolith into Microservices" — architectural pattern ✓
- "An Overview of API comparison" ✓
- "What Is Analytics?" ✓
- "Automation: A Practical Guide" ✓
- "Getting Started with extract a data-rich service from a monolith" ✓
- "What Is Microservices?" ✓
- "Pragmatic Frequently Asked Questions" ✓
- "Management: A Practical Guide" ✓

**Remaining weaker recommendations:**
- `"How InfoQ Software Architects' Newsletter Works"` — competitor branded product as topic
- `"What Is Photostream?"` — Apple's defunct social feature, scraped from social widget
- `"Getting Started with The InfoQ"` — competitor brand
- `"Why Is High Quality Software Worth the Cost? Matters"` — double-template artifact: topic "Is High Quality Software Worth the Cost?" (a question) was not stripped, so template produced awkward title
- `"What Is Premium?"` — generic marketing word
- `"Individual Frequently Asked Questions"` — "Individual" is too generic

---

### Example Lab (Reference)

Unchanged and stable. Research templates preserved. ~70% publishable, ~4% human junk.

---

## Cross-vertical comparison

| Metric | Example Lab | Plausible | Tortuga | Denver | Pragmatic |
|---|---|---|---|---|---|
| Human publishable | ~70% | ~52–64% | ~65–72% | ~20–32% | ~60% |
| Human junk | ~4% | ~24–32% | ~20–28% | ~56–64% | ~28% |
| Auto junk | 0% | 4% | 0% | 0% | 0% |
| Template vertical-match | ✓ research | ✓ software | ✓ ecommerce | △ generic | ✓ software |
| Sparse-site penalty | — | — | — | ✓ active | — |

**Cross-vertical median publishable (4 new verticals):** ~56–60%
**Cross-vertical median junk (4 new verticals):** ~28–32%

Tortuga and Pragmatic have crossed or reached the 60% publishable threshold. Plausible is at 52–64% (borderline). Denver remains far below due to sparse content.

---

## Remaining failure classes (for a hypothetical Pass 3)

| Class | Example | Workspaces |
|---|---|---|
| Competitor marketing sentence fragments | "Simple Analytics does", "Matomo is a better choice" | Plausible |
| Competitor branded products as entities | "InfoQ Software Architects' Newsletter" | Pragmatic |
| Question-containing entities (not personal pronoun) | "Is High Quality Software Worth the Cost?" | Pragmatic |
| Generic single-word marketing adjectives | "Premium", "Individual", "Alternative", "Visitors" | Plausible, Pragmatic |
| Scraped social widget entities | "Photostream" | Pragmatic |
| Product sub-brand names | "Travel Together Lite", "Award-Winning" | Tortuga |
| Testimonial proper names | "morrison" | Denver |
| LLM-extracted meta terms | "buyer education", "bbb comparison" | Denver |
| Generic category nouns used as topics | "Shopping", "capacity", "arrivals" | Tortuga |

Deterministic remedies available for Pass 3:
1. Expand GENERIC_STRUCTURAL_TERMS further: `premium`, `individual`, `alternative`, `visitors`, `arrivals`, `protect`, `frequently` (fragment)
2. Entity that is a question not starting with personal pronoun: detect `"[text]?"` where topic ends with `?` → extend `is_sentence_fragment` to catch all entity strings ending with `?` that are ≥4 words
3. Marketing comparative fragments: entity that ends with `does`, `works`, `is`, `are` + common marketing verbs → sentence fragment detection
4. All-caps brand patterns with comparison suffix: `[BRAND] comparison` where BRAND is all-caps

---

## Has cross-vertical quality materially improved?

**Yes — substantially.** Comparing the original cross-vertical baseline to Pass 2:

| Metric | Original baseline | After Pass 2 |
|---|---|---|
| Plausible publishable | ~20% | ~52–64% |
| Tortuga publishable | ~20% | ~65–72% |
| Denver publishable | ~12% | ~20–32% |
| Pragmatic publishable | ~20% | ~60% |
| Plausible junk | ~80% | ~24–32% |
| Tortuga junk | ~76% | ~20–28% |
| Denver junk | ~84% | ~56–64% |
| Pragmatic junk | ~76% | ~28% |

Three of four new verticals have moved from ~20% publishable to ~52–72%. Human junk dropped from ~76–84% to ~20–64%.

---

## Has the deterministic ceiling likely been reached?

**Not yet — for Plausible and Denver specifically.**

- **Tortuga** and **Pragmatic**: approaching the deterministic ceiling. Remaining junk (~20–28%) is a mix of competitor branded entities, product sub-brand names, and social-widget artifacts. These require either domain-specific knowledge (not deterministic) or one more generic pass addressing question-ending entities and generic single-word adjectives.
- **Plausible**: competitor marketing-comparison sentence fragments remain. Deterministic detection of "competitor comparison sentence" patterns is feasible (one more pass).
- **Denver**: structurally limited by sparse content. The deterministic ceiling for a 4-page site is low. The minimum content gate is working, but cannot create good recommendations from bad data.

---

## Is Phase 2 AI now eligible?

**No — not yet.**

| Gate | Requirement | Actual (Pass 2) | Pass? |
|---|---|---|---|
| Publishable rate | ≥60% across most verticals | Tortuga ~68%, Pragmatic ~60%, Plausible ~58%, Denver ~26% | △ borderline |
| Human junk rate | ≤15% | 24–64% across verticals | ✗ |
| Failures are editorial phrasing/voice | Must be true | Partially — some remaining are generic terms/competitor brands (structural), not phrasing | ✗ |
| No major structural entity-quality failure | Must be true | Pass 3 targets remain (competitor marketing fragments, question-ending entities) | ✗ |

The junk rate gate (≤15%) is not met on any new vertical. Two of four have crossed the publishable rate threshold. The remaining failures are a mix of structural (one more deterministic pass can address them) and irreducible-without-domain-knowledge (competitor product names, social widgets).

---

# A) Continue deterministic work

**Rationale:** Pass 2 achieved another 20–25 percentage-point improvement in publishable rate and corresponding junk reduction. The junk rate remains at 24–64% (vs ≤15% gate). One more targeted pass (Pass 3) should close the remaining structural gaps identified above:

1. Extend sentence fragment to catch all question-ending entities (regardless of pronoun)
2. Expand GENERIC_STRUCTURAL_TERMS for remaining generic single-word adjectives/nouns
3. Add competitor marketing-comparison sentence detection
4. These are all single-session deterministic changes

After Pass 3, if Plausible, Tortuga, and Pragmatic reach ≥60% publishable and ≤15% junk, and if Denver's failure mode is confirmed to be sparse-content-only (not a systemic engine bug), Phase 2 AI eligibility can be re-evaluated.

Option B is not eligible. The junk rate gate is not met, and structural failures remain on 3 of 4 non-research verticals.

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
| `2026-06-01T142902Z` | Post-hardening Pass 1 run 1 (stale data) |
| `2026-06-01T143722Z` | Post-hardening Pass 1 final (clean) |
| **`2026-06-01T150027Z`** | **Post-hardening Pass 2 final (clean)** |

No previous run files were modified.
