# Connector — Current State (Trendplot Codebase)

Audit of what exists **before** plugin implementation. Updated to reflect **inventory-first**, Trendplot-initiated architecture.

## Document index

| Doc | Topic |
|-----|--------|
| [CONNECTOR_ARCHITECTURE.md](./CONNECTOR_ARCHITECTURE.md) | Layers, pull model, phase direction |
| [CONNECTOR_API_CONTRACT.md](./CONNECTOR_API_CONTRACT.md) | v1 endpoints including `/content/search` |
| [CONNECTOR_AUTH_LICENSING.md](./CONNECTOR_AUTH_LICENSING.md) | HMAC + Phase 4 licensing |
| [CONNECTOR_INVENTORY_SCHEMA.md](./CONNECTOR_INVENTORY_SCHEMA.md) | Payload shapes + lifecycle fields |
| [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md) | Long-term content management |
| [DRAFT_PUBLISHING_CONTRACT.md](./DRAFT_PUBLISHING_CONTRACT.md) | Drafts + required meta |
| [PRODUCT_ARTICLE_RELATIONSHIPS.md](./PRODUCT_ARTICLE_RELATIONSHIPS.md) | Core relationships |
| [INTERNAL_LINKING.md](./INTERNAL_LINKING.md) | Link candidates (Phase 3) |
| [RANKMATH_INTEGRATION_PLAN.md](./RANKMATH_INTEGRATION_PLAN.md) | Phase 3 |
| [PLUGIN_IMPLEMENTATION_ROADMAP.md](./PLUGIN_IMPLEMENTATION_ROADMAP.md) | Phases 1–4 |
| [TRENDPLOT_CONNECTOR_PREP_PLAN.md](./TRENDPLOT_CONNECTOR_PREP_PLAN.md) | Backend prep |

---

## Product path (simplified)

```text
Website analysis (crawl)
  → catalog / niche extraction
  → AI Opportunity Ideation
  → recommendations → schedule
  → draft generation (async)
  → optional WordPress publish
```

**Target with plugin:** analysis and ideation consume **plugin inventory first**; crawl is fallback.

---

## What exists

### WordPress REST (direct)

| Component | Path |
|-----------|------|
| Client | [`app/wordpress.py`](../../app/wordpress.py) |
| Auth | `WORDPRESS_BASE_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD` |
| Features | Draft/publish, categories, tags, Elementor template meta, media upload |

### Connector client (backend contract, no plugin yet)

| Component | Path |
|-----------|------|
| HTTP client | [`app/connectors/wordpress.py`](../../app/connectors/wordpress.py) |
| Schemas | [`app/connectors/wordpress_schemas.py`](../../app/connectors/wordpress_schemas.py) |
| HMAC signing | `_headers()` in connector client |
| Routes | `/connectors/wordpress/*`, `/api/connectors/wordpress/events` in [`app/api/routes.py`](../../app/api/routes.py) |

**Note:** Endpoint names differ from v1 contract (`/site-summary`, `/inventory/content`). Phase 1 plugin should implement v1 names + aliases.

### Provider routing

[`app/providers/registry.py`](../../app/providers/registry.py):

- `WORDPRESS_CONNECTOR_ENABLED=true` → connector primary
- `WORDPRESS_CONNECTOR_FALLBACK_TO_REST=true` → REST fallback

### Workspace connection (partial)

- Table `workspace_connections` in [`app/models.py`](../../app/models.py)
- Upsert on connector sync in [`app/autopilot/service.py`](../../app/autopilot/service.py) `sync_connector_inventory`
- Credentials still **global env** (`WORDPRESS_CONNECTOR_*`), not per-workspace secrets

### Events (Phase 4 scope)

- Table `connector_events` (migration `0005`)
- `POST /api/connectors/wordpress/events` — ingest only; **not required** for Phases 1–3 flows

### Content inventory (crawl)

| Component | Path |
|-----------|------|
| Model helpers | [`app/content_inventory.py`](../../app/content_inventory.py) |
| Sync | [`app/website_analysis.py`](../../app/website_analysis.py) `sync_content_inventory` → `workspace_content_inventory` |

Crawl-derived: titles, URLs, content types, topic fingerprints. **No** reliable Woo SKUs, Rank Math, or stock status.

### Product catalog (heuristic)

[`app/catalog/products.py`](../../app/catalog/products.py) — product names from `/product/{slug}/` URL patterns during crawl. **Not** Woo API.

### Draft generation

| Component | Path |
|-----------|------|
| Pipeline | [`app/services/jobs.py`](../../app/services/jobs.py) `_run_generation_job` |
| Async UI | [`app/analyze_ui.py`](../../app/analyze_ui.py) `POST /generate-article/async` |
| Output schema | [`app/article_schema.py`](../../app/article_schema.py) |

Artifacts: `structured_article_json`, `rendered_html`, `wordpress_presentation_metadata`, quality/sanity, humanization logs.

### Internal linking (heuristic)

[`app/internal_links.py`](../../app/internal_links.py) — injects product URL into markdown; **no** site-wide candidate API.

### Recommendation metadata (ideation)

[`app/ai_opportunity_ideation/parser.py`](../../app/ai_opportunity_ideation/parser.py):

| Field | In parser | Passed to generation |
|-------|-----------|----------------------|
| `abstract` | yes | via `opportunity_context` in analyze UI |
| `search_intent` | yes | yes |
| `content_type` | yes | yes |
| `related_products` | yes | yes |
| `target_audience` | yes | yes |
| `safety_notes` | yes | yes |

**Not** persisted to WordPress post meta today.

---

## Environment variables

From [`app/config.py`](../../app/config.py) / [`.env.example`](../../.env.example):

| Variable | Purpose |
|----------|---------|
| `WORDPRESS_BASE_URL` | REST base |
| `WORDPRESS_USERNAME` / `WORDPRESS_APP_PASSWORD` | REST auth |
| `WORDPRESS_CONNECTOR_ENABLED` | Use connector client |
| `WORDPRESS_CONNECTOR_BASE_URL` | Plugin site URL |
| `WORDPRESS_CONNECTOR_SITE_ID` | Site binding |
| `WORDPRESS_CONNECTOR_SECRET` | HMAC shared secret (Phase 1 plugin) |
| `WORDPRESS_CONNECTOR_FALLBACK_TO_REST` | Fallback |
| `ALLOW_LIVE_PUBLISH` | Live gate |

---

## What is missing

| Capability | Phase |
|------------|-------|
| WordPress plugin | 1+ |
| `GET /content/search` | 1 |
| Unified inventory → ideation | 1 |
| Per-workspace credentials | 1 prep |
| `PATCH /drafts`, Trendplot post meta | 2 |
| **Product/article relationships** | 2 (core) |
| Internal link candidates API | 3 |
| Rank Math read/write | 3 |
| License, heartbeat, webhooks | 4 |
| Plugin-independent duplicate detection | 1–2 (`content_hash` + search) |

---

## Primary gap vs goal

**Today:** Site understanding depends on **crawl** for products and pages.  
**Goal:** Plugin inventory is canonical → better ideation, duplicate avoidance (`/content/search`), scheduling, and linking.

See [PLUGIN_IMPLEMENTATION_ROADMAP.md](./PLUGIN_IMPLEMENTATION_ROADMAP.md) Phase 1 acceptance.
