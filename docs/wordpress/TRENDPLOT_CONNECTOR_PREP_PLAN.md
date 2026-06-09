# Trendplot Connector — Backend Prep Plan

Backend changes in `seo-booster` **before** or **in parallel with** plugin Phase 1. No plugin code in this repo.

Aligned with: **inventory quality is the primary value; publishing is secondary**, Trendplot-initiated V1 pulls.

**Phase 1 success metric (primary):** Complete, accurate inventory + working `/content/search` on a WooCommerce site without crawl — enabling better understanding, ideation, duplicate avoidance, refresh detection, scheduling, product awareness, and (later) internal linking.

**Phase 4 only:** heartbeat, webhooks, event delivery, license enforcement, bidirectional sync — must not block Phases 1–3.

### V1 interaction (backend client)

Implement client methods matching:

`GET inventory` → `GET products` → `GET posts` → `GET content/search` → (Phase 2+) `POST draft` → `PATCH draft` → `POST relationship` → (Phase 3) `GET internal-link-candidates`

No dependency on webhooks or event buses for these flows.

---

## 1. Site connection model

**Today:** Global `WORDPRESS_CONNECTOR_*` env vars; `workspace_connections` upsert on sync without per-site secrets.

**Target:**

| Column / field | Purpose |
|----------------|---------|
| `workspace_id` | FK |
| `connection_type` | `trendplot_connector` |
| `status` | `connected`, `degraded`, `disconnected` |
| `site_id` | Plugin site binding |
| `base_url` | Canonical WP URL |
| `credentials_encrypted` | token + secret (not plain env) |
| `capabilities_json` | From `/site-info` |
| `last_inventory_sync_at` | |
| `inventory_revision` | Plugin cursor/hash |

**Migration:** extend `workspace_connections` or add `workspace_connector_credentials`.

**Files:** [`app/models.py`](../../app/models.py), [`app/repositories.py`](../../app/repositories.py)

---

## 2. Connector client factory

- `TrendplotWordPressConnectorClient.for_workspace(workspace_id)` loads credentials from DB
- Update paths to v1 contract ([CONNECTOR_API_CONTRACT.md](./CONNECTOR_API_CONTRACT.md))
- Implement client method `content_search(query, content_types, limit)`
- Keep legacy aliases until plugin stable

**Files:** [`app/connectors/wordpress.py`](../../app/connectors/wordpress.py), [`app/providers/registry.py`](../../app/providers/registry.py)

---

## 3. Inventory sync job (Phase 1 priority)

**Job:** `sync_workspace_inventory(workspace_id)`

1. `GET /inventory` (+ paginate)
2. Normalize → [`workspace_content_inventory`](../../app/content_inventory.py) upsert
3. Merge products into catalog service for ideation
4. Record `last_inventory_sync_at`

**Trigger:**

- After workspace connect
- Before analyze flow (if stale > N hours)
- Manual button in Analyze UI

**Not** dependent on webhooks (Phase 4).

**Files:** [`app/autopilot/service.py`](../../app/autopilot/service.py), new `app/connectors/inventory_sync.py` (planned)

---

## 4. Content search + lifecycle (Phase 1)

Before ideation approval or draft generation:

```python
results = connector.content_search(
    query=headline,
    content_types=["post", "page"],
    modified_after=optional_iso,
    limit=20,
)
```

Use response fields: `trendplot_generated`, `related_products`, `word_count`, `modified_at`.

- Duplicate prevention
- Refresh / expansion / follow-up / clustering per [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md)

**Files:** ideation pipeline, [`app/analyze_ui.py`](../../app/analyze_ui.py) recommendations tab

---

## 5. Draft push job (Phase 2)

- Populate `trendplot_meta` per [DRAFT_PUBLISHING_CONTRACT.md](./DRAFT_PUBLISHING_CONTRACT.md)
- `POST /drafts` then `POST /relationships`
- Resolve `related_products` via inventory SKU/name → ID map

**Files:** [`app/services/jobs.py`](../../app/services/jobs.py) `_publish_to_wordpress`

---

## 6. Relationship push (Phase 2 — core)

After draft create:

- Call `POST /relationships` with resolved product IDs
- Update content plan item state

**Files:** same as draft push; [`app/repositories.py`](../../app/repositories.py) content plan items

---

## 7. Internal links (Phase 3)

- Call `GET /internal-link-candidates` in generation pipeline
- Feed [`InternalLinkService`](../../app/internal_links.py) or replace heuristic when candidates exist

---

## 8. UI connection status

Analyze UI / workspace header:

- Connected / degraded / disconnected pill
- Last inventory sync time
- “Sync now” button
- **No** license messaging until Phase 4

**Files:** [`app/analyze_ui.py`](../../app/analyze_ui.py), trendplot UI

---

## 9. Fallback matrix

| Connector | REST | Crawl |
|-----------|------|-------|
| Connected | skip | supplement gaps |
| Down + fallback enabled | primary publish | inventory |
| Down + no REST | fail publish | inventory only |

Config: existing `WORDPRESS_CONNECTOR_FALLBACK_TO_REST`.

---

## 10. Phase 4 prep (stub only)

- Heartbeat ingest route enhancement
- License service interface (no implementation in Phase 1–3 blocker)
- Do **not** wire event bus

---

## Testing plan

| Test | Phase |
|------|-------|
| Mock plugin inventory → ideation input | 1 |
| `content_search` duplicate detection | 1 |
| Draft + meta + relationships E2E | 2 |
| Link candidates in generated HTML | 3 |

---

## Dependencies

```mermaid
flowchart LR
  P1[Phase 1 inventory + search]
  P2[Phase 2 publish + relationships]
  P3[Phase 3 links + Rank Math]
  P4[Phase 4 license + heartbeat]
  P1 --> P2 --> P3 --> P4
```

Backend prep tracks plugin phases; Phase 1 backend work is **highest priority** for recommendation quality.
