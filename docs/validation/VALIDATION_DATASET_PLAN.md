# Validation Dataset Plan

**Date:** 2026-06-01
**Purpose:** Part 2 — identify 3–5 real websites suitable for multi-vertical validation of the Trendplot EOG engine.
**Status:** Plan only. No analysis has been run. No workspaces have been created.

---

## Selection criteria

Each candidate must satisfy all of the following:

- Publicly crawlable (no authentication wall, no robots.txt blocking)
- A real functioning website with actual published content
- Not selected because Trendplot is expected to produce good output for it
- Represents a distinct business model / vertical bucket
- Ordinary website — not a media giant with atypical SEO structure

Sites that would make Trendplot look artificially good are excluded. Sites chosen from the bucket list
ensure the engine is tested against genuinely different content strategies and niche structures.

---

## Recommended candidates

### Candidate 1 — SaaS / software

**Target bucket:** SaaS / software tool
**Proposed site:** Plausible Analytics (plausible.io)

| Property | Value |
|---|---|
| Vertical | SaaS / analytics tool |
| Business model | Subscription SaaS |
| Content strategy | Technical blog, documentation-adjacent |
| GSC availability | No (Trendplot validation does not require GSC) |
| Crawlability | Public, standard sitemap |
| Why this site | Well-maintained blog in a specific niche (privacy-first analytics); entities are software/technical, not biomedical — exercises different entity extraction paths |
| Risk of artificial success | Low — SaaS content strategy is structurally different from peptide research; the engine has not been tuned on this vertical |

---

### Candidate 2 — Ecommerce

**Target bucket:** ecommerce / physical product
**Proposed site:** Tortuga Backpacks (tortugabackpacks.com)

| Property | Value |
|---|---|
| Vertical | Ecommerce — travel bags / accessories |
| Business model | Direct-to-consumer product sales |
| Content strategy | Buyer's guide and travel blog alongside product pages |
| GSC availability | No |
| Crawlability | Public, standard HTML |
| Why this site | Mid-size ecommerce with real editorial content alongside product catalog; exercises nav-label risk, product-entity handling, and category-level coverage gaps — patterns the engine has not been tested on |
| Risk of artificial success | Low — product catalog navigation structure is a known risk surface for nav-label CREATE recommendations; this is a stress test, not a cherry-pick |

---

### Candidate 3 — Local business

**Target bucket:** local business / services
**Proposed site:** A regional HVAC, plumbing, or landscaping company with a blog

**Rationale for not naming a specific site:** Local service businesses are common but individual company sites vary widely. The selection criterion is:

- A real regional business (not a national franchise)
- Has a "Resources" or "Blog" section with at least 10 published posts
- Business type: HVAC, plumbing, roofing, landscaping, or similar home services

**Suggested approach:** Find a site via Google ("HVAC company blog [city]") and confirm it has: a sitemap, >10 content pages, and no robots.txt blocking. Record the specific URL when the workspace is created.

| Property | Value |
|---|---|
| Vertical | Local service business |
| Business model | Lead generation / calls |
| Content strategy | SEO-driven FAQs and how-to content |
| GSC availability | Unlikely |
| Crawlability | Almost always public |
| Why this site | Exercises thin-niche entity extraction, local intent signals, and the engine's behavior when market data is sparse |
| Risk of artificial success | Low — local service content is structurally sparse; the engine may produce fewer recommendations, which is informative either way |

---

### Candidate 4 — Content site / publisher

**Target bucket:** content site / independent publisher
**Proposed site:** The Pragmatic Engineer (newsletter/blog at blog.pragmaticengineer.com or equivalent)

| Property | Value |
|---|---|
| Vertical | Independent tech publisher |
| Business model | Newsletter subscription / paid content |
| Content strategy | Long-form analysis; dense entity graph (software companies, tools, engineering concepts) |
| GSC availability | No |
| Crawlability | Public (at minimum, the free archive) |
| Why this site | Entity-dense niche with high-quality competitor content; exercises how the engine handles a workspace where most topics may already be covered by competitors — heavy MONITOR/REFRESH output is expected |
| Risk of artificial success | Low — if anything, the engine may produce conservative recommendations because coverage gaps are narrow; that is valid evidence, not a failure |

---

### Candidate 5 — Professional services

**Target bucket:** professional services / B2B
**Proposed site:** Clearbit (now Breeze by HubSpot) — or a mid-size B2B data/consulting firm

**Rationale:** B2B professional services websites exercise intent mapping for decision-maker audiences (commercial/awareness mix), and typically have authority-cluster content structures (thought leadership alongside product comparison pages).

**Alternative if clearbit.com is unsuitable:** any mid-size B2B consulting or data-services company with a blog publishing more than 20 articles per year.

| Property | Value |
|---|---|
| Vertical | B2B professional services / data |
| Business model | Enterprise SaaS / consulting |
| Content strategy | Thought leadership, category creation, comparison pages |
| GSC availability | No |
| Crawlability | Public |
| Why this site | Tests commercial-intent CREATE recommendations and whether the authority-cluster architecture handles B2B entity graphs correctly |
| Risk of artificial success | Moderate — B2B content is well-structured, which may make the engine look better; note this in the review |

---

## Minimum viable subset

If resource constraints require prioritizing, execute validation in this order:

1. **SaaS (Candidate 1)** — furthest from peptides in entity type; highest signal value
2. **Ecommerce (Candidate 2)** — exercises nav-label and product-catalog risks
3. **Local business (Candidate 3)** — sparse niche; stress-tests the low-signal path

Candidates 4 and 5 provide further coverage but are lower priority for the initial generalization gate.

---

## What this plan does NOT include

- Site-specific competitor URLs (to be determined at workspace creation time)
- Any analysis results (none have been run)
- Any assertion that the engine will perform well on these sites

The plan is a selection protocol. Actual results — good or bad — are the evidence.
