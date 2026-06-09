# Sample article — prompt v2 comparison

**Generated:** 2026-06-04  
**Prompt:** `app/prompts/templates/article_generation.yaml` (version 2)  
**Artifact:** [`sample_article_generation_v2.json`](./sample_article_generation_v2.json)  
**Command:** `python scripts/generate_sample_article.py`

## Generation metrics (single call)

| Metric | v2 sample | Reference job `2509c670` (initial gen only) |
|--------|----------:|---------------------------------------------:|
| Model | gpt-5.4 | gpt-5.4 |
| Input tokens | 1,145 | 741 |
| Output tokens | 8,651 | 10,738 |
| Est. cost | $0.071 | $0.087 |
| Publishable word count | 2,934 | 3,117 |
| Sections | 11 | — |
| Internal links | 1 | — |

## Prompt v2 behaviors observed

- **Search intent:** Sections 0–1 answer storage directly (“Store bacteriostatic water correctly…” / “How to handle… after opening”).
- **Word count:** 2,934 words within 1800–3000 target (aim ~2400).
- **Product link:** `internal_links` includes natural link to product name/URL.
- **No `call_to_action` field** in output (schema-safe).
- **Tone:** Concrete, procedural sentences; limited stock AI phrasing in opening sections.

## Quality gate (pre-repair)

| Result | Detail |
|--------|--------|
| Passed | No |
| Errors | RUO disclaimer wording mismatch vs configured exact string; false-positive on word `treats` in “treat the container” |
| Warnings | Closing summary detection |

In the full pipeline, `apply_deterministic_quality_fixes` and optional repair would address RUO/link gaps without humanization.

## Regenerate

```bash
python scripts/generate_sample_article.py --output docs/validation/sample_article_generation_v2.json
```
