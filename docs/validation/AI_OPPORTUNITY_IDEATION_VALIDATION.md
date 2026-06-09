# AI Opportunity Ideation — Example Lab Validation

Run this comparison after enabling the feature against workspace `2a71aaf6-cc69-4663-be7f-7b13e50c3722`.

## Setup

**A — Baseline (deterministic + strategist)**

```env
AI_OPPORTUNITY_IDEATION_ENABLED=false
AI_EDITORIAL_STRATEGIST_ENABLED=true
```

Re-run recommendations from Analyze or `rerun_recommendations`.

**B — AI opportunity ideation**

```env
AI_OPPORTUNITY_IDEATION_ENABLED=true
```

Re-run analyze/recommendations (strategist skipped; ideation runs with cache on second run).

## Metrics to record

| Metric | A (baseline) | B (ideation) |
|--------|--------------|--------------|
| Ideas / recommendations generated | | |
| Catalog product coverage | | |
| Duplicate headline count | | |
| Generic/glossary classification count | | |
| Safety warnings in ideation run | | |
| Create vs monitor ratio | | |

## Product coverage

Compare ideation `product_coverage` in run metadata against sitemap catalog (expect TB-500, Tirzepatide, CJC-1295 No DAC + IPA, BPC-157, etc.).

## Top 25 sample (B)

Record from `ai_opportunity_ideation_opportunities` or recommendations with `source_type=ai_opportunity_ideation`:

1. _(headline — abstract — related_products — recommendation_type)_
2. …

## Qualitative assessment

- Are B recommendations more product-specific and search-intent focused than A?
- Does B reduce generic glossary-style EOG noise in the Create queue?
- Do reviewed recommendations retain safety-appropriate framing?

## Notes

- Second ideation run with unchanged brief should report `cache_hit` in metrics.
- EOG path is unchanged in both modes; compare ideation candidates vs EOG-sourced rows separately in OI output.
