# Opportunity Quality Validation Plan

## Purpose

Trendplot now runs a multi-layer intelligence stack:

| Layer | Question it answers |
| --- | --- |
| Website Intelligence | What does this site contain and claim? |
| Competitor Intelligence | What does the ecosystem publish? |
| Demand Observations | What owned traffic and queries exist? |
| Publishing Memory | What is covered, stale, or at risk? |
| Market Intelligence | What is happening in the niche? |
| Opportunity Intelligence | What should we create, refresh, expand, merge, or monitor? |

Before adding providers, models, or architecture, we must answer one question:

```text
Did recommendation quality improve after Market Intelligence?
```

This document defines **how to measure that**. It does not prescribe new code, providers, or system redesign.

---

## Scope

**In scope**

- Repeatable evaluation across diverse workspaces and verticals
- Human scoring of final recommendations and intermediate artifacts
- Baseline vs post–Market Intelligence comparison using stored snapshots
- Failure taxonomy, distribution metrics, funnel metrics, explainability checks

**Out of scope**

- Building new providers or intelligence pipelines
- Automating LLM-as-judge scoring (optional later; not required for v1)
- Calendar/planning quality (separate validation track)

---

## Core Hypothesis

Market Intelligence should shift the recommendation set from **website-led labels** toward **market-led editorial opportunities** without requiring Search Console.

A successful validation shows:

1. Fewer navigation/category junk recommendations in the top 25
2. More educational, comparison, glossary, trend, and ecosystem topics
3. Stronger explainability (evidence, audience, why now, site fit)
4. A healthy funnel: many candidates discovered, fewer but higher-quality recommendations selected

---

## Validation Dataset

### Principles

- **No vertical hardcoding** — do not bake peptide-, fashion-, or SaaS-specific rules into the framework
- **Diversity over volume** — prefer 7–12 workspaces across business models rather than many sites in one niche
- **Comparable runs** — same analyze → market discover → OI refresh sequence for every workspace
- **Documented context** — each workspace records URL, stated niche, GSC on/off, external provider flags

### Suggested workspace mix

Use real or staging workspaces. Tag each with `vertical_tag` (free text, reviewer-assigned), not system-enforced enums.

| Bucket | Examples (illustrative only) | Why include |
| --- | --- | --- |
| Research / regulated | peptides, supplements, biotech-adjacent | Scientific gating, glossary/educational demand |
| Lifestyle / retail | fashion, e-commerce, DTC | Nav-label risk, comparison and buying guides |
| B2B / knowledge | software, consulting, agencies | Authority clusters, ecosystem topics |
| Local / services | clinics, trades, regional services | Thin content, local intent, weak GSC |
| Zero-traffic / new | fresh domains, GSC disconnected | Tests market-led CREATE without owned demand |
| Mature / GSC-connected | sites with impressions data | Tests refresh prioritization vs create mix |

Minimum for a credible v1 report: **7 workspaces**, at least **4 distinct vertical_tags**, at least **2 without Search Console**.

### Workspace registry (template)

For each evaluation workspace, record:

| Field | Description |
| --- | --- |
| `workspace_id` | Trendplot workspace UUID |
| `website_url` | Canonical URL analyzed |
| `vertical_tag` | Reviewer label (e.g. `e-commerce`, `health-research`) |
| `gsc_configured` | yes / no |
| `external_market_providers` | Which `MARKET_PROVIDER_*` flags were on |
| `run_date` | ISO date of evaluation run |
| `evaluator` | Initials or role |
| `notes` | Competitors listed, crawl limits, anomalies |

Store registry in `docs/validation/runs/<run_id>/workspace_registry.json` (manual curation; not product code).

---

## Baseline Capture

### What to snapshot

For each workspace, after a full pipeline run (`analyze` or equivalent: site understanding → trends → publishing memory → market discover → opportunity refresh), capture immutable JSON snapshots:

| Artifact | Source (current system) | Snapshot file |
| --- | --- | --- |
| Niche profile | `workspace_niche_profiles` | `niche_profile.json` |
| Market intelligence run | `market_intelligence_runs` (latest) | `market_run.json` |
| Market signals | `GET /developer/market/workspaces/{id}/signals` | `market_signals.json` |
| Topic clusters | `market_topic_clusters` or insights payload | `market_clusters.json` |
| Market opportunity candidates | `GET /developer/market/workspaces/{id}/candidates` | `market_candidates.json` |
| Final recommendations | `opportunity_recommendations` for workspace | `recommendations.json` |
| Optional: demand top rows | demand insights / observations | `demand_observations.json` |
| Optional: coverage | publishing memory coverage | `coverage.json` |

