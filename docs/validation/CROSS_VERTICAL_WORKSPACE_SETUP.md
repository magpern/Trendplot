# Cross-Vertical Workspace Setup

**Date:** 2026-06-01
**Purpose:** Record workspace IDs, setup outcomes, and competitor URLs for the 4 cross-vertical validation sites.
**Run ID:** `2026-06-01T125750Z`

---

## Workspace registry

| # | Vertical | Site | Workspace ID | Action | Status | Pages scraped | Recs | Niche detected |
|---|---|---|---|---|---|---|---|---|
| 1 | SaaS / software | https://plausible.io | `5b12397d-f7f6-4761-a852-964a9f732003` | created | `analyzed` | 9 | 80 | software (1.0) |
| 2 | Ecommerce | https://www.tortugabackpacks.com | `8466c34c-6195-44f7-818d-ad5dce33d369` | created | `analyzed` | 16 | 80 | fashion (1.0) |
| 3 | Local business | https://www.denverplumbingconsultants.com | `decb869c-93cd-400b-92f6-291ac9fe3ae8` | created | `analyzed` | 4 | 45 | generic (0.75) |
| 4 | Content publisher | https://blog.pragmaticengineer.com | `d6240535-a6cb-4e17-a5f4-7aaeefac7868` | created | `analyzed` | 16 | 80 | software (1.0) |

All workspaces reached `status=analyzed`. None required retry.

---

## Competitor URLs used

### Plausible Analytics (SaaS / software)
- **Site:** https://plausible.io
- **Competitor:** https://usefathom.com
- **Competitor:** https://simpleanalytics.com
- **Competitor:** https://matomo.org

### Tortuga Backpacks (Ecommerce)
- **Site:** https://www.tortugabackpacks.com
- **Competitor:** https://www.nomatic.com
- **Competitor:** https://www.peakdesign.com
- **Competitor:** https://aersf.com

### Denver Plumbing Consultants (Local business)
- **Site:** https://www.denverplumbingconsultants.com
- **Competitor:** https://www.neffandassociatesplumbing.com
- **Competitor:** https://www.denverplumbing.com
- **Note:** Only 2 competitors used; automated discovery was not available; 2 real Denver plumbing businesses were selected manually.

### The Pragmatic Engineer (Content publisher)
- **Site:** https://blog.pragmaticengineer.com
- **Competitor:** https://martinfowler.com
- **Competitor:** https://www.infoq.com
- **Competitor:** https://newsletter.pragmaticengineer.com
- **Note:** `newsletter.pragmaticengineer.com` is the same author's newsletter — included to observe cross-property competitor crawl behavior.

---

## Setup notes and crawlability observations

### Plausible
- Crawled successfully, 9 pages across main site and 3 competitors.
- **Warning:** Entity extraction pulled marketing copy (pricing values, CTAs, sentence fragments) as domain entities. See validation report for impact.
- No bot protection observed.

### Tortuga Backpacks
- Crawled successfully, 16 pages. Best crawl coverage in the cohort.
- **Warning:** Ecommerce page structure (category pages, product listings, promotional banners) produced navigation labels and product names as entities rather than editorial topics.
- Nav-label risk was confirmed: "Shopping Bag", "Best Sellers", "Bundle and Save", "Collection" appear in top-25 recommendations.

### Denver Plumbing Consultants
- **Sparse content site**: only 4 pages scraped.
- Niche detection failed — returned `generic` (confidence 0.75) rather than `plumbing` or `home services`.
- Produced 45 recommendations (vs 80 for denser sites), the smallest cohort output.
- **Significant quality degradation at sparse-content boundary**: recommend documenting minimum viable page count for reliable analysis.

### Pragmatic Engineer
- Crawled successfully, 16 pages across main blog and competitors.
- **Warning:** Competitor site (infoq.com) contributed taxonomy labels ("Articles about Microservices", "Podcasts about Service Mesh"), UI text ("Unlock the full InfoQ experience", "Don't have an InfoQ account?"), and navigation fragments as entities. These became recommendations.
- `newsletter.pragmaticengineer.com` was not suitable — it's a Substack paywall. Kept for documentation; content contribution minimal.

---

## Prior validation workspace (reference)

| Workspace | Vertical | Status | Notes |
|---|---|---|---|
| Example Lab (`2a71aaf6-...`) | Research / peptides | `analyzed` | 4-pass deterministic validation completed; baseline reference |

---

## Note on initial Plausible workspace

A Plausible workspace was created earlier in the session with competitors stored as a space-separated string instead of a JSON array (scripting error). That workspace was deleted before analysis ran. The workspace listed above (`5b12397d-...`) is the clean replacement with proper list storage.
