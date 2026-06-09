# Phase 2A Entity Relevance Scoring — Production Monitoring Dashboard

**Date:** 2026-06-01
**Feature flag:** `ENTITY_RELEVANCE_SCORING_ENABLED`
**Status:** Ready for production rollout
**Reference:** `docs/validation/PHASE2A_CONTROLLED_ENABLEMENT_REPORT.md`

---

## 1. Key metrics to collect and visualize

### 1.1 Model execution

| Metric | Type | Normal range | Collection |
|---|---|---|---|
| `model_calls` | Counter | 0–10/workspace/run | Per analysis, cumulative per day |
| `cache_hits` | Counter | 140–150/workspace/run (warm) | Per analysis, daily total |
| `cache_misses` | Counter | 0–150/workspace/run (cold) | Per analysis, daily total |
| `fallback_count` | Counter | 0 (per run) | Per analysis; alarm if >0 |
| `cache_hit_rate` | Gauge | 0.95–1.0 (steady-state) | Daily: `hits / (hits + misses)` |

**Collection point:** `app/entity_relevance/service.py`, logged in OI summary metrics block.

### 1.2 Filtering and scoring

| Metric | Type | Normal range | Collection |
|---|---|---|---|
| `filtered_by_relevance` | Counter | 30–50/workspace | Per analysis |
| `down_ranked_by_relevance` | Counter | 20–40/workspace | Per analysis |
| `entities_scored` | Counter | 32–150/workspace | Per analysis |
| `entities_requested` | Counter | 32–150/workspace | Per analysis |

**Interpretation:**
- Filter rate (filtered / entities_scored): 0.25–0.35 = healthy
- Down-rank rate (down_ranked / entities_scored): 0.20–0.30 = healthy
- If either drifts >0.40, investigate if niche profiles degraded or model behavior changed

### 1.3 Performance

| Metric | Type | Normal range | Collection |
|---|---|---|---|
| `entity_relevance_latency_seconds` | Histogram | 65–100 s (dense), 15–20 s (sparse) | Per analysis; 50th/95th/99th percentiles |
| `model_call_latency_seconds` | Histogram | 10–15 s/batch | Per batch; aggregate to percentiles |
| `cache_lookup_latency_ms` | Histogram | 1–5 ms/entity | Warm-cache runs |

**Interpretation:**
- Latencies are **off the hot path** (analysis time, not request time) — no user-facing SLA.
- Sustained >120 s suggests batch timeout issues; investigate model API or network.

### 1.4 Cost (if metered)

| Metric | Type | Period | Normal |
|---|---|---|---|
| `gpt_4o_mini_tokens_input` | Counter | Daily | 150k–300k |
| `gpt_4o_mini_tokens_output` | Counter | Daily | 50k–100k |
| `entity_relevance_cost_usd` | Gauge | Daily | $0.10–0.30 (5–10 active workspaces) |

**Interpretation:** Cold analysis (1st per workspace per week) ≈ $0.004; warm (re-analysis within 7 days) ≈ $0. Scaling linearly with workspace count and re-analysis frequency.

---

## 2. Alert thresholds

### Critical (page immediately)

| Condition | Threshold | Action |
|---|---|---|
| Fallback count > 0 in a single analysis | Any non-zero | Check logs: timeout / API error / malformed response. May indicate OpenAI API outage or network issue. Feature degrades to deterministic behavior (safe), but investigate cause. |
| Cache hit rate < 0.50 | Daily aggregate | Suggests cache is not warming or TTL is too short. Check for excessive new/modified entities or cache key collisions. Review `ENTITY_RELEVANCE_CACHE_TTL_SECONDS`. |
| Model call latency (95th percentile) > 30 s | Per batch | Possible OpenAI API slowdown. Check OpenAI status page. If sustained, increase `ENTITY_RELEVANCE_BATCH_SIZE` to decrease call frequency (trades latency for fewer calls). |

### Warning (investigate within 24 h)

| Condition | Threshold | Action |
|---|---|---|
| Filter rate > 0.40 | Per workspace | May indicate: (a) niche profile degradation (confirm in UI), (b) model behavior shift (spot-check a few high-filter cases), or (c) false negatives emerging. Compare to baseline week-1 rate. |
| Down-rank rate < 0.15 | Per workspace | May indicate: (a) fewer junk entities in entity set (benign), or (b) decision logic threshold drift. Spot-check OI summary to confirm. |
| Entity relevance cost > $1.00 USD in a day | Daily | Cold-start surge (workspace first analysis) is normal. Sustained >$1/day suggests excessive workspace counts or re-analysis cadence. Check sweep patterns. |
| Latency (95th percentile) > 120 s | Per analysis | Off the hot path, but investigate if sustained — may indicate network issues or model API queueing. |

### Informational (log, review in weekly checklist)