### Baseline vs treatment

| Phase | Description | When |
| --- | --- | --- |
| **Baseline** | Recommendations produced with Market Intelligence **disabled** (`MARKET_INTELLIGENCE_ENABLED=false`) or from a tagged pre-MI export if historical snapshots exist | Before claiming improvement |
| **Treatment** | Full stack with `MARKET_INTELLIGENCE_ENABLED=true`, default provider flags documented | Current production-like config |

If no true baseline snapshot exists, label the study **single-cohort quality audit** (absolute rubric only) and plan a follow-up A/B once baseline exports are available.

### Snapshot metadata

Each run folder: `docs/validation/runs/<run_id>/<workspace_id>/`

Include `manifest.json`:

```json
{
  "workspace_id": "...",
  "run_id": "2026-06-01-v1",
  "phase": "treatment",
  "market_intelligence_enabled": true,
  "captured_at": "2026-06-01T12:00:00Z",
  "api_paths": ["/developer/market/...", "/autopilot/.../market-insights"],
  "counts": {
    "market_signals": 0,
    "market_candidates": 0,
    "recommendations": 0
  }
}
```

---

## Evaluation Methodology

### Workflow (per workspace)

```mermaid
flowchart LR
    Setup[Register workspace] --> Run[Execute pipeline]
    Run --> Snap[Export snapshots]
    Snap --> Sample[Select top 25 recommendations]
    Sample --> Score[Human rubric scoring]
    Score --> Tag[Tag failures and source class]
    Tag --> Aggregate[Roll up metrics]
```

1. **Register** workspace in the validation registry
2. **Run** analyze + market discover + OI refresh (document env flags)
3. **Export** snapshots to the run folder
4. **Sample** top 25 recommendations by OI score (or priority order shown in UI)
5. **Score** each opportunity with the rubric (below)
6. **Tag** failure categories and source lineage (`market_intelligence` vs `niche_profile` vs `coverage`, etc.)
7. **Aggregate** workspace metrics, then cohort metrics

### Reviewer rules

- Score **what a publisher would ship**, not keyword difficulty or search volume
- Use only snapshot evidence; do not open the live site unless verifying a disputed relevance claim
- Two reviewers on a **20% overlap sample** for calibration (Cohen’s kappa target ≥ 0.6 on total score band)
- Blind to `phase` when possible (baseline vs treatment labels hidden in scoring sheet)

### Time budget

| Step | Target |
| --- | --- |
| Snapshot export | 5 min / workspace (scripted curl or manual API) |
| Top-25 scoring | 45–60 min / workspace |
| Failure tagging | Included in scoring |
| Cohort write-up | 2–4 hours after all workspaces scored |

---

## Opportunity Scoring Rubric

Each scored item is one **final recommendation** from `recommendations.json` (not raw market candidates unless doing a separate backlog audit).

### Dimensions (1–5 each)

| Dimension | Question | 1 (Poor) | 5 (Excellent) |
| --- | --- | --- | --- |
| **Relevance** | Does it fit this business and niche? | Off-niche or generic | Clearly on-niche and on-brand |
| **Audience value** | Would a real audience care? | Nobody would search or share | Clear audience need |
| **Editorial value** | Would a publisher actually write this? | Thin, awkward, or pointless | Strong angle and format |
| **Authority value** | Does it build topical authority? | One-off fluff | Cluster-worthy, linkable depth |
| **Novelty** | More than nav label or obvious page? | Duplicates site nav / boilerplate | Distinct market or editorial insight |
| **Actionability** | Could an article be generated immediately? | Missing topic, evidence, or scope | Clear title, topic, and evidence to draft |

**Total score:** sum of six dimensions (range 6–30).

**Publishable threshold (default):** total ≥ **22** and no dimension ≤ **2**.

Adjust thresholds after first calibration pass; document changes in the run report.

### Scoring sheet columns (spreadsheet)

