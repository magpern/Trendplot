# Trendplot — Claude Code Project Onboarding

> Onboarding orientation for anyone (human or agent) about to make changes to Trendplot.
> Read this before touching code. It captures product direction, the live architecture as
> implemented in the repo, the current quality frontier, and the guardrails to respect.
>
> Authored from a read-only inspection on **2026-06-01**. No code was changed to produce it.

---

## 1. Current product direction

Trendplot is evolving from an **SEO article generator** into an **AI-assisted autonomous
publishing intelligence platform**.

The intended end-to-end loop:

```
enter website → understand niche → discover market opportunities
   → generate content → publish → reassess → (loop)
```

The backend already implements every stage of this loop. The current limitation is **decision
quality**, not workflow coverage — the system can produce recommendations and content, but does
not yet reliably know *which* opportunities are worth publishing first (see
[TRENDPLOT_GAP_ANALYSIS.md](./TRENDPLOT_GAP_ANALYSIS.md)). The strategic priority is therefore
hardening the **decision substrate** (evidence → editorial quality → ranking), not adding
breadth.

Reference docs that frame the direction:
- [TRENDPLOT_V2_SIMPLIFIED_WORKFLOW.md](./TRENDPLOT_V2_SIMPLIFIED_WORKFLOW.md) — target 5-action user workflow.
- [TRENDPLOT_GAP_ANALYSIS.md](./TRENDPLOT_GAP_ANALYSIS.md) — the three biggest gaps (discovery, real demand, strategy planning).
- [MARKET_INTELLIGENCE_ENGINE.md](./MARKET_INTELLIGENCE_ENGINE.md) — niche-evidence layer.
- [EDITORIAL_OPPORTUNITY_GENERATOR_PLAN.md](./EDITORIAL_OPPORTUNITY_GENERATOR_PLAN.md) — editorial-quality layer.
- [OPPORTUNITY_QUALITY_VALIDATION_PLAN.md](./OPPORTUNITY_QUALITY_VALIDATION_PLAN.md) — how quality is measured.

---

## 2. Current major subsystems

Each maps to a package under `app/`. Data flows roughly top-to-bottom.

| Subsystem | Package(s) | Role |
| --- | --- | --- |
| **Website Intelligence** | `app/website_analysis.py`, `app/intelligence/` | Crawl site + competitors, OpenAI `website_analysis`, extract pages/entities/questions, build site-understanding snapshot. |
| **Niche Intelligence** | `app/niche_intelligence/` | Persistent niche profile (primary/secondary niches, entities, audiences, confidence). |
| **Competitor Intelligence** | competitor snapshots via website analysis; `competitor-ecosystem` market provider | Competitor topics/products/gap notes; one signal source into Market Intelligence. |
| **Demand Observations** | `app/demand/`, `app/demand/providers/` | Normalized owned/measurable demand (Search Console–style metrics). Gated by `DEMAND_INTELLIGENCE_ENABLED`. |
| **Publishing Memory & Coverage** | `app/publishing_memory/` | `content_entities`, `content_clusters`, `content_coverage`. Drives REFRESH / EXPAND / MERGE; detects coverage gaps and cannibalization. |
| **Market Intelligence Engine** | `app/market_intelligence/` | "What's happening in the niche?" Providers → `market_signals` → clusters → `market_opportunity_candidates` (seed backlog). Primary CREATE source; does **not** require Search Console. |
| **Editorial Opportunity Generator (EOG)** | `app/editorial_opportunity/` | "What should we publish?" Converts market seeds into 5–12 publishable **editorial concepts** per seed, then picks finalists. **Phase 1 (deterministic) is implemented and wired in.** |
| **Opportunity Intelligence (OI)** | `app/opportunity_intelligence/` | "What should we do next?" Discovers candidates from all sources, scores them, and assigns actions (create / refresh / expand / merge / monitor / ignore). |
| **Content Calendar / Planning** | `app/planning/` | `ContentCalendarEngine` turns recommendations into a scheduled plan. Currently deterministic selection + scheduling (not yet a strategy engine — Gap 3). |
| **Article Generation** | `app/services/jobs.py` + `app/prompts/templates/` | Full pipeline: generation → repair → expansion → humanization → narrative edit → YouTube enrichment → image workflow → quality + sanity gates → rendered HTML + social drafts. |
| **Humanization / Narrative Editor** | `app/review/`, editorial rewriter / narrative editor services | AI pattern cleanup + final editorial pass on generated articles. |
| **WordPress publishing / Connector** | `app/wordpress.py`, `app/connectors/wordpress.py`, `app/publishers/` | REST publisher and Trendplot Connector (plugin) path with fallback; guarded by quality/sanity gates and `ALLOW_LIVE_PUBLISH`. |
| **Social draft generation** | `app/social.py` + article JSON | Social drafts (`x_post`, `threads_post`, `social_posts`) currently emitted as part of the article-generation JSON. A standalone `SocialContentService` exists but has no wired route. |
| **Reassessment / Performance** | `app/reassessment/`, `app/performance/` | Post-publication strategy report and performance feedback (most external providers are still placeholders). |