| Condition | Threshold | Notes |
|---|---|---|
| Cache hit rate 0.85–0.95 | Daily | Normal during ramp-up (new workspaces, fresh cache). Should trend to >0.95 by week 2. |
| Filter + down-rank rate 0.40–0.60 | Per workspace | Healthy, within design spec. |

---

## 3. Weekly review checklist

**Frequency:** Every Monday morning (or equivalent cadence).

**Audience:** Product, infrastructure, ML/ops.

**Data sources:** Approval event metadata (OI summary), OpenAI billing, error logs.

### 3.1 Metrics review

- [ ] **Cache performance:** Hit rate trending up toward 0.95+? If flat or declining, check TTL and entity stability.
- [ ] **Filtering trend:** Any workspace spike >0.45 filter rate? Spot-check one recommendation per spike to rule out model drift.
- [ ] **Cost:** Cold-start cost within $0.004–$0.006 per new workspace? (Anything >$0.010 warrants model/prompt review.)
- [ ] **Latency:** 95th percentile < 120 s? Anything spiky (>150 s)? Check OpenAI incident logs.
- [ ] **Fallback:** Any non-zero fallback counts in the period? If yes, pull error logs immediately.

### 3.2 Quality spot checks

- [ ] **Allow-list integrity:** Spot-check 3 random workspaces. Do the known-good entities (NOMATIC, Thoughtworks, GDPR, capsule wardrobe, BPC-157, etc.) appear in recommendations? Any unexpected filters?
- [ ] **Off-topic removals:** Confirm Bloomberg/Michelin/Hyundai/Photostream absent from Plausible/Pragmatic/Tortuga top-25. (These are the test residuals.)
- [ ] **New workspace first-run:** If a new workspace was analyzed in this period, spot-check its top-25 for obvious junk. Are the residuals gone?

### 3.3 Configuration audit

- [ ] **Flag state:** `ENTITY_RELEVANCE_SCORING_ENABLED=true` in all production environments? (Expected: yes from day 1.)
- [ ] **Model:** `ENTITY_RELEVANCE_MODEL` empty or `gpt-4o-mini`? (No unexpected model overrides.)
- [ ] **Thresholds unchanged:**
  - `ENTITY_RELEVANCE_FILTER_THRESHOLD: 0.25`
  - `ENTITY_RELEVANCE_DOWNRANK_THRESHOLD: 0.60`
  - `ENTITY_RELEVANCE_TOPIC_THRESHOLD: 0.35`
  - `ENTITY_RELEVANCE_DOWNRANK_PENALTY: 0.35`
- [ ] **Timeout and batch size:** 60 s timeout, 25 entities/batch? (These tuned values; do not change without investigation.)

### 3.4 Operator notes

- [ ] Any unexpected errors in logs? Filter for `entity_relevance` or `EntityRelevanceService` in error traceback.
- [ ] Did any workspace hit the 150-entity cap? (Log will show `entities_requested > 150`, triggering deterministic fallback for overflow. This is safe but indicates possible workspaces with many candidates — OK to note.)
- [ ] Any customer-reported junk in recommendations since rollout? Cross-reference with Phase 2A filter/down-rank metrics for that workspace. If a junk item survived, was it in the scored set?

---

## 4. Rollback checklist

**Condition for rollback:** Critical alert fires and cannot be resolved within 4 hours, OR a regression is identified (e.g., false-positive filter of a known-good entity).

**Time to execute:** ~2 minutes (no migrations, no data undo).

### 4.1 Immediate action

```bash
# Option 1: via environment (if you can restart worker)
ENTITY_RELEVANCE_SCORING_ENABLED=false
# Restart the worker/autopilot service.

# Option 2: via .env file
# Edit .env, set ENTITY_RELEVANCE_SCORING_ENABLED=false
# Restart worker.
```

### 4.2 Verification

