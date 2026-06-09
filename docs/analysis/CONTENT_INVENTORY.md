# Content inventory

Workspace content inventory tracks pages seen on the customer site and content created by Trendplot so Opportunity Intelligence can avoid duplicate **CREATE** recommendations.

## Storage

Table: `workspace_content_inventory` (per workspace, keyed by `canonical_url`).

Each row includes:

| Field | Description |
|-------|-------------|
| `url` / `canonical_url` | Page location |
| `title`, `slug` | Display and path identity |
| `content_type` | `article`, `product`, `category`, `faq`, `utility`, `unknown` |
| `source` | `existing_site`, `trendplot_generated`, `wordpress_import`, `unknown` |
| `created_by_trendplot` | Boolean flag |
| `generated_job_id` | Article generation job when applicable |
| `wordpress_post_id` | WordPress post ID when known |
| `topic_fingerprint` | Normalized title/slug fingerprint |
| `coverage_topics` | Title + extracted entities |
| `last_seen_at` | Updated on every crawl sync |

## Population

1. **Website crawl** — after analysis pages are saved, crawled pages upsert into inventory (`existing_site`).
2. **Prefetch crawl** — pre-discovery crawl in Analyze Website also syncs inventory.
3. **WordPress publish** — when Trendplot publishes a draft/live post, inventory + `published_content` are updated with `trendplot_generated` metadata.

Trendplot does not rely on visible page text alone; DB flags and job/post IDs identify generated content on later crawls.

## Duplicate-topic handling

Before finalizing a **CREATE** recommendation, Opportunity Intelligence checks inventory using:

- `topic_fingerprint` equality
- Normalized title similarity (≥ 0.88)
- Slug match
- Entity/topic overlap on `coverage_topics`

**Product**, **category**, and **utility** pages do not block editorial CREATE unless the candidate clearly matches them.

### Outcomes

| Situation | Action |
|-----------|--------|
| Duplicate Trendplot article | `refresh` — rationale cites existing Trendplot URL |
| Duplicate site article with gaps | `expand` — FAQ/schema/internal links |
| Related but distinct angle | `expand` with `expansion_kind: follow_up` |
| No match | Original `decide_action` result |

Example explanation:

```text
Not recommended as CREATE because an existing Trendplot article already covers this topic:
https://example.com/peptide-reconstitution-guide/

Suggested action:
Refresh existing article with competitor FAQ gaps.
```

## Re-crawl

`last_seen_at` is refreshed whenever the same canonical URL is seen again. Stale rows remain for pages no longer in sitemap until manually cleaned (future work).
