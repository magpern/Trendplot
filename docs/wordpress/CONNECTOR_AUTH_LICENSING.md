# Authentication and Licensing

## Phase placement

| Concern | Phase |
|---------|--------|
| HMAC request signing, connect-time credentials | **1** (minimum for inventory) |
| Full license validation, domain enforcement, heartbeat, revoke | **4** |

Phases 1–3 must work with **simple site pairing** only. Do not block inventory or publishing on license server availability until Phase 4.

---

## Trendplot-initiated auth (Phase 1)

Every Trendplot → plugin request includes:

```http
Authorization: Bearer {token}
X-Trendplot-Site-ID: {site_id}
X-Trendplot-Timestamp: {unix_seconds}
X-Trendplot-Signature: {hmac_hex}
```

### Signature base string

```text
{METHOD}\n{path}\n{timestamp}\n{sha256_hex(body)}
```

- `path` = `/wp-json/trendplot/v1/...` (no query string)
- Body empty for GET → hash of empty string
- Plugin rejects if `|now - timestamp| > 300` seconds (replay protection)

Implemented today in [`TrendplotWordPressConnectorClient._headers`](../../app/connectors/wordpress.py).

### Connect flow (Phase 1 simplified)

1. User enters site URL in Trendplot.
2. User installs plugin; opens **Connect** in WP admin.
3. Plugin displays one-time pairing code or pre-shared token (admin copies).
4. User pastes into Trendplot; Trendplot stores `site_id`, `token`, `secret` on workspace connection.
5. Trendplot calls `GET /health` and `GET /site-info` to verify.

**Deferred to Phase 4:** automated license check, domain whitelist, SaaS-initiated OAuth-style redirect.

---

## Credential model

| Secret | Stored on Trendplot | Stored on plugin |
|--------|---------------------|------------------|
| `site_id` | workspace_connections | options table |
| `bearer_token` | encrypted | options table |
| `signing_secret` | encrypted (HMAC verify on ingest only for plugin→Trendplot in Phase 4) | options table |

Plugin stores **only** what it needs to verify Trendplot requests. Trendplot never stores WP admin passwords if connector is used.

---

## Phase 4 — Licensing and lifecycle

### License validation

- Trendplot SaaS is **source of truth** for plan, seat count, domain allowlist
- Plugin heartbeat includes `license_status` cached from last Trendplot response
- Writes (`POST /drafts`, `POST /relationships`) may return `forbidden` if license expired

### Domain binding

- **One production domain** per license (configurable exception for `*.staging.*`)
- `GET /site-info` returns canonical `home_url`; Trendplot rejects mismatch

### Heartbeat (plugin → Trendplot)

```http
POST https://trendplot.example/api/connectors/wordpress/heartbeat
```

Body: `site_id`, `plugin_version`, `wp_version`, `inventory_revision`, `license_nonce`

Trendplot responds: `ok`, `license_valid`, `next_heartbeat_seconds`, optional `revoke`

**Optional:** failure does not stop Phase 1–3 pull sync if operator runs manual sync.

### Disconnect / revoke

- Trendplot admin: disconnect workspace → plugin token invalidated on next heartbeat
- Plugin admin: disconnect → clears secrets; Trendplot marks connection `disconnected`

### Key rotation

- Trendplot issues new `token` + `secret`; plugin accepts overlap window (old + new signatures valid 24h)

---

## Plugin → Trendplot events (Phase 4 only)

Existing: `POST /api/connectors/wordpress/events` with [`ConnectorEventRequest`](../../app/connectors/wordpress_schemas.py).

Use for: `content_inventory_changed`, `post_published` — **supplement** scheduled `GET /inventory`, not replace.

Auth: separate HMAC or signed JWT on event payload; verify `site_id` maps to workspace.

---

## Multi-domain licenses

Document product decision in SaaS billing (not plugin):

| Model | Behavior |
|-------|----------|
| Single site | One `home_url` |
| Agency | N sites, N `site_id`s |
| Staging | Child site_id linked to production license |

---

## Security checklist

- HTTPS only
- No secrets in query strings
- Rate limit unsigned `/health` if exposed
- Capability checks on every mutating endpoint
- Nonce for one-time pairing codes (Phase 1 admin UI)