| Column | Values |
| --- | --- |
| `rank` | 1–25 |
| `title` | From recommendation |
| `topic` | From recommendation |
| `action` | create / refresh / expand / merge / monitor |
| `source_type` | e.g. `market_intelligence`, `niche_profile`, `coverage` |
| `relevance` … `actionability` | 1–5 |
| `total` | Formula |
| `publishable` | Y/N |
| `failure_tags` | Comma-separated (see below) |
| `topic_class` | educational / glossary / comparison / trend / ecosystem / refresh / expand / other |
| `reviewer_notes` | Free text |

---

## Failure Categories

Explicitly tag any recommendation that exhibits these patterns. A single item may have multiple tags.

| Code | Description | Examples |
| --- | --- | --- |
| `NAV_LABEL` | Site navigation or chrome | Shop, Contact, Why Us, Home |
| `CATEGORY_LABEL` | Internal taxonomy only | Products, Services, Blog |
| `PRODUCT_ATTR` | SKU/variant language without audience frame | Product Variations, Size Chart (as CREATE) |
| `DUPLICATE` | Same intent/topic as another top-25 item | Two “BPC-157 guide” variants |
| `WEAK_EVIDENCE` | CREATE with no market/demand/competitor support in snapshot | Empty `evidence`, no `source_signal_ids` |
| `GENERIC_FILLER` | Could apply to any site in any industry | “Improve your SEO”, “Content marketing tips” |
| `OFF_NICHE` | Wrong industry or audience | Peptide site gets fashion trend |
| `OVER_BROAD` | Topic too wide to publish one article | “Health”, “Business growth” |

### Automatic pre-checks (manual spreadsheet formulas or script optional)

Flag for human review if **any** of:

- `topic` or `title` matches blocklist tokens (case-insensitive): `shop`, `contact`, `why us`, `product variations`, `privacy`, `terms`, `cart`, `login`
- `source_type` not in (`market_intelligence`, `trend_signal`, `competitor`, `demand_observation`) and `action` = `create`
- `action` = `create` and `has_external_evidence` = false and no market candidate linkage in metadata

These checks support reviewers; they do not replace human judgment.

---

## Opportunity Distribution

Measure composition of **top 25 recommendations** and optionally **full recommendation set**.

### Topic class taxonomy

Assign each item one primary `topic_class`:

| Class | Signals |
| --- | --- |
| `educational` | Guides, explainers, how-to, beginner content |
| `glossary` | Definitions, “what is X” |
| `comparison` | vs, alternatives, buying comparison |
| `trend` | Timely, news, rising interest, “what changed” |
| `ecosystem` | Entities, maps, competitor/market landscape |
| `refresh` | OI action refresh |
| `expand` | OI action expand |
| `merge` | OI action merge |
| `monitor` | OI action monitor |
| `other` | Does not fit |

### Cohort metrics

| Metric | Formula |
| --- | --- |
| Market-led CREATE share | % create where `source_type` = `market_intelligence` |
| Website-led CREATE share | % create where `source_type` in (`niche_profile`, `existing_opportunity`, `coverage`) without market linkage |
| Nav-junk rate | % top-25 with `NAV_LABEL` or `CATEGORY_LABEL` tag |
| Publishable rate | % top-25 with `publishable` = Y |
| Mean total rubric score | Average of six dimensions |
| Class diversity index | Count of distinct `topic_class` with ≥2 items (target ≥ 4 in top 25) |
| Refresh/expansion share | % refresh + expand + merge in top 25 |

### Diversity target (guidance)

In top 25, aim for **no single class > 40%** except `refresh` on mature GSC sites (document exception).

---

## Candidate Volume (Funnel)

Measure whether the system discovers more than it recommends.

| Stage | Metric | Source |
| --- | --- | --- |
| Raw market signals | `count(market_signals)` | Snapshot |
| Clustered topics | `count(market_topic_clusters)` | Snapshot |
| Market candidates | `count(market_opportunity_candidates)` | Snapshot |
| OI candidate pool | `summary.candidate_count` from OI build if logged | Run metadata |
| Final recommendations | `count(recommendations)` | Snapshot |
| Top-25 subset | 25 | Scoring sample |

### Funnel ratios

| Ratio | Healthy direction | Notes |
| --- | --- | --- |
| `candidates / recommendations` | > 2.0 | OI should filter aggressively |
| `signals / candidates` | > 1.5 | Clustering should compress noise |
| `publishable in top 25` | ≥ 60% treatment; ≥ 40% baseline | Calibrate after first run |
| `market_candidates linked to top-25 create` | ≥ 50% of CREATE rows | Proves MI → OI path |