### Pipeline orchestration

`AutopilotService` ([app/autopilot/service.py](../app/autopilot/service.py)) is the conductor.
Workspace **analyze** runs site understanding → niche → trends → publishing memory → **market
intelligence → EOG** → opportunity intelligence. The market-intelligence refresh now chains the
editorial generator before OI:

```
_refresh_market_intelligence()
  → MarketIntelligenceService.discover_for_workspace()   # signals → clusters → seed candidates
  → _run_editorial_generator()                           # seeds → editorial concepts + finalists
  → _market_inputs_for_oi()                              # prefers editorial finalists over raw seeds
  → refresh_opportunity_intelligence(editorial_opportunity_concepts=…)
```

Key wiring references:
- EOG chained after market discover: [app/autopilot/service.py:689](../app/autopilot/service.py#L689), [app/autopilot/service.py:711-743](../app/autopilot/service.py#L711-L743)
- OI prefers editorial finalists, falls back to raw market candidates: [app/autopilot/service.py:574-590](../app/autopilot/service.py#L574-L590), [app/autopilot/service.py:734-743](../app/autopilot/service.py#L734-L743)
- OI ingests editorial concepts via bridge: [app/opportunity_intelligence/discovery.py:20-29](../app/opportunity_intelligence/discovery.py#L20-L29)

---

## 3. Current UI state

| Surface | Route | Source | Status |
| --- | --- | --- | --- |
| **Trendplot operator UI** | `/`, `/app` | [app/trendplot_ui.py](../app/trendplot_ui.py) | **Active.** This is where operator features belong. |
| Developer / Admin workbench | `/developer`, `/admin` | [app/ui.py](../app/ui.py) | **Legacy / obsolete.** Do **not** add new features here unless explicitly requested. |
| API docs | `/docs` | FastAPI | Dev/debug. |
| Health | `/health` | [app/main.py](../app/main.py) | Internal. |

Direction: the **root UI (`/`, `/app`) should eventually absorb the operator diagnostics** that
are currently only in `/developer`. New operator-facing surfaces go to the root UI, not the legacy
developer/admin workbench.

The EOG endpoints currently live under the developer namespace
(`/developer/editorial/workspaces/{id}/generate`, `/developer/editorial/workspaces/{id}/concepts`
— [app/api/routes.py:611-637](../app/api/routes.py#L611-L637)). Market endpoints are similarly under
`/developer/market/...`. Treat these as backend/diagnostic plumbing; operator-facing exposure
should land in the root UI.

---

## 4. Current architectural priorities

1. **Do not add more intelligence layers blindly.** The platform already has many layers; the
   bottleneck is quality, not coverage.
2. **Validate recommendation quality before adding new providers or models.** Use the validation
   workflow (Section 6) as the gate.
3. The **Editorial Opportunity Generator Phase 1 (deterministic)** was the named next candidate —
   **and it is now implemented and wired in.** ⚠️ See Section 5: the live frontier has moved to
   *tuning EOG output quality*, not building it.
4. **Phase 2 (LLM editorial refinement, `EDITORIAL_GENERATOR_AI_ENABLED`) must NOT be implemented
   yet** unless explicitly requested. The plan's flag exists in design but the deterministic path
   should be proven first.

---

## 5. Current known problems

Recommendation quality is **still weak**, and the frontier has shifted since the plan docs were
written. Market Intelligence now produces CREATE candidates, and the EOG converts them into
better-phrased titles — but **a new diversity failure mode has appeared**.

### 5a. The EOG is already built (status update vs. the plan docs)

`app/editorial_opportunity/` exists with `generator.py`, `service.py`, `bridge.py`, `dedupe.py`,
`title_guards.py`, `models.py`. It is wired into `AutopilotService`, `OpportunityIntelligence`,
the API, and `main.py`. Config flags exist (`EDITORIAL_GENERATOR_*`, default enabled). Migration
`0011_editorial_opportunity_concepts.py` adds the tables. So
[EDITORIAL_OPPORTUNITY_GENERATOR_PLAN.md](./EDITORIAL_OPPORTUNITY_GENERATOR_PLAN.md) describes
Phase 1 as "design only / do not implement" — **that is now out of date**; Phase 1 is done.

### 5b. The current quality failure: templated angles repeated across topics

Older problem (raw `MarketStrategist` templates) — still present in the seed layer, to **avoid**:
- "BPC-157: Questions Answered"
- "peptides: Questions Answered"
- "Product Variations & Concentrations"
- nav/site-structure labels: Shop, Why Us, Contact

These come from `_title_for` / `_angle_for` in
[app/market_intelligence/strategist.py:196-220](../app/market_intelligence/strategist.py#L196-L220)
(`: questions answered`, `: complete guide`). The plan calls for deprecating these for CREATE
seeds; the EOG is meant to replace that collapse.

**New problem revealed by the latest validation runs** (`docs/validation/runs/2026-06-01T0834*`):
the EOG now produces good *individual* titles, but the OI ranking surfaces the **same content_type
/ angle applied across many different topics** in the top 25. Observed top-5s:

- Run `083408Z`: "Understanding the Scientific Interest Around {BPC-157 / aging research / angiogenesis / autophagy / bactriostatic}"
- Run `083457Z`: "Current Research Areas Involving {…}"
- Run `083533Z`: "What Is {…}? Research Overview"

So the failure shifted from *bad titles* to *monotonous packs*: one template angle cloned over the
entity list. Contributing causes worth knowing:
- Within-seed dedupe and finalist selection enforce per-seed type diversity, but **across-workspace
  dedupe only caps per-topic-key** ([app/editorial_opportunity/dedupe.py:89-109](../app/editorial_opportunity/dedupe.py#L89-L109)) — there is **no global cap per content_type/angle**, so OI can fill the top with one repeated angle.
- Weak seeds still leak through: `is_weak_seed_topic` only filters nav labels, product-attribute
  patterns, and very short single tokens ([app/editorial_opportunity/title_guards.py:18-27](../app/editorial_opportunity/title_guards.py#L18-L27)). Topics like `bactriostatic` (a typo) and `aging research` pass.

**The goal is article assignments, not entity labels** — and not the same assignment template
stamped across an entity list.

### 5c. Decision-layer history (context for the OI gate)

Early validation (`081551Z`) found OI converted 79/79 market rows to `monitor` because CREATE
required `has_external_evidence`, which is false for internal-context-only runs. This was fixed by
`_market_backed_create()` ([app/opportunity_intelligence/decisions.py:46-56](../app/opportunity_intelligence/decisions.py#L46-L56)),
which allows CREATE for `market_intelligence` / `editorial_opportunity` source types when there is
a persisted signal/concept link and `action_hint=create`, without requiring third-party APIs.
**Do not weaken or revert this gate without re-validating.**

---

## 6. Current validation discipline

- **Validate before adding complexity.** The standing rule (from the findings docs): *do not add
  intelligence layers until publishable_rate ≥ 60% on the treatment cohort.*
- **Preserve the `docs/validation/` workflow.** Each run is an immutable folder
  `docs/validation/runs/<run_id>/` with per-workspace snapshots, `REPORT.md`, and sometimes
  `FINDINGS.md`. Don't rewrite past runs; add new ones.
- The runner is [scripts/run_opportunity_quality_validation.py](../scripts/run_opportunity_quality_validation.py)
  (e.g. `python scripts/run_opportunity_quality_validation.py --refresh`).
- The rubric, failure taxonomy, funnel ratios, and success/failure thresholds are defined in
  [OPPORTUNITY_QUALITY_VALIDATION_PLAN.md](./OPPORTUNITY_QUALITY_VALIDATION_PLAN.md).
- **Any new intelligence/EOG/OI change must be followed by an opportunity-quality validation run**
  and a comparison against thresholds.

---

## 7. Implementation conventions

- Identify the relevant files first; keep changes scoped.
- **Do not edit unrelated plan files** unless explicitly asked (the plan docs are reference, not
  scratch space).
- **Preserve migrations and existing APIs.** Migrations are sequential
  (`0001`…`0011`); add new ones, don't mutate. Don't break existing route contracts.
- **Do not weaken quality / sanity / publishing gates** (article quality checks, semantic sanity
  review, `ALLOW_LIVE_PUBLISH`, the `_market_backed_create` CREATE gate).
- **Do not hardcode niche-specific rules** (no peptide-only / fashion-only logic). Keep the
  architecture generic; use optional **profiles/providers** and **config flags** for optional
  behavior. Vertical specialization (e.g. scientific provider) is gated by generic keyword
  detection, not by niche name.
- Optional behavior is config-gated via `Settings` ([app/config.py](../app/config.py)) with
  `.env` aliases; mirror new flags in [.env.example](../.env.example).

---

## 8. Useful files to inspect

| Area | Files |
| --- | --- |
| Operator UI / legacy UI | [app/trendplot_ui.py](../app/trendplot_ui.py), [app/ui.py](../app/ui.py) |
| HTTP routes | [app/api/routes.py](../app/api/routes.py) |
| Orchestration | [app/autopilot/service.py](../app/autopilot/service.py), [app/main.py](../app/main.py) |
| Market Intelligence | [app/market_intelligence/](../app/market_intelligence/) — `service.py`, `strategist.py`, `clustering.py`, `filters.py`, `query_planner.py`, `scoring.py`, `bridge.py`, `providers/` |
| Editorial Opportunity Generator | [app/editorial_opportunity/](../app/editorial_opportunity/) — `service.py`, `generator.py`, `dedupe.py`, `title_guards.py`, `bridge.py`, `models.py` |
| Opportunity Intelligence | [app/opportunity_intelligence/](../app/opportunity_intelligence/) — `service.py`, `discovery.py`, `scoring.py`, `decisions.py`, `demand.py`, `models.py` |
| Demand | [app/demand/](../app/demand/) |
| Publishing Memory | [app/publishing_memory/](../app/publishing_memory/) |
| Article pipeline | [app/services/jobs.py](../app/services/jobs.py), [app/prompts/templates/](../app/prompts/templates/) |
| Review / sanity | [app/review/](../app/review/) |
| Persistence | [app/models.py](../app/models.py), [app/repositories.py](../app/repositories.py), [migrations/versions/](../migrations/versions/) |
| Config | [app/config.py](../app/config.py), [.env.example](../.env.example) |
| Tests | [tests/test_market_intelligence.py](../tests/test_market_intelligence.py), [tests/test_editorial_opportunity.py](../tests/test_editorial_opportunity.py) |
| Docs | the four plan docs in `docs/` plus `docs/validation/runs/` |

---

## 9. Summary

### How I understand the architecture

Trendplot is a layered, config-flagged pipeline orchestrated by `AutopilotService`. Evidence flows
**site understanding → niche profile → trends/competitors/demand → publishing memory → Market
Intelligence (signals → clusters → seed candidates) → Editorial Opportunity Generator (seeds →
publishable concepts → finalists) → Opportunity Intelligence (discover → score → assign action) →
recommendations → calendar → article generation → WordPress publish → reassessment**. Each layer is
generic and optional behavior is gated. The newest layer, the EOG, sits between Market Intelligence
("what matters") and OI ("what to do next") to answer "what should we publish", and it is already
implemented (Phase 1 deterministic), wired, migrated, flag-controlled, and producing finalists that
OI now prefers over raw market candidate titles.

### Where the next likely implementation should happen

**Quality tuning of the existing EOG/OI output**, not new layers:
- **Diversity across the top-N**: add a global content_type/angle cap (or interleave) so the top 25
  isn't one template cloned across an entity list — the failure visible in
  `docs/validation/runs/2026-06-01T0834*`. Natural homes:
  [app/editorial_opportunity/dedupe.py](../app/editorial_opportunity/dedupe.py) (`dedupe_across_workspace`)
  and OI ranking/diversity in [app/opportunity_intelligence/](../app/opportunity_intelligence/).
- **Stronger seed filtering**: extend `is_weak_seed_topic`
  ([title_guards.py](../app/editorial_opportunity/title_guards.py)) and/or the internal-context
  signal generation to drop typos / over-broad single tokens (`bactriostatic`, bare `aging research`)
  before they become concepts.
- **Deprecate the templated `MarketStrategist` titles for CREATE seeds** (per the plan) now that
  EOG owns editorial phrasing — but keep the strategist's seed selection / `action_hint`.
- Re-run validation after each change; only then consider Phase 2 LLM refinement (and only if
  explicitly requested).

### Confusing or risky areas

- **Plan docs lag the code**: the EOG plan says "do not implement"; it's implemented. Trust the
  code + validation runs over the plan's status header.
- **EOG endpoints live under `/developer/...`** even though `/developer` is the legacy UI — these
  are backend plumbing; operator exposure should move to the root UI.
- **The `_market_backed_create` gate** is load-bearing for zero-traffic CREATE. Changing OI scoring
  or evidence handling can silently collapse all CREATE back to `monitor` (the `081551Z` regression).
- **Trend query generation is partially broken**: `task_type="trend_query_generation"` is not in
  `ModelTask`, the exception is swallowed, and heuristics are used (documented in
  [UI_WORKFLOW_MAP.md](./UI_WORKFLOW_MAP.md)). Real trend/demand providers are mostly stubs.
- Validation so far is **single-workspace (example-lab/peptides)** — risk of tuning to one vertical.
  The plan calls for ≥7 workspaces and ≥4 verticals; broaden before drawing conclusions.

### What I would avoid changing

- Migrations `0001`–`0011` (add new ones instead).
- Existing API route contracts (`/autopilot/...`, `/developer/market/...`, `/developer/editorial/...`).
- The quality, sanity, and live-publish gates, and the `_market_backed_create` CREATE gate.
- The `docs/validation/` historical runs and the four plan docs (reference, not edit targets).
- The legacy `/developer` / `/admin` UI (no new features there).
- Anything that would hardcode a specific niche into generic logic.
```
