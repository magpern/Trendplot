# Domain classification

Analyze Website competitor discovery classifies every discovered domain before selection.
Classification is generic (TLD patterns, host categories, path hints) and does not use niche-specific blocklists.

## Categories

| Classification | Role |
| --- | --- |
| `competitor` | Commercial site eligible for competitor analysis |
| `authority_source` | Publisher or authority content |
| `academic_source` | Scientific or academic publication source |
| `government_source` | Government domain |
| `community` | Discussion or Q&A community |
| `tool` | Analytics, infrastructure, or SaaS tool |
| `marketplace` | Marketplace or large commerce platform |
| `social_or_owned` | Social host or owned brand channel |
| `directory` | Directory or listing site |
| `unknown` | Role unclear |

## Competitor analysis

Only domains classified as `competitor` enter the competitor selection pool.
Other domains are preserved in diagnostics as `other_discovered_domains` with `classification` and `reason`.

## Diagnostics

Per-domain example:

```json
{
  "domain": "pubmed.ncbi.nlm.nih.gov",
  "classification": "academic_source",
  "reason": "scientific or academic publication source"
}
```

Aggregate counts are exposed as `classification_counts`.

## Future reuse

Classification metadata is stored on discovery results for future authority research, citation discovery, community discovery, and trust signals. No additional consumers are implemented yet.