**Goal:** Trendplot consistently discovers **more** opportunities than it ultimately recommends, with higher average quality in the recommended subset than in the raw candidate backlog (spot-check 10 random non-top candidates: expect lower mean rubric score).

---

## Explainability

Every **top-25** recommendation must be auditable against the snapshot. Score explainability separately (Y/N per field):

| Question | Where to look in snapshot |
| --- | --- |
| Why does this matter? | `explanation`, `reasons`, `evidence_summary` |
| Which evidence supports it? | `evidence[]`, `demand_summary`, `metadata.market_candidate_id`, `source_signal_ids` on linked market candidate |
| Which audience is it for? | `metadata`, market candidate `audience`, niche `known_audiences` |
| Why now? | market candidate `metadata.why_now`, trend velocity, news freshness |
| Why this site? | relevance scores, coverage gap, cannibalization risk, related content ids |

### Explainability score

| Field | Pass criterion |
| --- | --- |
| `why_matters` | Non-empty explanation or ≥2 reasons |
| `evidence` | ≥1 evidence item OR linked market candidate with `evidence_summary` |
| `audience` | Audience named OR inferable from niche profile |
| `why_now` | Present for trend/news classes; optional for evergreen glossary |
| `site_fit` | `business_relevance` / `niche_relevance` documented OR coverage relationship clear |

**Explainability pass:** ≥ 4 of 5 fields for CREATE; ≥ 3 of 5 for refresh/expand.

Cohort metric: **% top-25 passing explainability**.

---

## Benchmark Evaluation (Top 25)

For each workspace, score exactly **25 recommendations** (if fewer exist, score all and note `n < 25`).

### Summary table (per workspace)

| Metric | Value |
| --- | --- |
| `n_scored` | 25 or actual |
| `publishable_count` | |
| `publishable_rate` | |
| `mean_total_score` | /30 |
| `market_led_create_count` | |
| `website_led_create_count` | |
| `obvious_junk_count` | NAV + CATEGORY + GENERIC_FILLER |
| `mean_explainability_fields` | /5 |
| `failure_tag_counts` | By code |

### Cohort rollup

| Metric | Baseline median | Treatment median | Delta |
| --- | --- | --- | --- |
| Publishable rate | | | |
| Obvious junk rate | | | |
| Market-led CREATE share | | | |
| Mean total score | | | |
| Nav-junk in top 25 | | | |

---

## Success Thresholds

Treat as **directional** until first calibration run completes. Refine in `docs/validation/runs/<run_id>/thresholds.md`.

### Treatment cohort (Market Intelligence on)

| Metric | Success |
| --- | --- |
| Publishable rate (top 25) | ≥ **60%** |
| Obvious junk rate (top 25) | ≤ **10%** (≤2 items) |
| NAV_LABEL + CATEGORY_LABEL in top 25 | **0** preferred; ≤1 acceptable |
| Market-led CREATE share (of all CREATE in top 25) | ≥ **50%** |
| Mean total rubric score | ≥ **22.0** / 30 |
| Explainability pass rate | ≥ **75%** |
| Topic class diversity (classes with ≥2 items) | ≥ **4** |
| `candidates / recommendations` | ≥ **2.0** |

### Baseline comparison (if available)

| Metric | Success vs baseline |
| --- | --- |
| Publishable rate | ≥ **+15 percentage points** |
| Obvious junk rate | ≥ **50% relative reduction** |
| Market-led CREATE share | ≥ **+20 percentage points** |
| Mean total score | ≥ **+2.0** points |

### Zero-traffic subset (GSC off)

| Metric | Success |
| --- | --- |
| CREATE count in top 25 | ≥ **8** |
| Publishable CREATE without GSC | ≥ **5** |
| Weak-evidence CREATE | ≤ **2** |

---

## Failure Thresholds

Stop scaling Market Intelligence promotion if **any** of the following hold on the treatment cohort:

| Condition | Threshold | Action |
| --- | --- | --- |
| Junk rate | > **25%** top-25 tagged NAV/CATEGORY/GENERIC | Review filters and OI weighting; do not add providers |
| Publishable rate | < **40%** | Pause feature flag rollout |
| Market-led share | < **25%** of CREATE | Verify discover → OI wiring and snapshots |
| Explainability pass | < **50%** | Fix metadata surfacing before UI work |
| Regression vs baseline | Publishable rate **drops** ≥10 pp | Revert flag default; root-cause run |
| Duplicate rate | > **20%** top-25 tagged DUPLICATE | Tighten cluster/dedupe before new features |