- [ ] Check the next analysis run: OI summary should have **no** `entity_relevance` block.
- [ ] Spot-check a dense workspace (e.g., Plausible): top-25 should match the OFF baseline (Bloomberg #14, Michelin #17, Hyundai #19 present).
- [ ] **Cost:** Next day's OpenAI bill should drop by ~$0.15–0.30 (assuming 5–10 active workspaces, 1 analysis per workspace per week).

### 4.3 Post-rollback investigation

- [ ] Pull logs: grep for `entity_relevance` errors or anomalies during the flagged period.
- [ ] Check OpenAI API status (check OpenAI status page for outages).
- [ ] Review the specific workspace(s) that triggered the alert: are their entity sets unusual (many new entities, rare verticals)?
- [ ] Post to the team Slack channel: summarize the alert, action taken, and ETA for root-cause fix.

### 4.4 Re-enable

Once root cause is fixed (e.g., OpenAI API latency issue resolved, decision threshold adjusted):

```bash
ENTITY_RELEVANCE_SCORING_ENABLED=true
# Restart worker.
```

Trigger a re-analysis of the workspace that flagged the issue to confirm it passes.

---

## 5. Success criteria by time horizon

### 5.1 After 1 day

- [ ] **Scoring active:** `entity_relevance` block present in OI summary for all analyses.
- [ ] **No fallbacks:** `fallback_count = 0` for all runs.
- [ ] **Model calls normal:** ~5–10 total calls across all workspaces (varies by scope and re-analysis, but should be finite and reasonable).
- [ ] **Known residuals gone:** Spot-check Plausible: Bloomberg/Michelin/Hyundai absent.
- [ ] **Known-good preserved:** Spot-check Tortuga: NOMATIC and capsule wardrobe present.
- [ ] **No critical alerts:** Fallback count = 0, cache hit rate > 0.5 (acceptable on day 1, lower is OK).

**Pass/Fail:** Go / No-go for continuing rollout.

### 5.2 After 1 week

- [ ] **Cache warm:** Hit rate trending to 0.90+ (steady-state 0.95+).
- [ ] **Filter rate stable:** 0.25–0.35 per workspace (no workspace >0.45).
- [ ] **Cost tracking:** ~$0.004–$0.006 per unique workspace analyzed (cold); near-zero on re-analysis.
- [ ] **Latency acceptable:** 95th percentile < 110 s (off hot path; no user-facing impact).
- [ ] **No unexpected allow-list losses:** Spot-check 5 workspaces; all known-good entities intact.
- [ ] **Customer feedback:** No new complaints about junk in recommendations since day 1 rollout.

**Pass/Fail:** Proceed to broad rollout vs. investigate and iterate.

### 5.3 After 1 month

- [ ] **Sustained quality:** All metrics from week 1 remain stable; no metric threshold breached.
- [ ] **Cache efficiency plateau:** Hit rate consistently 0.95–0.99 (only new/modified entities trigger model calls).
- [ ] **Cost predictable:** Monthly cost = `$0.004 × active_workspaces × (1 + re_analysis_frequency)`. For 20 workspaces analyzed once per week, expect ~$0.16/week = ~$0.64/month.
- [ ] **No residual false positives:** A/B compare 2–3 workspaces (run OFF for 1 analysis, ON for 1 analysis); results match validation report (residuals gone, allow-list intact).
- [ ] **Latency under control:** 95th percentile < 110 s, no trend toward timeouts.
- [ ] **Operator confidence:** Monitoring dashboard reflects stable state; no critical alerts in the month.

**Pass/Fail:** Feature is production-healthy. Consider enabling by default for new workspaces (currently opt-in via env var).

---

## 6. Monitoring setup

### 6.1 Metrics export

The OI summary (emitted in approval events and `/refresh-opportunity-intelligence` responses) includes the `entity_relevance` block:

```json
{
  "entity_relevance": {
    "enabled": true,
    "entities_requested": 150,
    "entities_scored": 150,
    "model_calls": 6,
    "cache_hits": 0,
    "cache_misses": 150,
    "filtered_by_relevance": 44,
    "down_ranked_by_relevance": 38,
    "fallback_count": 0,
    "cost_usd": 0.005
  }
}
```

**Export destinations:**
- **Logs:** Parse approval event JSON; forward `entity_relevance` block to observability platform (e.g., DataDog, New Relic).
- **Metrics:** Emit Prometheus-style metrics: `entity_relevance_model_calls`, `entity_relevance_cache_hits`, etc.
- **Cost tracking:** Log `cost_usd` per analysis; aggregate daily/weekly/monthly for budget tracking.

### 6.2 Dashboard example

**Tool:** Grafana, CloudWatch, or equivalent.

**Panels:**
1. **Cache hit rate (daily %):** Line chart, target line at 0.95.
2. **Filter rate by workspace (weekly avg):** Bar chart, threshold line at 0.40.
3. **Fallback count (daily total):** Single-value gauge, target 0, red alert >0.
4. **Model calls (daily total):** Area chart, scale with workspace count.
5. **Cost (daily USD):** Single-value gauge, scale with workspace count.
6. **Latency (95th percentile):** Line chart, target <110 s.
7. **Entity type distribution (pie, weekly):** Sanity check for model drift.

---

## 7. Conclusion

> ## A) Ready for production rollout

All monitoring infrastructure is in place. The metrics are stable from validation, alert thresholds are conservative (fail-safe), and the rollback path is instant. Enable `ENTITY_RELEVANCE_SCORING_ENABLED=true` in production and monitor the weekly checklist above. No additional staging observation required.

**First action:** Set `ENTITY_RELEVANCE_SCORING_ENABLED=true`, restart the worker, and trigger `/refresh-opportunity-intelligence` on Plausible Analytics. Verify the `entity_relevance` block appears in the OI summary and Bloomberg/Michelin/Hyundai are absent from top-25. If all pass, proceed to full rollout.
