# Deterministic Ceiling Review

**Date:** 2026-06-01
**Validation run:** `docs/validation/runs/2026-06-01T153916Z`
**Context:** Post-Entity Quality Hardening Pass 4 (final deterministic micro-pass)

---

## Executive summary

The deterministic ceiling has been reached or nearly reached for all dense-content verticals. The remaining junk items are either:

1. **Off-topic proper nouns from competitor blog posts** — company names (Bloomberg, Michelin, Hyundai for Plausible) that appear in competitor case-study content and are indistinguishable from legitimate domain entities by syntactic rules alone.
2. **Competitor branded products** — product names (InfoQ Software Architects' Newsletter, Photostream) scraped from competitor pages.
3. **Whack-a-mole generic floaters** — as each generic term is added to `GENERIC_STRUCTURAL_TERMS`, a new slightly-different generic entity from the pool floats up. Diminishing returns have set in as of Pass 3.

The dense-content verticals (Plausible, Tortuga, Pragmatic) have stabilized in the 76–88% publishable range after five deterministic passes. The sparse-content vertical (Denver) is limited by content poverty rather than engine quality.

---

## 1. What deterministic improvements remain?

### Very small, marginal gains possible

**Three remaining generic single-word entities in Plausible top-25:**
- `"Accurate"` (adjective) → add to `GENERIC_STRUCTURAL_TERMS`
- `"business"` (overly generic standalone) → add
- `"Compare"` (verb as topic) → add

**Estimated gain:** Filters 3 items from Plausible top-25. Junk drops from ~24% to ~12% IF no new junk replaces them. Evidence from Passes 3–4 suggests new generics float up (whack-a-mole dynamic), so net gain may be 0–3 items.

### No further generic-term passes will eliminate the semantic residual

Bloomberg, Michelin, Hyundai (Plausible) and Photostream, InfoQ Newsletter (Pragmatic) cannot be filtered by any generic syntactic rule. These require knowledge of domain relevance. All deterministic structural failure classes (prices, CTAs, site titles, question entities, comparison fragments, sentence fragments, etc.) have been addressed.

---

## 2. Estimated maximum gain from remaining deterministic improvements

| Workspace | Current junk | Max achievable (deterministic) | Improvement |
|---|---|---|---|
| Plausible | ~24% | ~12–16% | ~8–12 pp |
| Tortuga | ~8–12% | ~8–12% | 0 pp (at ceiling) |
| Denver | ~60% | ~50–55%* | ~5–10 pp |
| Pragmatic | ~12% | ~12% | 0 pp (at ceiling) |
| Example Lab | ~4% | ~4% | 0 pp (at ceiling) |

*Denver's deterministic ceiling is approximately ~20–30% publishable / ~50–60% junk regardless of filter improvements, because the entity extraction input quality is bounded by 4 crawled pages and a "generic" niche profile. The limiting factor is data, not filters.

---

## 3. What failures are now semantic rather than structural?

### Class A: Off-topic proper nouns from competitor blog posts

**Examples:** Bloomberg, Michelin, Hyundai (in Plausible top-25)

**Why it survives:** The competitor websites (Matomo, Fathom, Simple Analytics) publish enterprise case studies mentioning large clients. The LLM entity extractor identifies these company names as entities from the competitor pages. They pass all syntactic filters because they are correctly formed proper nouns — there is no syntactic signal that distinguishes "Bloomberg uses Matomo" (client mention) from "Kubernetes" (domain concept).

**What is required:** Domain relevance scoring — given the workspace niche profile ("software analytics / privacy"), rank entities by relevance to the target domain. Bloomberg and Michelin would score near-zero for a web analytics tool; Thoughtworks would score high for a software engineering blog.

**Risk of deterministic false positive:** Any rule specific enough to catch "Bloomberg" would also reject "Thoughtworks" (Pragmatic) or valid ecommerce brand entities (NOMATIC for Tortuga). Generic rules cannot distinguish these.

### Class B: Competitor branded products

**Examples:** "InfoQ Software Architects' Newsletter", "The InfoQ" (Pragmatic)

**Why it survives:** The Pragmatic Engineer blog links to InfoQ (competitor newsletter). The LLM extracted "InfoQ Software Architects' Newsletter" as an entity. It is 38 characters (under the 55-char length gate), a valid noun phrase, and not a question, CTA, site title, or price.

**What is required:** Competitor-source entity scoring — entities that appear exclusively in competitor page crawls and not in the main site's content should be scored lower. The entity "InfoQ Software Architects' Newsletter" does not appear in the main site, only in competitor crawl.

**Risk of deterministic false positive:** Any rule that filters "proper noun + possessive + Newsletter" would also filter "Pragmatic Engineer Newsletter" (the workspace's own product) or "Kubernetes User Newsletter" (a legitimate domain entity).

### Class C: Deprecated / off-topic service entities

**Examples:** Photostream (Pragmatic)

**Why it survives:** Apple's Photostream service was embedded as a photo widget in older blog posts. The LLM extracted it as an entity. It is a valid proper noun, 12 characters, properly capitalized.

**What is required:** Freshness/relevance scoring — entities that refer to deprecated services or features that have been off-market for years score low. This requires either a knowledge cutoff check (AI) or a maintained blocklist (impractical to generalize).

---

## 4. Which failures require which type of understanding?

| Failure class | Understanding required |
|---|---|
| Bloomberg/Michelin/Hyundai as Plausible entities | Relevance understanding (is this entity relevant to web analytics?) |
| InfoQ Newsletter as Pragmatic entity | Competitor understanding (is this a competitor's product?) |
| Photostream as Pragmatic entity | Topic freshness (is this entity current and relevant?) |
| "Tortuga" as its own FAQ topic | Workspace/brand understanding (niche → brand entity → brand-FAQ) |
| Product sub-brand names (Travel Together Lite) | Niche understanding (product-brand vs. editorial topic) |
| Client mention entities from competitor content | Source/context understanding (client case study vs. domain entity) |

---

## 5. Is further deterministic work likely to produce marginal, moderate, or major gains?

**Marginal.** The trajectory is clear:

| Pass | Plausible junk | Tortuga junk | Pragmatic junk |
|---|---|---|---|
| Baseline | ~80% | ~76% | ~76% |
| Pass 1 | ~48% | ~44% | ~40% |
| Pass 2 | ~28% | ~24% | ~28% |
| Pass 3 | ~24% | ~14% | ~24% |
| Pass 4 | ~24% | ~10% | ~12% |

Pass 1 → Pass 2: ~30 pp improvement. Pass 2 → Pass 3: ~8 pp. Pass 3 → Pass 4: ~0–4 pp. The marginal return on additional deterministic passes is now in the 0–5 pp range for Tortuga and Pragmatic (which are at ceiling), and 5–12 pp for Plausible (if 3 more generic terms are added, with uncertain whack-a-mole effect).

**The total deterministic gain ceiling has been effectively reached for Tortuga and Pragmatic.**

---

## 6. Has the deterministic ceiling been reached?

### SaaS (Plausible): Nearly reached

- Current state: ~76% publishable / ~24% junk
- Estimated ceiling: ~76–80% publishable / ~12–16% junk
- Gap to ceiling: ~8–12 pp junk reduction possible with 3–5 more generic terms + no guarantee of whack-a-mole suppression
- Irreducible residual: 3 off-topic proper nouns from competitor enterprise blog posts (Bloomberg, Michelin, Hyundai) — semantic, cannot be addressed deterministically

**Ceiling reached? Effectively yes** — within one very small pass of the hard deterministic limit.

### Ecommerce (Tortuga): Ceiling reached

- Current state: ~88% publishable / ~10% junk
- Remaining junk: product sub-brand names (Travel Together Lite, Daily Carry Pro) — require brand/product entity understanding
- No further generic-rule passes will materially improve this

**Ceiling reached? Yes.**

### Publisher (Pragmatic): Ceiling reached

- Current state: ~84% publishable / ~12% junk
- Remaining junk: InfoQ Newsletter (competitor branded product), Photostream (deprecated service), The InfoQ (competitor brand) — all require semantic understanding
- No generic deterministic rule can safely remove these without false positives on "Thoughtworks", "Microservices", "Monolith"

**Ceiling reached? Yes.**

### Local business (Denver): Ceiling not reached — but not an engine problem

- Current state: ~26% publishable / ~60% junk
- Root cause: 4 pages crawled, niche detected as "generic", LLM entity extraction produces meta-structural words from thin content
- The engine is applying all filters correctly; the issue is input data quality
- Low-content warning now surfaces in the API response
- Adding more filters will not materially improve Denver until the site has more content

**Deterministic ceiling: ~20–30% publishable** regardless of filter quality. Further deterministic work on this vertical is not productive.

---

## 7. Summary table

| Vertical | Publishable | Junk | Det. ceiling | Residual type |
|---|---|---|---|---|
| Research (Example Lab) | ~70% | ~4% | Reached | Plausible domain-spelling (LLM needed) |
| SaaS (Plausible) | ~76% | ~24% | Nearly | Off-topic proper nouns from competitor blogs |
| Ecommerce (Tortuga) | ~88% | ~10% | Reached | Product sub-brand names |
| Publisher (Pragmatic) | ~84% | ~12% | Reached | Competitor branded products, deprecated services |
| Local (Denver) | ~26% | ~60% | N/A | Content poverty — not an engine problem |

---

## Appendix: Hardening progression

| Pass | Changes | Major impact |
|---|---|---|
| Pass 1 | Price/promo, CTA, competitor UI, competitor taxonomy, possessive fragments, overly-long entities, NAV expansion, template routing | −30–40 pp junk across all verticals |
| Pass 2 | Site-title separators/emoji, sentence fragments, personal-pronoun questions, article subtitles, competitor how-story, expanded blocklists, question-wrapping bypass | −10–20 pp junk |
| Pass 3 | Question-entity filter (`?` ending), marketing comparison fragments, 15 GENERIC_STRUCTURAL_TERMS, QUESTION_STEM extension, low-content warning | −4–10 pp junk |
| Pass 4 | 7 GENERIC_STRUCTURAL_TERMS additions (follow, additional, development, government, complete, interface, capacity) | ~0–4 pp junk (marginal) |