---

## Validation Workflow (Checklist)

### Phase 0 — Prepare

- [ ] Create `docs/validation/runs/<run_id>/`
- [ ] Copy workspace registry template
- [ ] Document `.env` flags for baseline and treatment
- [ ] Assign reviewers and overlap sample

### Phase 1 — Baseline (optional)

- [ ] Set `MARKET_INTELLIGENCE_ENABLED=false`
- [ ] Run analyze + OI refresh per workspace
- [ ] Export snapshots to `.../baseline/<workspace_id>/`
- [ ] Score top 25 per workspace

### Phase 2 — Treatment

- [ ] Set `MARKET_INTELLIGENCE_ENABLED=true` (document provider flags)
- [ ] Run analyze (includes market discover) or discover + OI refresh
- [ ] Export snapshots to `.../treatment/<workspace_id>/`
- [ ] Score top 25 per workspace

### Phase 3 — Analyze

- [ ] Compute per-workspace summary tables
- [ ] Compute cohort rollups
- [ ] Compare baseline vs treatment if both exist
- [ ] Write findings: `docs/validation/runs/<run_id>/REPORT.md`

### Phase 4 — Decide

| Outcome | Criteria |
| --- | --- |
| **Ship** | Meets majority of success thresholds; no failure threshold triggered |
| **Iterate** | Mixed results; junk reduced but publishable rate flat — tune OI/scoring only |
| **Hold** | Failure thresholds triggered — no new complexity until fixed |

---

## Recommended Dashboard Metrics

When product UI exists, surface these read-only KPIs per workspace (no new backend required for v1 manual validation):

| Metric | Definition | UI placement |
| --- | --- | --- |
| Publishable index | Rolling mean rubric total / 30 from last validation run | OI header |
| Junk rate | % recommendations flagged NAV/CATEGORY/GENERIC (last run) | OI quality chip |
| Market-led % | % CREATE from `market_intelligence` | Market + OI panels |
| Candidate funnel | signals → clusters → candidates → recommendations | Market insights |
| Topic mix | Stacked bar by `topic_class` in top 25 | OI analytics |
| Explainability | % passing 4/5 fields | Recommendation detail drawer |
| Evidence depth | Avg evidence items + % with `source_signal_ids` | Market candidate row |
| Zero-traffic CREATE | CREATE count when GSC not configured | Workspace health |

### Alert-style thresholds (dashboard)

- Junk rate > 15% → yellow
- Junk rate > 25% → red
- Publishable index < 0.65 → yellow
- `candidates / recommendations` < 1.5 → yellow (under-discovery or over-selection)

---

## Reporting Template

`docs/validation/runs/<run_id>/REPORT.md` should include:

1. **Executive summary** — Did quality improve? Ship / iterate / hold
2. **Cohort table** — All workspaces with key metrics
3. **Best and worst examples** — 3 titles each with rubric notes (no vertical-specific rules)
4. **Failure analysis** — Counts by failure code
5. **Distribution** — Topic class chart (markdown table acceptable)
6. **Funnel** — Median candidates vs recommendations
7. **Explainability** — Pass rates and common gaps
8. **Limitations** — Small N, single reviewer, missing baseline, provider flags
9. **Next run** — Date, workspaces to add, threshold adjustments

---

## Relationship to Market Intelligence success criteria

Cross-reference [MARKET_INTELLIGENCE_ENGINE.md](./MARKET_INTELLIGENCE_ENGINE.md):

| MI success criterion | Validated by |
| --- | --- |
| Zero-traffic sites get strong recommendations | Zero-traffic subset metrics |
| Shift away from site-derived labels | Junk rate, novelty scores, topic class mix |
| CREATE includes market evidence | Explainability + WEAK_EVIDENCE tags |
| GSC not required for CREATE | Zero-traffic CREATE counts |
| System explains niche, coverage, action | Explainability checklist |

---

## What we are not doing in this plan

- No new providers or ingestion pipelines
- No automated production scoring gate (human rubric first)
- No architecture changes
- No modification of the attached design plan file

This plan exists to **measure** whether the implemented Market Intelligence Engine improved opportunities before further investment.
