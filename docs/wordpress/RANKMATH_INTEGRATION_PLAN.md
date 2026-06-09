# Rank Math Integration Plan

**Phase:** 3 — not implemented in plugin or Trendplot until inventory and publishing are stable.

**Principle:** Rank Math access **only through the plugin**. Trendplot never calls Rank Math PHP APIs directly.

**Graceful degradation:** If Rank Math inactive, `/site-info` reports `rankmath_active: false`; SEO fields omitted or null.

---

## Read (Phase 3a)

### GET /rankmath/meta

**Query:** `post_id` or `product_id`

**Response:**

```json
{
  "title": "",
  "description": "",
  "focus_keyword": "",
  "schema_type": "article",
  "canonical": "",
  "robots": { "index": true, "follow": true },
  "faq_schema": null
}
```

**Capability:** `read`  
**Error:** `capability_not_supported` if Rank Math missing

Use for:

- Inventory enrichment ([CONNECTOR_INVENTORY_SCHEMA.md](./CONNECTOR_INVENTORY_SCHEMA.md))
- Avoid focus keyword collision via `/content/search`

---

## Write (Phase 3b)

### POST /rankmath/meta

**Body:** `post_id`, fields to update (partial)

**Constraints:**

- Default: only posts with `_trendplot_content_source=trendplot` and `status=draft`
- Operator override flag for published posts (off by default)

**Fields Trendplot sets from generation:**

| Rank Math field | Trendplot source |
|-----------------|------------------|
| SEO title | `structured_article.meta_title` |
| Meta description | `structured_article.meta_description` |
| Focus keyword | `structured_article.primary_keyword` |
| Canonical | presentation metadata |
| Schema type | article / FAQ if FAQ sections present |

### FAQ schema

- If article has FAQ block, plugin may emit FAQ schema
- **Tentative** — verify against Rank Math version during implementation
- Feature flag `rankmath_faq_write`

---

## Version risk

Rank Math stores data in post meta keys that may change between major versions.

**Mitigation:**

- Plugin adapter class `RankMath_Adapter` with version probe
- Unit tests against 2+ Rank Math versions
- On unknown version: read-only mode, `warnings` in envelope

---

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Rank Math deactivated | Skip; generation continues |
| Write fails | Log warning; draft still created |
| Read fails | Omit `rankmath` in inventory item |

---

## Acceptance (Phase 3)

- Draft in WP admin shows Rank Math title/description/focus keyword matching Trendplot generation
- Site without Rank Math: no errors in analyze or publish path
