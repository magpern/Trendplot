# Web Search Provider Configuration

## Summary

Competitor discovery can use an external **web search provider** when configured. Providers implement `search_web()` and are injected at application startup into `CompetitorDiscoveryService`.

Without a configured provider, discovery continues using crawl fallbacks, workspace history, and snapshots only (fail-open).

**Conclusion: A) Web-search providers implemented (Brave Search + DuckDuckGo)**

---

## Supported providers

| Provider | Config value | API key | Implementation |
|----------|--------------|---------|----------------|
| Brave Search API | `WEB_SEARCH_PROVIDER=brave` | Required (`BRAVE_SEARCH_API_KEY`) | [`app/intelligence/brave_search.py`](../intelligence/brave_search.py) |
| DuckDuckGo (via `ddgs`) | `WEB_SEARCH_PROVIDER=duckduckgo` | None | [`app/intelligence/duckduckgo_search.py`](../intelligence/duckduckgo_search.py) |

Serper, Bing, and Google HTML scraping are not implemented. The factory returns `None` for unknown provider values.

### DuckDuckGo vs Brave

| | DuckDuckGo | Brave |
|---|------------|-------|
| API key | Not required | Required |
| SLA | Best-effort; unofficial scraping/metasearch | Official Brave Search API |
| Best for | Dev, self-hosted, validation, light usage | Production when you want a stable configured provider |
| Failure mode | Fail-open (`[]`); analysis continues | Fail-open (`[]`); analysis continues |

DuckDuckGo uses the [`ddgs`](https://pypi.org/project/ddgs/) package (successor to `duckduckgo-search`). It is **not** mandatory; set `WEB_SEARCH_PROVIDER=` empty to disable web search.

---

## Required environment variables

### Feature flags (required for web search to run)

| Variable | Default | Role |
|----------|---------|------|
| `ENABLE_EXTERNAL_RESEARCH` | `false` | Master external research switch |
| `MARKET_PROVIDER_WEB_ENABLED` | `false` | Enables web-search eligibility |
| `WEB_SEARCH_PROVIDER` | empty | `brave` or `duckduckgo` |

### Brave-only

| Variable | Default | Role |
|----------|---------|------|
| `BRAVE_SEARCH_API_KEY` | empty | Brave API subscription token |
| `WEB_SEARCH_TIMEOUT_SECONDS` | `10` | HTTP timeout per query |

### DuckDuckGo-only

| Variable | Default | Role |
|----------|---------|------|
| `DUCKDUCKGO_SEARCH_TIMEOUT_SECONDS` | `10` | Per-query timeout (async wrapper + `ddgs` client) |
| `DUCKDUCKGO_SEARCH_MAX_RESULTS` | `10` | Max results cap per query |

### Shared tuning

| Variable | Default | Role |
|----------|---------|------|
| `EXTERNAL_RESEARCH_MAX_RESULTS_PER_QUERY` | `5` | Max results requested per query |
| `COMPETITOR_DISCOVERY_MAX_QUERIES` | `5` | Max competitor discovery queries |

---

## Example configuration

### DuckDuckGo (no API key — recommended for dev/self-hosted)

```env
ENABLE_EXTERNAL_RESEARCH=true
MARKET_PROVIDER_WEB_ENABLED=true
WEB_SEARCH_PROVIDER=duckduckgo
DUCKDUCKGO_SEARCH_TIMEOUT_SECONDS=10
DUCKDUCKGO_SEARCH_MAX_RESULTS=10

COMPETITOR_DISCOVERY_ENABLED=true
COMPETITOR_DISCOVERY_MAX_QUERIES=5
COMPETITOR_DISCOVERY_MAX_COMPETITORS=3
COMPETITOR_TOTAL_MAX_COMPETITORS=5
```

### Brave (production-oriented)

```env
ENABLE_EXTERNAL_RESEARCH=true
MARKET_PROVIDER_WEB_ENABLED=true
WEB_SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=your_brave_api_key_here
WEB_SEARCH_TIMEOUT_SECONDS=10
```

Obtain a Brave Search API key from [Brave Search API](https://brave.com/search/api/). Restart the application after changing env vars.

---

## How competitor discovery chooses a provider

```text
main.py
  └─ build_web_search_provider(settings)
       ├─ WEB_SEARCH_PROVIDER=brave      → BraveSearchProvider(settings)
       ├─ WEB_SEARCH_PROVIDER=duckduckgo → DuckDuckGoSearchProvider(settings)
       └─ empty / unknown                → None

AutopilotService(..., web_search_provider=provider)
  └─ CompetitorDiscoveryService(settings, web_search_provider=provider)
       └─ _web_search_available()
            ├─ provider.is_configured()
            ├─ ENABLE_EXTERNAL_RESEARCH=true
            └─ MARKET_PROVIDER_WEB_ENABLED=true
```

When available, discovery runs queries from workspace name, niche hint, and brief entities, extracts URLs from normalized results, then applies existing filters (same-domain, social, directories, marketplaces, dedupe, caps). **No separate DuckDuckGo competitor logic** — the same web-search path is used for all providers.

---

## Normalized result contract

All providers return:

```json
{
  "source_type": "web",
  "query": "...",
  "title": "...",
  "url": "...",
  "snippet": "...",
  "domain": "...",
  "provider": "duckduckgo",
  "status": "ok",
  "verified": false
}
```

(`provider` is `brave-search` for Brave.)

---

## Diagnostics fields

When discovery completes, `competitor_discovery` includes:

```json
{
  "provider_name": "duckduckgo",
  "web_search_enabled": true,
  "web_search_attempted": true,
  "queries_run": 5,
  "raw_results_count": 23,
  "candidates_found": 8,
  "selected_count": 3,
  "provider_error": null,
  "web_search_summary": "Web search attempted using DuckDuckGo. Found 23 results, 8 candidates, selected 3."
}
```

### UI messages

| Condition | Message |
|-----------|---------|
| DuckDuckGo success | `Web search attempted using DuckDuckGo. Found X results, Y candidates, selected Z.` |
| DuckDuckGo empty / error | `DuckDuckGo search failed or returned no usable results. Analysis continued.` |
| Brave success | `Web search attempted using Brave Search. Found X results, ...` |
| Brave, key empty | `Web search skipped: API key missing` |
| Provider empty | `provider not configured` |
| Flags off | `external research disabled` / `web market provider disabled` |

Failures never abort the analyze run.

---

## How to verify configuration

1. Set env vars for `duckduckgo` or `brave`.
2. Restart Trendplot.
3. Run **Analyze Website** on a first-run workspace (no provided competitors).
4. Open **Competitor discovery** → **Details**.
5. Expect for DuckDuckGo:
   - `web_search_enabled: true`
   - `web_search_attempted: true`
   - `provider_name: duckduckgo`
   - `sources_checked` includes `web_search`

---

## Limitations

- DuckDuckGo has no official SLA; rate limits and blocks are handled fail-open.
- Brave remains the more stable option when you have an API key.
- Market intelligence and research enrichment do not yet share this provider instance (competitor discovery only).
- Tests mock all live DuckDuckGo/Brave calls.

---

## Dependency

```text
ddgs>=9.0
```

Listed in `requirements.txt`. Install with `pip install -r requirements.txt`.

A) Web-search providers implemented
