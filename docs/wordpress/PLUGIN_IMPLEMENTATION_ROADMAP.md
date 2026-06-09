# WordPress Plugin — Implementation Roadmap

Plugin code lives in a **separate repository** (not `seo-booster`).

**Priority:** **Inventory quality first. Publishing is secondary.** Phase 1 must deliver trustworthy products, posts, pages, taxonomies, lifecycle fields, and `/content/search` before invest in draft push.

---

## Phase 1 — Site connection + inventory

### Goals

- Connect WordPress site
- Verify connectivity
- Pull inventory (posts, pages, products, taxonomies)
- Establish versioned connector contract
- Enable duplicate detection via content search

### Plugin deliverables

| Item | Notes |
|------|--------|
| Plugin skeleton | `trendplot-connector` slug, autoload, uninstall hygiene |
| Admin connect screen | Site URL display, copy credentials, test connection |
| HMAC auth middleware | Verify Trendplot-signed requests |
| `GET /health` | Liveness + versions |
| `GET /site-info` | Site name, URL, timezone, WooCommerce/Rank Math flags |
| `GET /inventory` | Aggregated snapshot (posts, pages, products, categories, tags) |
| `GET /posts` | Paginated post list |
| `GET /pages` | Paginated page list |
| `GET /products` | Paginated WooCommerce products |
| `GET /content/search` | Query existing content before ideation/generation |

### Trendplot deliverables (prep, no plugin code here)

- Align [`TrendplotWordPressConnectorClient`](../../app/connectors/wordpress.py) paths to v1 contract
- Per-workspace connection record (see prep plan)
- Inventory sync job → `workspace_content_inventory`
- Wire ideation/schedule to plugin inventory when connected

### Tests

- Contract tests: mock plugin responses for each GET
- Integration: Example Lab-style Woo site, full inventory pull without crawl

### Risks

- Endpoint naming vs legacy client (`/site-summary`, `/inventory/content`) — alias in Phase 1
- Large catalogs: pagination and timeouts

### Acceptance criteria

**Trendplot can retrieve complete site inventory from a WooCommerce site without crawling.**

- Product names, SKUs, URLs, categories match Woo admin
- Posts/pages include slugs, status, modified dates, optional lifecycle fields (`generated_by_trendplot`, `content_hash`, `related_products`)
- `GET /content/search` returns duplicates, refresh candidates, and cluster-related posts
- **Primary success metric: inventory quality** — not draft creation
- Publishing readiness is proven only after inventory + search pass acceptance tests

### What inventory enables (Phase 1 exit)

- Better website understanding
- Better AI ideation
- Better scheduling
- Duplicate avoidance
- Refresh / expansion opportunity detection ([CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md))
- Product awareness for later relationships

---

## Phase 2 — Publishing + relationships

### Goals

- Push generated articles as drafts
- Update drafts without manual WP editing
- Upload media (featured + inline)
- **Manage product ↔ article relationships (core feature)**

### Plugin deliverables

| Item | Notes |
|------|--------|
| `POST /drafts` | Create draft; never auto-publish |
| `PATCH /drafts/{id}` | Update title, content, excerpt, taxonomies, Trendplot meta |
| `POST /media` | Upload binary |
| `POST /media/from-url` | Optional sideload |
| `POST /relationships` | Bidirectional product ↔ article links |

### Trendplot deliverables

- Extend `JobService` publish path with Trendplot metadata (see draft contract)
- Map `related_products` from ideation → Woo product IDs via inventory
- Relationship push after successful draft create

### Tests

- Draft create + PATCH idempotency (`external_job_id`)
- Media attach to draft
- Relationship dedup and reverse links on product

### Risks

- Elementor/template meta
- Product ID resolution from catalog names

### Acceptance criteria

Trendplot can:

- Create draft
- Update draft
- Attach products (relationships)
- Upload featured media

**without manual WordPress editing.**

**Product page:** related guides / comparisons / storage articles  
**Article page:** related products  

---

## Phase 3 — Internal linking + Rank Math

### Goals

- Suggest internal links from real site inventory
- Read/write SEO metadata when Rank Math is present

### Plugin deliverables

| Item | Notes |
|------|--------|
| `GET /internal-link-candidates` | Ranked URLs + anchor suggestions |
| `GET /rankmath/meta` | Read SEO fields for post/product |
| `POST /rankmath/meta` | Write SEO fields on draft (feature-flagged) |

### Trendplot deliverables

- Call link candidates during generation (before/alongside [`InternalLinkService`](../../app/internal_links.py))
- Merge Rank Math fields into draft push + presentation metadata

### Tests

- Rank Math active vs inactive site
- Link candidate relevance for product + topic query

### Risks

- Rank Math version drift — isolate in plugin adapter

### Acceptance criteria

Generated drafts can receive:

- Suggested internal links from plugin inventory
- SEO metadata (title, description, focus keyword) when Rank Math available

---

## Phase 4 — Licensing + heartbeat + webhooks

**Isolation:** Heartbeat, webhooks, event delivery, license checks, and bidirectional sync are **Phase 4 only**. Phases 1–3 must ship without them.

### Goals

- Production-grade connection lifecycle
- License and domain enforcement
- Optional freshness via events (supplement pull sync — never replace Trendplot-initiated pulls)

### Plugin deliverables

| Item | Notes |
|------|--------|
| License validation | Trendplot SaaS is source of truth |
| Heartbeat | Periodic `POST` to Trendplot with site + plugin version |
| Domain enforcement | One production domain per license (staging exception documented) |
| Site binding lifecycle | Connect, rotate keys, revoke |
| Change feed / webhooks | `post_updated`, inventory changed — **optional**; Trendplot may still pull on schedule |

### Trendplot deliverables

- License API integration
- `connector_events` ingestion (already stubbed in backend)
- Connection health UI

### Tests

- Revoked license blocks write endpoints
- Heartbeat failure marks workspace connection degraded

### Acceptance criteria

**Site connection remains healthy and license-aware.**

Core flows (inventory, publish, links) do **not** depend on webhooks; webhooks only improve staleness.

---

## Phase summary

| Phase | Focus | Primary metric |
|-------|--------|----------------|
| 1 | Inventory + search | **Primary:** inventory quality + `/content/search` (ideation-grade) |
| 2 | Drafts + **relationships** | End-to-end draft + product links |
| 3 | Links + Rank Math | SEO + internal links on drafts |
| 4 | License + heartbeat + webhooks | Operational hardening |

---

## Legacy backend mapping

Existing client paths (to alias or migrate in Phase 1):

| New | Legacy in Trendplot client |
|-----|---------------------------|
| `GET /site-info` | `GET /site-summary` |
| `GET /inventory` | `GET /inventory/content` + `/inventory/products` |
| `POST /drafts` | `POST /posts/draft` |

See [CONNECTOR_API_CONTRACT.md](./CONNECTOR_API_CONTRACT.md).
