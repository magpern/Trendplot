# Market Intelligence Engine

## Purpose

The Market Intelligence Engine answers **what is happening in this niche** before Opportunity Intelligence decides what to publish. It is separate from:

| Layer | Role |
| --- | --- |
| `demand_observations` | Owned/measurable demand (Search Console metrics) |
| `trend_signals` | Trend-facing summaries for UI and trend discovery |
| `market_signals` | Normalized external and ecosystem evidence |
| `market_opportunity_candidates` | Evidence-backed editorial backlog (50–120 by default) |
| Opportunity Intelligence | Decision layer (create/refresh/expand/merge/monitor) |

**Design rule:** CREATE does not require Search Console. Market candidates are the primary CREATE source; Publishing Memory drives REFRESH/EXPAND/MERGE.

## Pipeline

1. **Market Brief** — niche, entities, audiences, pain points, competitors (`query_planner.py`)
2. **Query Planner** — provider-family queries (web, news, competitor, YouTube, trend)
3. **Providers** — normalize into `market_signals` + `market_signal_evidence`
4. **Clustering** — `market_topic_clusters` with confidence, freshness, velocity, novelty, relevance, saturation
5. **AI Market Strategist** — heuristic by default; optional OpenAI when `MARKET_AI_STRATEGIST_ENABLED=true`
6. **Opportunity Intelligence** — ingests `market_opportunity_candidates` first; scoring boosts `market_intelligence` source

## Providers (Phase 1–2)

| Provider | Flag | Notes |
| --- | --- | --- |
| `internal-context` | always on | Niche entities, audiences, trends, coverage gaps, competitor themes |
| `owned-demand` | `DEMAND_INTELLIGENCE_ENABLED` | Maps GSC rows to `owned_performance_signal` |
| `competitor-ecosystem` | `MARKET_PROVIDER_COMPETITOR_ENABLED` | Competitor snapshot themes |
| `web-search` | `MARKET_PROVIDER_WEB_ENABLED` + `ENABLE_EXTERNAL_RESEARCH` | Uses intelligence web adapter |
| `news` | `MARKET_PROVIDER_NEWS_ENABLED` | News-style web queries |
| `youtube` | `MARKET_PROVIDER_YOUTUBE_ENABLED` | YouTube adapter when configured |
| `scientific` | `MARKET_PROVIDER_SCIENTIFIC_ENABLED` | Gated by research-heavy verticals |
| `trend` | `MARKET_PROVIDER_TREND_ENABLED` | Trend adapter when configured |

Navigation labels (`Shop`, `Why Us`, `Product Variations`) are filtered or reframed in `filters.py`.

## API

| Method | Path |
| --- | --- |
| GET | `/developer/market/providers` |
| POST | `/developer/market/workspaces/{id}/discover` |
| GET | `/developer/market/workspaces/{id}/signals` |
| GET | `/developer/market/workspaces/{id}/candidates` |
| GET | `/developer/market/workspaces/{id}/runs` |
| GET | `/autopilot/workspaces/{id}/market-insights` |
| POST | `/autopilot/workspaces/{id}/market-intelligence/refresh` |

Workspace **analyze** runs market discovery automatically when enabled, then refreshes Opportunity Intelligence.

## Rollout Phases

1. **Foundation** — tables, protocol, internal + owned providers (current)
2. **Provider MVP** — enable web/news/YouTube with real API keys
3. **Clustering** — topic/entity/intent clusters with coverage context (current heuristic clustering)
4. **AI Strategist** — enable `MARKET_AI_STRATEGIST_ENABLED` for LLM backlog
5. **OI integration** — market-first CREATE, nav filtering (current)
6. **Planning** — feed clusters into calendar/strategy planner (future)

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Noisy web/news results | Evidence rows, confidence, clustering, dedupe |
| Overgeneral topics | Website brief as relevance filter, not sole source |
| Niche hardcoding | Scientific gating by vertical keywords only |
| Cost/latency | Query caps, async analyze, configurable max signals/candidates |
| Evidence hallucination | Candidates reference `source_signal_ids` + persisted evidence |
| Repetition | Cluster + intent-level dedupe before OI |
| Planner overload | OI selects subset; planner schedules best items |

## Success Criteria

- Zero-traffic workspaces get market-led CREATE recommendations without GSC.
- Recommendations shift from nav labels to educational, comparison, glossary, trend, and ecosystem topics.
- Each CREATE shows market evidence summary, source mix, relevance, confidence, and why now.
- Search Console improves prioritization but is not required for new-site backlog.

## Configuration

See `.env.example` keys prefixed with `MARKET_`. Run migrations:

```bash
alembic upgrade head
```
