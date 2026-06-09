# AI Editorial Strategist + Recommendation Reviewer Validation

Date: 2026-06-02

## Summary

**Conclusion: A) AI Editorial Strategist and Recommendation Reviewer implemented.**

Both layers are implemented as separate modules with independent configuration, fail-open behavior, and 4-way A/B validation support in `scripts/run_opportunity_quality_validation.py`.

## Architecture

- **Strategist** (`app/ai_editorial_strategist/`) runs before OI ranking and feeds `source_type=ai_editorial_strategist` candidates.
- **Reviewer** (`app/ai_recommendation_reviewer/`) runs after OI ranking and may adjust final actions while preserving `metadata.oi_action`.

See:

- [docs/architecture/AI_EDITORIAL_STRATEGIST.md](../architecture/AI_EDITORIAL_STRATEGIST.md)
- [docs/architecture/AI_RECOMMENDATION_REVIEWER.md](../architecture/AI_RECOMMENDATION_REVIEWER.md)

## Validation modes

| Mode | Strategist | Reviewer |
|---|---|---|
| baseline | off | off |
| strategist_only | on | off |
| reviewer_only | off | on |
| both | on | on |

Run:

```bash
python scripts/run_opportunity_quality_validation.py --ab-strategist-reviewer --refresh
```

Cohort sites (URL match): Example Lab, Plausible, Tortuga, Pragmatic.

## Metrics

- `product_category_alignment_rate` — CREATE titles matching known products/categories
- `off_topic_rate` — Facebook, Adhesives, Internet, Characteristics in CREATE queue
- `weird_create_count` — off-topic CREATE items
- `false_rejection_rate` — reviewer ignored items where product entity matches (both mode)

## Example Lab success criteria

CREATE queue should predominantly reference BPC-157, GHK-Cu, MOTS-C, Retatrutide, Kisspeptin, research peptide education, storage/reconstitution/FAQ/comparison topics — not Facebook, Adhesives, Internet, Characteristics.

Expected best mode: **both enabled** (strategist adds site-first ideas; reviewer removes residual junk).

## Automated tests

- `tests/test_ai_editorial_strategist_*.py`
- `tests/test_ai_recommendation_reviewer.py`
- `tests/test_opportunity_intelligence_discovery_strategist.py`
- `tests/test_config_env_sync.py`
- `tests/test_analyze_website_flow.py` (updated step list)

## Notes

Live cohort runs require analyzed workspaces and OpenAI credentials. The validation harness exports snapshots under `docs/validation/runs/<timestamp>/strategist_reviewer_ab/` when executed with `--refresh`.
