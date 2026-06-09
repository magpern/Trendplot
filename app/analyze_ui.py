ANALYZE_WEBSITE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Analyze Website | Trendplot</title>
  <style>
    :root {
      --bg: #f4f1ea;
      --ink: #1e2930;
      --muted: #65747b;
      --line: #cfc7b8;
      --panel: #fffdf8;
      --panel-2: #ebe4d6;
      --accent: #0f766e;
      --accent-2: #b45309;
      --ok: #15803d;
      --warn: #b45309;
      --bad: #b91c1c;
      --queued: #64748b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        linear-gradient(120deg, rgba(15,118,110,.12), transparent 38rem),
        repeating-linear-gradient(90deg, rgba(30,41,48,.035) 0 1px, transparent 1px 42px),
        var(--bg);
      color: var(--ink);
    }
    button, input, select, textarea { font: inherit; }
    a { color: var(--accent); }
    .shell { width: min(1280px, 94vw); margin: 0 auto; padding: 28px 0 64px; }
    .masthead { display: grid; grid-template-columns: 1.1fr .9fr; gap: 28px; align-items: end; margin-bottom: 22px; }
    h1 { margin: 0; font-size: clamp(2.4rem, 5vw, 5.4rem); line-height: .92; font-weight: 500; max-width: 760px; }
    .lede { color: var(--muted); font-size: 1.05rem; line-height: 1.55; max-width: 620px; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
    .pill { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); border-radius: 999px; padding: 7px 10px; background: rgba(255,253,248,.7); color: var(--muted); font-size: .9rem; }
    .dot { width: 9px; height: 9px; border-radius: 999px; background: var(--queued); }
    .dot.succeeded { background: var(--ok); }
    .dot.running { background: var(--accent); animation: pulse-dot 1.2s ease-in-out infinite; }
    @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .55; transform: scale(1.15); } }
    .step.running { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--panel)); box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent); }
    .active-run-banner {
      border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--line));
      background: color-mix(in srgb, var(--accent) 10%, var(--panel));
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 10px;
      color: var(--ink);
      font-size: .95rem;
      line-height: 1.4;
    }
    .active-run-banner strong { color: var(--accent); }
    .active-run-banner small { display: block; color: var(--muted); margin-top: 4px; }
    #start-button.analyzing { background: color-mix(in srgb, var(--accent) 72%, var(--muted)); border-color: color-mix(in srgb, var(--accent) 72%, var(--muted)); }
    .dot.warning, .dot.skipped, .dot.disabled { background: var(--warn); }
    .dot.failed { background: var(--bad); }
    .dot.cancelled { background: var(--muted); }
    .layout { display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 18px; align-items: start; }
    .panel { border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 94%, transparent); border-radius: 8px; padding: 16px; box-shadow: 0 18px 50px rgba(30,41,48,.08); }
    .panel h2, .panel h3 { margin: 0 0 12px; font-weight: 600; }
    label { display: grid; gap: 5px; margin: 11px 0; color: var(--muted); }
    input, select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 10px 11px; background: #fffaf0; color: var(--ink); }
    textarea { min-height: 92px; resize: vertical; }
    button { border: 1px solid var(--accent); background: var(--accent); color: white; border-radius: 6px; padding: 10px 12px; cursor: pointer; font-weight: 700; }
    button.secondary { background: var(--panel); color: var(--accent); }
    button:disabled { opacity: .52; cursor: not-allowed; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .steps { display: grid; gap: 8px; }
    .step { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: rgba(255,250,240,.72); align-items: start; }
    .step.queued { opacity: .72; }
    .step strong { display: block; }
    .step small { color: var(--muted); line-height: 1.35; }
    .status { text-transform: uppercase; font-size: .72rem; letter-spacing: .08em; color: var(--muted); }
    .progress-text { margin-top: 5px; color: var(--muted); font-size: .86rem; }
    .timing-note { margin-top: 5px; color: var(--muted); font-size: .82rem; font-style: italic; }
    .step details { margin-top: 7px; color: var(--muted); }
    .step summary { cursor: pointer; }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin-bottom: 12px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,250,240,.7); padding: 11px; }
    .metric span { display: block; color: var(--muted); font-size: .82rem; }
    .metric strong { font-size: 1.5rem; font-weight: 500; }
    .notice { border: 1px solid color-mix(in srgb, var(--accent-2) 46%, var(--line)); background: rgba(180,83,9,.1); color: #78350f; border-radius: 8px; padding: 10px; margin: 8px 0; }
    .list { display: grid; gap: 8px; }
    .item { border: 1px solid var(--line); background: rgba(255,253,248,.75); border-radius: 8px; padding: 11px; }
    .item strong { display: block; line-height: 1.25; }
    .item p { margin: 6px 0 0; color: var(--muted); line-height: 1.4; }
    .item.ideation-rec { border-color: color-mix(in srgb, var(--accent) 35%, var(--line)); background: color-mix(in srgb, var(--accent) 4%, rgba(255,253,248,.85)); }
    .item.ideation-rec .ideation-abstract { color: var(--ink); font-size: .98rem; line-height: 1.5; margin-top: 8px; }
    .item.ideation-rec .meta-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .item.ideation-rec .meta-pills span { border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; font-size: .78rem; color: var(--muted); background: rgba(255,250,240,.8); }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
    .actions-primary { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .progress-header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 4px; }
    .step-status-col { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 5.5rem; }
    .step-rerun-btn, .rerun-menu-trigger {
      border: 1px solid var(--line); background: var(--panel); color: var(--accent);
      border-radius: 6px; padding: 2px 8px; font-size: .85rem; font-weight: 600; line-height: 1.4; cursor: pointer;
    }
    .step-rerun-btn:disabled, .rerun-menu-trigger:disabled { opacity: .45; cursor: not-allowed; }
    .rerun-menu { position: relative; display: inline-block; }
    .rerun-menu-panel {
      position: absolute; right: 0; top: calc(100% + 4px); z-index: 20; min-width: 15rem;
      border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
      box-shadow: 0 10px 28px rgba(30,41,48,.14); padding: 4px; display: none;
    }
    .rerun-menu.open .rerun-menu-panel { display: block; }
    .rerun-menu-item {
      display: block; width: 100%; text-align: left; border: none; background: transparent;
      color: var(--ink); border-radius: 4px; padding: 8px 10px; font-weight: 500; cursor: pointer;
    }
    .rerun-menu-item:hover:not(:disabled) { background: rgba(15,118,110,.08); }
    .rerun-menu-item:disabled { opacity: .5; cursor: not-allowed; color: var(--muted); }
    .rerun-menu-divider { height: 1px; background: var(--line); margin: 4px 0; }
    .rerun-menu-item-danger { color: var(--bad); }
    .rerun-menu-item-danger:hover:not(:disabled) { background: rgba(185,28,28,.08); }
    .recent-run-meta { font-size: .9rem; }
    .recent-older { margin-top: 8px; }
    .recent-older summary { cursor: pointer; color: var(--accent); font-size: .92rem; }
    .preview { width: 100%; min-height: 360px; border: 1px solid var(--line); border-radius: 8px; background: white; }
    pre { white-space: pre-wrap; overflow: auto; max-height: 340px; background: #1e2930; color: #f8fafc; border-radius: 8px; padding: 12px; }
    .draft-console {
      margin-top: 10px;
      max-height: 280px;
      overflow: auto;
      background: #1e2930;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      font-family: ui-monospace, Consolas, monospace;
      font-size: .82rem;
      line-height: 1.45;
    }
    .draft-console .log-line { margin: 2px 0; }
    .draft-console .log-line.error { color: #fca5a5; }
    .draft-console .log-line.warn { color: #fcd34d; }
    .draft-jobs-list { margin-top: 12px; }
    .draft-jobs-list .item { cursor: pointer; }
    .draft-jobs-list .item.selected { border-color: var(--accent); box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent); }
    .tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .tabs button { width: auto; background: var(--panel); color: var(--accent); border-color: var(--line); }
    .tabs button.active { background: var(--accent); color: white; border-color: var(--accent); }
    .rec-queue-filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 12px; }
    .rec-queue-filters button {
      width: auto; background: var(--panel); color: var(--accent); border: 1px solid var(--line);
      border-radius: 999px; padding: 6px 11px; font-size: .88rem; font-weight: 600; cursor: pointer;
    }
    .rec-queue-filters button.active { background: var(--accent); color: white; border-color: var(--accent); }
    .rec-queue-filters button .count { opacity: .85; font-weight: 500; }
    .rec-queue-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .rec-queue-toolbar .rec-queue-filters { margin-bottom: 0; flex: 1 1 auto; }
    .manual-idea-overlay {
      position: fixed; inset: 0; z-index: 40; background: rgba(30,41,48,.42);
      display: grid; place-items: center; padding: 16px;
    }
    .manual-idea-modal {
      width: min(560px, 96vw); max-height: 90vh; overflow: auto;
      border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
      box-shadow: 0 22px 60px rgba(30,41,48,.18); padding: 16px;
    }
    .manual-idea-modal h3 { margin: 0 0 12px; }
    .manual-idea-modal .modal-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .manual-idea-preview { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: rgba(255,250,240,.7); margin-top: 10px; }
    .manual-idea-preview p { margin: 6px 0; color: var(--ink); }
    .manual-field-help { font-size: .88rem; line-height: 1.45; margin: 0 0 8px; }
    .manual-product-field { margin: 11px 0; }
    .manual-selected-chips { display: flex; flex-wrap: wrap; gap: 6px; min-height: 1.6rem; margin-bottom: 8px; }
    .manual-product-chip { gap: 4px; padding-right: 6px; }
    .manual-product-chip button {
      border: none; background: transparent; color: var(--muted); cursor: pointer;
      font-size: 1rem; line-height: 1; padding: 0 2px; font-weight: 700;
    }
    .manual-product-chip button:hover { color: var(--bad); }
    .manual-product-suggestions {
      border: 1px solid var(--line); border-radius: 6px; background: #fffaf0;
      max-height: 11rem; overflow: auto; margin-top: 6px;
    }
    .manual-product-suggestion {
      display: block; width: 100%; text-align: left; border: none; border-bottom: 1px solid var(--line);
      background: transparent; color: var(--ink); padding: 8px 10px; font-weight: 500; cursor: pointer;
    }
    .manual-product-suggestion:last-child { border-bottom: none; }
    .manual-product-suggestion:hover { background: rgba(15,118,110,.08); }
    .manual-product-suggestion:disabled { opacity: .45; cursor: default; }
    .wp-connector-panel {
      border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-top: 12px;
      background: rgba(255,250,240,.65);
    }
    .wp-connector-panel h3 { margin: 0 0 8px; font-size: 1rem; }
    .wp-connector-status { font-size: .9rem; color: var(--muted); margin: 0 0 8px; }
    .wp-connector-settings { margin-top: 8px; }
    .wp-connector-settings summary { cursor: pointer; color: var(--accent); font-size: .92rem; }
    [hidden] { display: none !important; }
    @media (max-width: 960px) {
      .masthead, .layout, .cards, .form-grid { grid-template-columns: 1fr; }
      .toolbar { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="masthead">
      <div>
        <h1>Analyze Website</h1>
        <p class="lede">Enter the essentials, then let Trendplot discover pages, analyze the business, rank opportunities, and propose a publishing schedule.</p>
      </div>
      <nav class="toolbar">
        <a class="pill" href="/">Workspace UI</a>
        <a class="pill" href="/docs">API docs</a>
        <span id="safety-pill" class="pill"><span class="dot"></span>Manual review default</span>
      </nav>
    </header>

    <section id="recent-runs" class="panel" style="margin-bottom: 18px" hidden>
      <h2>Recent analysis</h2>
      <div id="recent-runs-list" class="list"></div>
      <div id="recent-runs-older" class="recent-older" hidden></div>
    </section>

    <section class="layout">
      <form id="analyze-form" class="panel">
        <h2>Website Essentials</h2>
        <label>Website URL <input id="website_url" name="website_url" type="url" required placeholder="https://example.com"></label>
        <label>Workspace/site name <input id="name" name="name" placeholder="Example Brand"></label>
        <label>Competitor URLs, one per line <textarea id="competitor_urls" name="competitor_urls" placeholder="https://competitor.com"></textarea></label>
        <div class="form-grid">
          <label>Target market / language <input id="target_market" name="target_market" placeholder="US English"></label>
          <label>Max pages <input id="max_pages_per_site" name="max_pages_per_site" type="number" min="1" max="30" value="30"></label>
        </div>
        <label>Publishing mode
          <select id="publishing_mode" name="publishing_mode">
            <option value="manual_review">Manual review only</option>
            <option value="create_wordpress_draft">Send to WordPress as draft (after generation)</option>
            <option value="live_publish" disabled>Live publish</option>
          </select>
        </label>
        <label>Notes / niche hint <textarea id="notes" name="notes" placeholder="Optional audience, market, product, or niche context"></textarea></label>
        <button id="start-button" type="submit">Analyze</button>
      </form>

      <section class="panel">
        <h2>Progress</h2>
        <div class="progress-header">
          <div id="overall" class="pill"><span class="dot"></span>Queued</div>
          <button type="button" id="stop-run-button" class="secondary" hidden>Stop analysis</button>
          <div id="progress-rerun-menu" hidden></div>
        </div>
        <div id="active-run-banner" class="active-run-banner" hidden></div>
        <div id="steps" class="steps" style="margin-top: 12px"></div>
      </section>
    </section>

    <section id="results" class="panel" style="margin-top: 18px" hidden>
      <div class="tabs">
        <button type="button" class="active" data-tab="summary">Summary</button>
        <button type="button" data-tab="recommendations">Recommendations</button>
        <button type="button" data-tab="schedule">Schedule</button>
        <button type="button" data-tab="draft">Draft</button>
        <button type="button" data-tab="diagnostics">Diagnostics</button>
      </div>
      <div id="tab-summary"></div>
      <div id="tab-recommendations" hidden></div>
      <div id="tab-schedule" hidden></div>
      <div id="tab-draft" hidden></div>
      <div id="tab-diagnostics" hidden></div>
    </section>
  </main>

  <script>
    const $ = id => document.getElementById(id);
    const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
    const formatTime = value => value ? new Date(value).toLocaleTimeString() : "";
    let currentRunId = "";
    let pollTimer = null;
    let elapsedTimer = null;
    let currentStatus = null;
    let selectedRecommendation = null;
    let selectedScheduleItem = null;
    let latestDraftJob = null;
    let selectedArticleJobId = "";
    let connectorSettingsCache = { workspaceId: null, settings: null };
    let activeDraftJobId = "";
    let draftPollTimer = null;
    let workspaceDraftJobs = [];
    let autoTabShownForRun = "";
    const DRAFT_ACTIVE_STATUSES = new Set([
      "queued", "running_generation", "running_repair", "running_expansion",
      "running_review", "running_rendering", "running_publish"
    ]);
    const WORDPRESS_PUBLISHED_STATUSES = new Set(["publish", "published", "private"]);
    const WP_STATUS_AUTO_REFRESH_MS = 5 * 60 * 1000;
    const openStepDetails = new Set();

    $("steps").addEventListener("toggle", event => {
      const details = event.target;
      if (!details.matches("details[data-step-key]")) return;
      const key = details.dataset.stepKey;
      if (details.open) openStepDetails.add(key);
      else openStepDetails.delete(key);
    }, true);

    function syncOpenStepDetailsFromDom() {
      document.querySelectorAll("#steps details[data-step-key][open]").forEach(details => {
        if (details.dataset.stepKey) openStepDetails.add(details.dataset.stepKey);
      });
    }

    function rerunContextFromStatus(status) {
      const summary = status.summary || {};
      const prior = status.prior_summary || {};
      const effectiveSummary = (summary.workspace || summary.recommendations || summary.competitor_discovery)
        ? summary
        : (prior.workspace || prior.recommendations || prior.competitor_discovery ? prior : summary);
      const discoveryStep = (status.steps || []).find(step => step.key === "competitor_discovery");
      const discovery = effectiveSummary.competitor_discovery || (discoveryStep && discoveryStep.details) || {};
      const competitors = Array.isArray(discovery.competitors) ? discovery.competitors : [];
      const selected = Number(discovery.selected_count ?? discovery.competitors_selected ?? competitors.length ?? 0);
      const crawlStep = (status.steps || []).find(step => step.key === "website_crawl");
      const hasAnalysis = Boolean((effectiveSummary.site || {}).pages_analyzed || (crawlStep && crawlStep.status === "succeeded"));
      const hasRecs = Number((effectiveSummary.recommendations || {}).total ?? 0) > 0;
      const ideationOnly = Boolean(effectiveSummary.ideation_short_circuit);
      return { selected, hasAnalysis, hasRecs, ideationOnly };
    }

    const RECENT_RUNS_VISIBLE = 3;
    const IDEATION_ONLY_VISIBLE_STEPS = new Set([
      "workspace_setup",
      "sitemap_discovery",
      "website_crawl",
      "website_analysis",
      "niche_intelligence",
      "ai_opportunity_ideation",
      "opportunity_ranking",
      "content_calendar",
      "draft_generation",
      "wordpress_upload",
    ]);

    function ideationShortCircuitActive(status) {
      if (!status) return false;
      if (status.ideation_short_circuit) return true;
      const summary = status.summary || {};
      const prior = status.prior_summary || {};
      if (summary.ideation_short_circuit) return true;
      if (prior.ideation_short_circuit) return true;
      return false;
    }

    function visibleAnalyzeSteps(status) {
      return status.steps || [];
    }

    const STEP_RERUN_TYPES = {
      opportunity_ranking: "recommendations",
      content_calendar: "schedule",
    };

    function rerunActionList(context) {
      const hasAnalysis = Boolean(context.hasAnalysis);
      const hasRecs = Boolean(context.hasRecs);
      return [
        { type: "recommendations", label: "Re-run AI recommendations", enabled: hasAnalysis, reason: "Website analysis incomplete." },
        { type: "schedule", label: "Re-generate schedule", enabled: hasRecs, reason: "No recommendations available." },
        { type: "full", label: "Start full re-analysis", enabled: true, reason: "" },
      ];
    }

    function rerunContextFromRun(run) {
      return {
        selected: Number(run.competitors_selected ?? 0),
        hasAnalysis: Number(run.pages_analyzed ?? 0) > 0,
        hasRecs: Number(run.recommendations_total ?? 0) > 0,
      };
    }

    function closeAllRerunMenus() {
      document.querySelectorAll(".rerun-menu.open").forEach(menu => menu.classList.remove("open"));
    }

    function renderRerunMenuHtml({ workspaceId, parentJobId, context, menuId, triggerLabel = "⋯", triggerTitle = "More actions" }) {
      if (!parentJobId) return "";
      const actions = workspaceId ? rerunActionList(context) : [];
      const items = actions.map(item => {
        const title = item.enabled ? item.label : `${item.label} — ${item.reason}`;
        return `<button type="button" class="rerun-menu-item" data-rerun-type="${escapeHtml(item.type)}" data-rerun-parent="${escapeHtml(parentJobId)}" title="${escapeHtml(title)}"${item.enabled ? "" : " disabled"}>${escapeHtml(item.label)}</button>`;
      }).join("");
      const divider = items ? `<div class="rerun-menu-divider" role="separator"></div>` : "";
      const deleteItem = `<button type="button" class="rerun-menu-item rerun-menu-item-danger" data-delete-run="${escapeHtml(parentJobId)}" title="Remove this analysis from recent history. Workspace data is kept.">Delete analysis</button>`;
      return `<div class="rerun-menu" id="${escapeHtml(menuId)}" data-rerun-parent="${escapeHtml(parentJobId)}">
        <button type="button" class="rerun-menu-trigger secondary" data-rerun-menu-toggle="${escapeHtml(menuId)}" title="${escapeHtml(triggerTitle)}" aria-label="${escapeHtml(triggerTitle)}">${escapeHtml(triggerLabel)}</button>
        <div class="rerun-menu-panel" role="menu">${items}${divider}${deleteItem}</div>
      </div>`;
    }

    function wireRerunMenus(root) {
      const scope = root || document;
      scope.querySelectorAll("[data-rerun-menu-toggle]").forEach(button => {
        if (button.dataset.rerunMenuBound) return;
        button.dataset.rerunMenuBound = "1";
        button.addEventListener("click", event => {
          event.stopPropagation();
          const menu = document.getElementById(button.dataset.rerunMenuToggle);
          if (!menu) return;
          const open = menu.classList.contains("open");
          closeAllRerunMenus();
          if (!open) menu.classList.add("open");
        });
      });
      scope.querySelectorAll(".rerun-menu-item[data-rerun-type]").forEach(button => {
        if (button.dataset.rerunItemBound) return;
        button.dataset.rerunItemBound = "1";
        button.addEventListener("click", () => {
          if (button.disabled) return;
          closeAllRerunMenus();
          triggerRerun(button.dataset.rerunParent || currentRunId, button.dataset.rerunType);
        });
      });
      scope.querySelectorAll("[data-step-rerun]").forEach(button => {
        if (button.dataset.stepRerunBound) return;
        button.dataset.stepRerunBound = "1";
        button.addEventListener("click", () => {
          if (button.disabled) return;
          triggerRerun(currentRunId, button.dataset.stepRerun);
        });
      });
      scope.querySelectorAll("[data-delete-run]").forEach(button => {
        if (button.dataset.deleteRunBound) return;
        button.dataset.deleteRunBound = "1";
        button.addEventListener("click", event => {
          event.stopPropagation();
          deleteAnalysisRun(button.dataset.deleteRun);
        });
      });
    }

    function clearActiveRunView() {
      currentRunId = "";
      currentStatus = null;
      clearRecommendationCache();
      stopPolling();
      setAnalyzeButtonState({ overall_status: "queued" });
      $("results").hidden = true;
      $("progress-rerun-menu").hidden = true;
      $("progress-rerun-menu").innerHTML = "";
      const stopBtn = $("stop-run-button");
      if (stopBtn) stopBtn.hidden = true;
      const banner = $("active-run-banner");
      if (banner) {
        banner.hidden = true;
        banner.innerHTML = "";
      }
      $("overall").innerHTML = `<span class="dot"></span>Queued`;
      $("steps").innerHTML = "";
      const url = new URL(window.location.href);
      url.searchParams.delete("run");
      window.history.replaceState({}, "", url);
    }

    async function deleteAnalysisRun(jobId) {
      if (!jobId) return;
      const label = (currentStatus && (currentStatus.website_url || currentStatus.run_label)) || "this analysis";
      if (!window.confirm(`Delete ${label} from recent history?\\n\\nThe workspace and its SEO data will remain; only this run record is removed.`)) return;
      closeAllRerunMenus();
      try {
        await api(`/app/analyze/runs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
        if (currentRunId === jobId) clearActiveRunView();
        await loadRecentRuns();
      } catch (error) {
        renderError(error.message);
      }
    }

    if (!window.__analyzeRerunMenuCloseBound) {
      window.__analyzeRerunMenuCloseBound = true;
      document.addEventListener("click", () => closeAllRerunMenus());
    }

    function renderProgressRerunMenu(status) {
      const slot = $("progress-rerun-menu");
      if (!slot) return;
      const workspaceId = status.workspace_id || ((status.summary || {}).workspace || {}).id;
      const parentJobId = currentRunId;
      const terminal = ["succeeded", "warning", "failed", "cancelled"].includes(status.overall_status || "");
      if (!workspaceId || !parentJobId || !terminal) {
        slot.hidden = true;
        slot.innerHTML = "";
        return;
      }
      slot.hidden = false;
      slot.innerHTML = renderRerunMenuHtml({
        workspaceId,
        parentJobId,
        context: rerunContextFromStatus(status),
        menuId: `rerun-menu-progress-${parentJobId}`,
        triggerLabel: "↻",
        triggerTitle: "More actions",
      });
      wireRerunMenus(slot);
    }

    function renderStepRerunIcon(step, status) {
      const rerunType = STEP_RERUN_TYPES[step.key];
      if (!rerunType) return "";
      if (!["succeeded", "warning"].includes(step.status || "")) return "";
      const terminal = ["succeeded", "warning", "failed", "cancelled"].includes(status.overall_status || "");
      if (!terminal || !status.workspace_id || !currentRunId) return "";
      const context = rerunContextFromStatus(status);
      const action = rerunActionList(context).find(item => item.type === rerunType);
      if (!action) return "";
      const title = action.enabled ? action.label : `${action.label} — ${action.reason}`;
      return `<button type="button" class="step-rerun-btn" data-step-rerun="${escapeHtml(rerunType)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"${action.enabled ? "" : " disabled"}>↻</button>`;
    }

    async function stopCurrentRun() {
      if (!currentRunId) return;
      if (!window.confirm("Stop this analysis? Work already saved on the workspace will be kept.")) return;
      closeAllRerunMenus();
      const stopBtn = $("stop-run-button");
      if (stopBtn) stopBtn.disabled = true;
      try {
        const status = await api(`/app/analyze/runs/${encodeURIComponent(currentRunId)}/cancel`, { method: "POST" });
        stopPolling();
        setAnalyzeButtonState(status);
        renderStatus(status);
        loadRecentRuns();
      } catch (error) {
        if (stopBtn) stopBtn.disabled = false;
        renderError(error.message);
      }
    }

    if (!window.__analyzeStopBound) {
      window.__analyzeStopBound = true;
      const stopBtn = $("stop-run-button");
      if (stopBtn) stopBtn.addEventListener("click", () => stopCurrentRun());
    }

    loadSafety();
    loadRecentRuns();
    function shouldPollRun(status) {
      if (!status) return false;
      const overall = status.overall_status || "";
      if (["queued", "running"].includes(overall)) return true;
      const steps = visibleAnalyzeSteps(status);
      if (steps.some(step => step.status === "running")) return true;
      // Keep polling when the pipeline still has queued steps (e.g. after website_analysis
      // succeeds but overall_status was briefly "warning" from an earlier step).
      const hasQueued = steps.some(step => step.status === "queued");
      const hasStarted = steps.some(step => ["succeeded", "warning", "failed", "skipped"].includes(step.status || ""));
      if (hasQueued && hasStarted && !["succeeded", "failed", "cancelled"].includes(overall)) return true;
      return false;
    }

    function stopPolling() {
      clearInterval(pollTimer);
      pollTimer = null;
      stopElapsedTimer();
    }

    function stopElapsedTimer() {
      clearInterval(elapsedTimer);
      elapsedTimer = null;
    }

    function startElapsedTimer() {
      stopElapsedTimer();
      elapsedTimer = setInterval(() => {
        if (!currentStatus || !shouldPollRun(currentStatus)) {
          stopElapsedTimer();
          return;
        }
        renderActiveRunBanner(currentStatus);
        updateRunningStepElapsed(currentStatus);
      }, 1000);
    }

    function runningStep(status) {
      return visibleAnalyzeSteps(status).find(step => step.status === "running") || null;
    }

    function elapsedSecondsSince(iso) {
      if (!iso) return null;
      const started = Date.parse(iso);
      if (Number.isNaN(started)) return null;
      return Math.max(0, Math.floor((Date.now() - started) / 1000));
    }

    function formatElapsed(seconds) {
      if (seconds === null || seconds === undefined) return "";
      if (seconds < 60) return `${seconds}s`;
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}m ${secs}s`;
    }

    function renderActiveRunBanner(status) {
      const banner = $("active-run-banner");
      if (!banner) return;
      const overall = status.overall_status || "queued";
      const active = runningStep(status);
      const inProgress = shouldPollRun(status);
      const failedStep = visibleAnalyzeSteps(status).find(step => step.status === "failed");
      const flowError = (status.summary || {}).error || "";
      if (overall === "failed" || overall === "cancelled") {
        const detail = flowError || failedStep?.error || failedStep?.message || overall;
        banner.hidden = false;
        banner.innerHTML = `
          <strong>Analysis ${escapeHtml(overall)}</strong>
          <small>${escapeHtml(detail)}</small>`;
        banner.style.borderColor = "color-mix(in srgb, var(--danger, #b91c1c) 40%, var(--line))";
        banner.style.background = "color-mix(in srgb, var(--danger, #b91c1c) 8%, var(--panel))";
        return;
      }
      banner.style.borderColor = "";
      banner.style.background = "";
      if (!inProgress || !active) {
        banner.hidden = true;
        banner.innerHTML = "";
        return;
      }
      const elapsed = formatElapsed(elapsedSecondsSince(active.started_at));
      const progress = active.progress_label
        || (active.progress_current !== null && active.progress_total !== null
          ? `${active.progress_current} / ${active.progress_total}`
          : "");
      banner.hidden = false;
      banner.innerHTML = `
        <strong>Analysis in progress</strong> — ${escapeHtml(active.label)}
        <small>${escapeHtml(active.message || "Working…")}${elapsed ? ` · ${escapeHtml(elapsed)} elapsed` : ""}${progress ? ` · ${escapeHtml(progress)}` : ""}</small>`;
    }

    function updateRunningStepElapsed(status) {
      const active = runningStep(status);
      if (!active) return;
      const elapsed = formatElapsed(elapsedSecondsSince(active.started_at));
      const stepEl = document.querySelector(`#steps .step.running .step-elapsed`);
      if (stepEl && elapsed) stepEl.textContent = `${elapsed} elapsed`;
    }

    function setAnalyzeButtonState(status, options = {}) {
      const btn = $("start-button");
      if (!btn) return;
      const busy = Boolean(options.starting) || Boolean(currentRunId && status && shouldPollRun(status));
      btn.disabled = busy;
      btn.textContent = busy ? "Analyzing…" : "Analyze";
      btn.classList.toggle("analyzing", busy);
    }

    async function openRunFromUrl(runId) {
      if (runId !== currentRunId) clearRecommendationCache();
      currentRunId = runId;
      try {
        const status = await api(`/app/analyze/runs/${encodeURIComponent(runId)}`);
        renderStatus(status);
        if (shouldPollRun(status)) startPolling();
        else stopPolling();
      } catch (error) {
        stopPolling();
      }
    }

    const runFromQuery = new URLSearchParams(window.location.search).get("run");
    if (runFromQuery) openRunFromUrl(runFromQuery);

    async function api(path, options = {}) {
      const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
      if (response.status === 204) {
        if (!response.ok) throw new Error("Request failed.");
        return {};
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Request failed.");
      return data;
    }

    async function loadSafety() {
      try {
        renderSafety(await api("/app/analyze/safety"));
      } catch (error) {
        $("safety-pill").innerHTML = `<span class="dot warning"></span>Safety state unavailable`;
      }
    }

    $("analyze-form").addEventListener("submit", async event => {
      event.preventDefault();
      const form = new FormData(event.target);
      const payload = {
        website_url: form.get("website_url"),
        name: form.get("name"),
        competitor_urls: String(form.get("competitor_urls") || "").split(/\\n+/).map(v => v.trim()).filter(Boolean),
        target_market: form.get("target_market"),
        publishing_mode: form.get("publishing_mode"),
        max_pages_per_site: Number(form.get("max_pages_per_site") || 30),
        notes: form.get("notes")
      };
      setAnalyzeButtonState({ overall_status: "running" }, { starting: true });
      $("results").hidden = true;
      clearRecommendationCache();
      try {
        const status = await api("/app/analyze/runs", { method: "POST", body: JSON.stringify(payload) });
        currentRunId = status.job_id;
        const url = new URL(window.location.href);
        url.searchParams.set("run", status.job_id);
        window.history.replaceState({}, "", url);
        renderStatus(status);
        startPolling();
        loadRecentRuns();
      } catch (error) {
        setAnalyzeButtonState({ overall_status: "failed" });
        renderError(error.message);
      }
    });

    function startPolling() {
      stopPolling();
      if (!currentRunId) return;
      const tick = async () => {
        if (!currentRunId) {
          stopPolling();
          return;
        }
        try {
          const status = await api(`/app/analyze/runs/${encodeURIComponent(currentRunId)}`);
          renderStatus(status);
          if (!shouldPollRun(status)) {
            stopPolling();
            setAnalyzeButtonState(status);
          } else {
            startElapsedTimer();
          }
        } catch (error) {
          stopPolling();
          setAnalyzeButtonState({ overall_status: "failed" });
          renderError(error.message);
        }
      };
      tick();
      pollTimer = setInterval(tick, 1600);
      startElapsedTimer();
    }

    function updateStopButton(status) {
      const stopBtn = $("stop-run-button");
      if (!stopBtn) return;
      const show = Boolean(currentRunId && shouldPollRun(status));
      stopBtn.hidden = !show;
      if (show) stopBtn.disabled = false;
    }

    function renderStatus(status) {
      currentStatus = status;
      syncOpenStepDetailsFromDom();
      const overall = status.overall_status || "queued";
      const active = runningStep(status);
      const overallLabel = active && shouldPollRun(status)
        ? `running — ${active.label}`
        : overall;
      $("overall").innerHTML = `<span class="dot ${escapeHtml(overall)}"></span>${escapeHtml(overallLabel)}`;
      setAnalyzeButtonState(status);
      renderActiveRunBanner(status);
      updateStopButton(status);
      $("steps").innerHTML = visibleAnalyzeSteps(status).map(step => `
        <article class="step ${escapeHtml(step.status || "queued")}" data-step-key="${escapeHtml(step.key)}">
          <span class="dot ${escapeHtml(step.status)}"></span>
          <div>
            <strong>${escapeHtml(step.label)}</strong>
            <small>${escapeHtml(step.message || "")}</small>
            ${renderProgress(step)}
            ${renderCurrentUrl(step)}
            ${step.status === "running" ? `<div class="progress-text step-elapsed">${escapeHtml(formatElapsed(elapsedSecondsSince(step.started_at)) || "")}${step.started_at ? " elapsed" : ""}</div>` : ""}
            ${renderTimingNote(step)}
            ${step.error ? `<div class="notice">${escapeHtml(step.error)}</div>` : ""}
            ${(step.warnings || []).map(w => `<div class="notice">${escapeHtml(w)}</div>`).join("")}
            ${renderStepDetails(step)}
          </div>
          <div class="step-status-col">
            <span class="status">${renderStepStatus(step)}</span>
            ${renderStepRerunIcon(step, status)}
          </div>
        </article>
      `).join("");
      const runningEl = document.querySelector("#steps .step.running");
      if (runningEl && shouldPollRun(status)) {
        runningEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      renderProgressRerunMenu(status);
      wireRerunMenus($("steps"));
      renderResults(status);
    }

    function renderStepStatus(step) {
      const hasMeasuredDuration = Boolean(step.started_at && step.completed_at) && step.duration_seconds !== null && step.duration_seconds !== undefined;
      const label = step.status === "disabled" ? "disabled" : (step.status || "queued");
      return `${escapeHtml(label)}${hasMeasuredDuration ? ` | ${escapeHtml(step.duration_seconds)}s` : ""}`;
    }

    function renderProgress(step) {
      const hasCount = step.progress_current !== null && step.progress_current !== undefined && step.progress_total !== null && step.progress_total !== undefined;
      const label = step.progress_label || (hasCount ? `Progress: ${step.progress_current} / ${step.progress_total}` : "");
      if (!label && !hasCount) return "";
      return `<div class="progress-text">${escapeHtml(label)}${hasCount ? ` | ${escapeHtml(step.progress_current)} / ${escapeHtml(step.progress_total)}` : ""}</div>`;
    }

    function renderStepDetails(step) {
      const details = step.details && typeof step.details === "object" ? step.details : {};
      const body = step.key === "competitor_discovery"
        ? renderCompetitorDiscoveryDetails(details)
        : renderGenericStepDetails(details);
      if (!body) return "";
      const openAttr = openStepDetails.has(step.key) ? " open" : "";
      return `<details data-step-key="${escapeHtml(step.key)}"${openAttr}><summary>Details</summary><div class="progress-text">${body}</div></details>`;
    }

    function renderGenericStepDetails(details) {
      const entries = Object.entries(details).filter(([key, value]) => (
        value !== null && value !== undefined && value !== ""
        && !["sources_checked", "sources_skipped", "reason_message", "competitors", "web_search_summary", "source_summary", "classification_counts", "other_discovered_domains"].includes(key)
      ));
      if (!entries.length) return "";
      return entries.map(([key, value]) => `<div><strong>${escapeHtml(key)}</strong>: ${escapeHtml(formatDetailValue(value))}</div>`).join("");
    }

    function renderCompetitorDiscoveryDetails(details) {
      if (!details || typeof details !== "object") return "";
      const rows = [];
      const reasonMessage = String(details.reason_message || "").trim();
      if (reasonMessage) rows.push(`<div><strong>Reason</strong>: ${escapeHtml(reasonMessage)}</div>`);
      const sourceLabels = {
        comparison_pages: "Comparison pages",
        outbound_domains: "Outbound domains",
        niche_peers: "Historical niche peers",
        workspace_history: "History",
        competitor_snapshots: "Competitor snapshots",
        web_search: "Web search",
      };
      const checked = (details.sources_checked || []).map(item => sourceLabels[item] || item);
      if (checked.length) rows.push(`<div><strong>Checked</strong>: ${checked.map(item => "✓ " + escapeHtml(item)).join("<br>")}</div>`);
      const skipped = (details.sources_skipped || []).map(item => {
        if (!item || typeof item !== "object") return "";
        const label = sourceLabels[item.source] || item.source || "source";
        if (item.reason === "disabled") return `${label} (disabled${item.detail ? ": " + item.detail : ""})`;
        if (item.reason === "no_results") return `${label} (no results)`;
        return `${label} (${item.reason || "skipped"})`;
      }).filter(Boolean);
      if (skipped.length) rows.push(`<div><strong>Skipped</strong>: ${skipped.map(item => "✗ " + escapeHtml(item)).join("<br>")}</div>`);
      const competitors = Array.isArray(details.competitors) ? details.competitors : [];
      if (competitors.length) {
        rows.push(`<div><strong>Competitors discovered</strong></div>`);
        competitors.forEach(item => {
          const domain = escapeHtml(item.domain || item.url || "");
          const source = escapeHtml(item.source || item.origin || "discovered");
          rows.push(`<div>${domain}<br>Source: ${source}</div>`);
        });
      }
      if (details.history_checked !== undefined) rows.push(`<div><strong>History checked</strong>: ${details.history_checked ? "yes" : "no"}</div>`);
      if (details.snapshots_checked !== undefined) rows.push(`<div><strong>Snapshots checked</strong>: ${details.snapshots_checked ? "yes" : "no"}</div>`);
      if (details.web_search_enabled !== undefined) rows.push(`<div><strong>Web search enabled</strong>: ${details.web_search_enabled ? "yes" : "no"}</div>`);
      if (details.web_search_attempted !== undefined) rows.push(`<div><strong>Web search attempted</strong>: ${details.web_search_attempted ? "yes" : "no"}</div>`);
      if (details.provider_name) rows.push(`<div><strong>Provider</strong>: ${escapeHtml(details.provider_name)}</div>`);
      if (details.queries_run !== undefined) rows.push(`<div><strong>Queries run</strong>: ${escapeHtml(details.queries_run)}</div>`);
      if (details.raw_results_count !== undefined) rows.push(`<div><strong>Raw results</strong>: ${escapeHtml(details.raw_results_count)}</div>`);
      if (details.provider_error) rows.push(`<div><strong>Provider error</strong>: ${escapeHtml(details.provider_error)}</div>`);
      if (details.web_search_summary) rows.push(`<div><strong>Web search</strong>: ${escapeHtml(details.web_search_summary)}</div>`);
      const sourceSummary = Array.isArray(details.source_summary) ? details.source_summary : [];
      if (sourceSummary.length) {
        rows.push(`<div><strong>Sources</strong></div>`);
        sourceSummary.slice(0, 8).forEach(item => {
          const label = escapeHtml(item.label || item.source || "source");
          const note = escapeHtml(item.note || (item.selected ? `${item.selected} selected` : (item.candidates ? `${item.candidates} candidate(s)` : "0")));
          rows.push(`<div>- ${label}: ${note}</div>`);
        });
      }
      const selectedCount = Number(details.selected_count ?? details.competitors_selected ?? 0);
      if (selectedCount) rows.push(`<div><strong>Competitors selected</strong>: ${escapeHtml(selectedCount)}</div>`);
      const otherDomains = Array.isArray(details.other_discovered_domains) ? details.other_discovered_domains : [];
      if (otherDomains.length) {
        rows.push(`<div><strong>Other discovered domains</strong></div>`);
        otherDomains.slice(0, 6).forEach(item => {
          const label = escapeHtml(item.domain || item.url || "");
          const classification = escapeHtml((item.classification || "unknown").replaceAll("_", " "));
          rows.push(`<div>- ${label} (${classification})</div>`);
        });
      }
      const classificationCounts = details.classification_counts && typeof details.classification_counts === "object" ? details.classification_counts : {};
      const countEntries = Object.entries(classificationCounts);
      if (countEntries.length) {
        rows.push(`<div><strong>Classification counts</strong>: ${countEntries.map(([key, count]) => escapeHtml(`${key.replaceAll("_", " ")}: ${count}`)).join(", ")}</div>`);
      }
      if (details.candidates_found !== undefined) rows.push(`<div><strong>Candidates found</strong>: ${escapeHtml(details.candidates_found)}</div>`);
      if (details.candidates_rejected !== undefined) rows.push(`<div><strong>Candidates rejected</strong>: ${escapeHtml(details.candidates_rejected)}</div>`);
      const rejectedByReason = details.rejected_by_reason && typeof details.rejected_by_reason === "object" ? details.rejected_by_reason : {};
      const reasonEntries = Object.entries(rejectedByReason);
      if (reasonEntries.length) {
        rows.push(`<div><strong>Rejected by reason</strong>: ${reasonEntries.map(([code, count]) => escapeHtml(`${code}: ${count}`)).join(", ")}</div>`);
      }
      const rejectedSamples = Array.isArray(details.rejected_samples) ? details.rejected_samples : [];
      if (rejectedSamples.length) {
        rows.push(`<div><strong>Rejected sample</strong></div>`);
        rejectedSamples.slice(0, 5).forEach(item => {
          rows.push(`<div>${escapeHtml(item.url || "")}<br>${escapeHtml(item.reason || "")}</div>`);
        });
      }
      if (details.reason) rows.push(`<div><strong>Reason code</strong>: ${escapeHtml(details.reason)}</div>`);
      const generic = renderGenericStepDetails(details);
      if (generic) rows.push(generic);
      return rows.join("") || renderGenericStepDetails(details);
    }

    function renderCurrentUrl(step) {
      const details = step.details && typeof step.details === "object" ? step.details : {};
      const currentUrl = details.current_url || details.current_path || "";
      if (!currentUrl) return "";
      return `<div class="progress-text">Current URL: ${escapeHtml(currentUrl)}</div>`;
    }

    function renderTimingNote(step) {
      if (!step.timing_note) return "";
      return `<div class="timing-note">${escapeHtml(step.timing_note)}</div>`;
    }

    function formatDetailValue(value) {
      if (Array.isArray(value)) return value.join(", ");
      if (value && typeof value === "object") return JSON.stringify(value);
      return value;
    }

    async function loadRecentRuns() {
      try {
        const data = await api("/app/analyze/runs/recent?limit=20");
        renderRecentRuns(data.runs || []);
      } catch (error) {
        $("recent-runs").hidden = true;
      }
    }

    function renderRecentRunCard(run) {
      const url = escapeHtml(run.website_url || run.run_label || "Analysis");
      const when = escapeHtml(run.completed_at || run.created_at || "");
      const status = escapeHtml(run.overall_status || "unknown");
      const pages = escapeHtml(run.pages_analyzed ?? "n/a");
      const recs = escapeHtml(run.recommendations_total ?? "n/a");
      const menuId = `rerun-menu-recent-${String(run.job_id || "").replace(/[^a-zA-Z0-9_-]/g, "")}`;
      const menu = run.workspace_id
        ? renderRerunMenuHtml({
            workspaceId: run.workspace_id,
            parentJobId: run.job_id,
            context: rerunContextFromRun(run),
            menuId,
            triggerLabel: "⋯",
            triggerTitle: "Re-run actions",
          })
        : "";
      return `<article class="item">
        <strong>${url}</strong>
        <p class="recent-run-meta">${status} · ${when}</p>
        <p class="recent-run-meta">Pages analyzed: ${pages} · Recommendations: ${recs}</p>
        <div class="actions actions-primary">
          <button type="button" data-open-run="${escapeHtml(run.job_id)}">Open result</button>
          ${menu}
        </div>
      </article>`;
    }

    function renderRecentRuns(runs) {
      if (!runs.length) {
        $("recent-runs").hidden = true;
        return;
      }
      $("recent-runs").hidden = false;
      const visible = runs.slice(0, RECENT_RUNS_VISIBLE);
      const older = runs.slice(RECENT_RUNS_VISIBLE);
      $("recent-runs-list").innerHTML = visible.map(renderRecentRunCard).join("");
      const olderEl = $("recent-runs-older");
      if (older.length) {
        olderEl.hidden = false;
        olderEl.innerHTML = `<details><summary>View all previous analyses (${older.length} more)</summary><div class="list" style="margin-top: 8px">${older.map(renderRecentRunCard).join("")}</div></details>`;
      } else {
        olderEl.hidden = true;
        olderEl.innerHTML = "";
      }
      const bindOpen = root => {
        root.querySelectorAll("[data-open-run]").forEach(button => {
          button.addEventListener("click", () => openRun(button.dataset.openRun));
        });
        wireRerunMenus(root);
      };
      bindOpen($("recent-runs-list"));
      if (older.length) bindOpen(olderEl);
    }

    function openRun(jobId) {
      if (jobId !== currentRunId) clearRecommendationCache();
      currentRunId = jobId;
      const url = new URL(window.location.href);
      url.searchParams.set("run", jobId);
      window.history.replaceState({}, "", url);
      api(`/app/analyze/runs/${encodeURIComponent(jobId)}`).then(status => {
        renderStatus(status);
        if (["running", "queued"].includes(status.overall_status)) startPolling();
      }).catch(error => renderError(error.message));
    }

    async function triggerRerun(parentJobId, rerunType) {
      setAnalyzeButtonState({ overall_status: "running" }, { starting: true });
      clearRecommendationCache();
      try {
        const status = await api(`/app/analyze/runs/${encodeURIComponent(parentJobId)}/rerun`, {
          method: "POST",
          body: JSON.stringify({ rerun_type: rerunType })
        });
        currentRunId = status.job_id;
        const url = new URL(window.location.href);
        url.searchParams.set("run", status.job_id);
        window.history.replaceState({}, "", url);
        renderStatus(status);
        startPolling();
      } catch (error) {
        setAnalyzeButtonState({ overall_status: "failed" });
        renderError(error.message);
      }
    }

    async function renderResults(status) {
      const summary = status.summary || {};
      const effectiveSummary = (summary.workspace || summary.recommendations) ? summary : (status.prior_summary || summary);
      if (!effectiveSummary.workspace && !effectiveSummary.recommendations) return;
      $("results").hidden = false;
      renderSafety(effectiveSummary.publishing_safety || summary.publishing_safety || status.publishing_safety || {});
      let summaryHtml = "";
      if (status.prior_summary && Object.keys(status.prior_summary).length) {
        summaryHtml = `<div class="notice"><strong>Previous completed result preserved.</strong> Updated sections reflect the latest partial rerun.</div>`;
      }
      if (effectiveSummary.ideation_short_circuit) {
        summaryHtml += `<div class="notice"><strong>Short-circuit analyze.</strong> This run used website analysis and AI opportunity ideation only.</div>`;
      }
      $("tab-summary").innerHTML = summaryHtml;
      renderSummary(effectiveSummary);
      const workspaceId = status.workspace_id || ((effectiveSummary.workspace || {}).id);
      const recItems = await renderRecommendations(effectiveSummary, workspaceId);
      renderSchedule(effectiveSummary);
      await restoreDraftState(workspaceId);
      renderDraft(effectiveSummary);
      const terminal = ["succeeded", "warning", "failed"].includes(status.overall_status || "");
      if (
        effectiveSummary.ideation_short_circuit
        && terminal
        && status.job_id
        && autoTabShownForRun !== status.job_id
        && Number((effectiveSummary.recommendations || {}).total ?? recItems.length) > 0
      ) {
        autoTabShownForRun = status.job_id;
        showTab("recommendations");
      }
      const mismatches = recommendationCountMismatches(effectiveSummary, recItems);
      const mismatchHtml = mismatches.length
        ? `<div class="notice">${mismatches.map(line => escapeHtml(line)).join("<br>")}</div>`
        : "";
      const explainHtml = renderRecommendationExplainability(recItems);
      const profile = (effectiveSummary.site || {}).strategy_profile || (summary.site || {}).strategy_profile || null;
      const profileHtml = profile
        ? `<section class="metric" style="margin-bottom:12px"><span>Site Strategy Profile</span><pre style="white-space:pre-wrap;margin:8px 0 0">${escapeHtml(JSON.stringify(profile, null, 2))}</pre></section>`
        : "";
      $("tab-diagnostics").innerHTML = `${profileHtml}${mismatchHtml}${explainHtml}<details><summary>Full run payload</summary><pre>${escapeHtml(JSON.stringify(status, null, 2))}</pre></details>`;
    }

    function renderRecommendationExplainability(items) {
      const ideationOnly = ideationShortCircuitActive(currentStatus || {});
      const rows = (items || []).filter(item => {
        if (!item) return false;
        if (ideationOnly) return item.source_type === "ai_opportunity_ideation";
        return item.metadata && (item.metadata.explainability || item.metadata.ai_review || item.source_type === "ai_editorial_strategist" || item.source_type === "ai_opportunity_ideation");
      });
      if (!rows.length) return "";
      const cards = rows.slice(0, 50).map(item => {
        const explain = item.metadata.explainability || {};
        const aiReview = item.metadata.ai_review || {};
        const entity = explain.entity_relevance !== undefined && explain.entity_relevance !== null
          ? `<p>Entity relevance: ${escapeHtml(explain.entity_relevance)}</p>`
          : "";
        const competitorBlock = explain.competitor_raw_signal
          ? `<p><strong>Competitor signal:</strong> ${escapeHtml(explain.competitor_raw_signal)}</p>
             <p><strong>Mapped entity:</strong> ${escapeHtml(explain.competitor_mapped_entity || "none")} · CREATE allowed: ${escapeHtml(String(explain.competitor_create_allowed ?? false))}</p>`
          : "";
        const strategistBlock = item.source_type === "ai_editorial_strategist" || item.metadata.rationale
          ? `<p><strong>Source:</strong> AI Editorial Strategist</p>
             <p><strong>Reason:</strong> ${escapeHtml(item.metadata.rationale || item.explanation || "")}</p>`
          : "";
        const ideationBlock = item.source_type === "ai_opportunity_ideation"
          ? `<p><strong>Source:</strong> AI Opportunity Ideation</p>
             <p><strong>Abstract:</strong> ${escapeHtml(item.metadata.abstract || item.demand_summary || "")}</p>
             <p><strong>Intent:</strong> ${escapeHtml(item.metadata.search_intent || "n/a")} · <strong>Content type:</strong> ${escapeHtml(item.metadata.content_type || "n/a")}</p>`
          : "";
        const reviewBlock = aiReview.reviewed_at
          ? `<p><strong>Original action:</strong> ${escapeHtml(item.metadata.oi_action || item.action || "")}</p>
             <p><strong>AI reviewed action:</strong> ${escapeHtml(aiReview.recommended_action || item.action || "")}</p>
             <p><strong>Site fit:</strong> ${escapeHtml(aiReview.site_fit ?? aiReview.relevance_score ?? "n/a")} · <strong>Search value:</strong> ${escapeHtml(aiReview.search_value ?? aiReview.content_usefulness_score ?? "n/a")}</p>
             <p><strong>Decision:</strong> ${escapeHtml(aiReview.decision || "n/a")} · <strong>Duplicate risk:</strong> ${escapeHtml(aiReview.duplicate_risk ?? "n/a")}</p>
             <p><strong>Reason:</strong> ${escapeHtml(aiReview.reason || "")}</p>`
          : "";
        const alignmentBlock = explain.business_alignment_tier
          ? `<p><strong>Business alignment:</strong> tier ${escapeHtml(explain.business_alignment_tier)} · score ${escapeHtml(explain.business_alignment_score ?? "n/a")}${explain.linked_product ? ` · product ${escapeHtml(explain.linked_product)}` : ""}${explain.linked_category ? ` · category ${escapeHtml(explain.linked_category)}` : ""}</p>`
          : "";
        return `<details class="item diag-rec">
          <summary><strong>${escapeHtml(item.title || item.topic)}</strong> · ${escapeHtml(item.action)} · score ${escapeHtml(explain.final_score ?? item.score ?? "n/a")}</summary>
          ${strategistBlock}
          ${ideationBlock}
          ${reviewBlock}
          ${alignmentBlock}
          <p>Niche relevance: ${escapeHtml(explain.niche_relevance ?? item.niche_relevance ?? "n/a")} · Business relevance: ${escapeHtml(explain.business_relevance ?? item.business_relevance ?? "n/a")} · Coverage gap: ${escapeHtml(explain.coverage_gap ?? item.coverage_gap ?? "n/a")}</p>
          <p>Competitor evidence: ${escapeHtml(explain.competitor_evidence ?? item.competitor_gap ?? 0)} · Demand evidence: ${escapeHtml(explain.external_demand ?? (item.has_external_evidence ? item.demand_score : 0))} · Source: ${escapeHtml(explain.source_type || item.source_type || "")}</p>
          ${entity}
          ${competitorBlock}
          <p><strong>Reason:</strong> ${escapeHtml(explain.action_reason || item.explanation || "")}</p>
          <p class="muted">${escapeHtml(explain.rank_reason || "")}</p>
        </details>`;
      }).join("");
      return `<section style="margin-bottom: 14px"><h3 style="margin: 0 0 10px">Recommendation scoring</h3><div class="list">${cards}</div></section>`;
    }

    function renderSafety(safety) {
      const live = safety.live_publish_available ? "Live enabled" : "Live blocked";
      $("safety-pill").innerHTML = `<span class="dot ${safety.live_publish_available ? "succeeded" : "warning"}"></span>${escapeHtml(live)} · manual review default`;
      $("publishing_mode").querySelector('option[value="live_publish"]').disabled = !safety.live_publish_available;
    }

    function renderDiscoveredCompetitors(competitorDiscovery) {
      const competitors = Array.isArray(competitorDiscovery.competitors) ? competitorDiscovery.competitors : [];
      if (!competitors.length) return "";
      const rows = competitors.map(item => {
        const domain = escapeHtml(item.domain || item.url || "");
        const source = escapeHtml(item.source || item.origin || "discovered");
        return `<div class="item"><strong>${domain}</strong><p>Source: ${source}</p></div>`;
      }).join("");
      return `<div class="list"><div class="item"><strong>Competitors discovered</strong></div>${rows}</div>`;
    }

    function renderCompetitorDiscoverySummary(competitorDiscovery) {
      const source = competitorDiscovery.source || "none";
      const provided = Number(competitorDiscovery.provided_count ?? 0);
      const discovered = Number(competitorDiscovery.discovered_count ?? 0);
      const total = Number(competitorDiscovery.selected_count ?? competitorDiscovery.competitors_selected ?? 0);
      const warning = String(competitorDiscovery.warning || "").trim();
      const webSearchSummary = String(competitorDiscovery.web_search_summary || "").trim();
      const sourceSummary = Array.isArray(competitorDiscovery.source_summary) ? competitorDiscovery.source_summary : [];
      const sourceLines = sourceSummary.map(item => {
        const label = item.label || item.source || "source";
        const note = item.note || (item.selected ? `${item.selected} selected` : (item.candidates ? `${item.candidates} candidate(s)` : "0"));
        return `${label}: ${note}`;
      });
      const otherDomains = Array.isArray(competitorDiscovery.other_discovered_domains) ? competitorDiscovery.other_discovered_domains : [];
      const otherLines = otherDomains.slice(0, 5).map(item => `${item.domain || item.url} (${String(item.classification || "unknown").replaceAll("_", " ")})`);
      if (total && (sourceLines.length || webSearchSummary)) {
        const sourcesBlock = sourceLines.length ? `<p>Sources:<br>${sourceLines.map(line => escapeHtml(line)).join("<br>")}</p>` : "";
        const otherBlock = otherLines.length ? `<p>Other discovered domains:<br>${otherLines.map(line => escapeHtml(line)).join("<br>")}</p>` : "";
        const webBlock = webSearchSummary && !sourceLines.length ? `<p>${escapeHtml(webSearchSummary)}</p>` : "";
        return `${renderDiscoveredCompetitors(competitorDiscovery)}<div class="item"><strong>Competitor discovery</strong><p>Competitors selected: ${escapeHtml(total)}</p>${sourcesBlock}${otherBlock}${webBlock}</div>`;
      }
      if (source === "provided+discovered") {
        return `${renderDiscoveredCompetitors(competitorDiscovery)}<div class="item"><strong>Competitor discovery</strong><p>Provided competitors: ${escapeHtml(provided)}<br>Discovered competitors: ${escapeHtml(discovered)}<br>Total analyzed: ${escapeHtml(total)}</p></div>`;
      }
      if (source === "discovered" && total) {
        return `${renderDiscoveredCompetitors(competitorDiscovery)}<div class="item"><strong>Competitor discovery</strong><p>Discovered competitors: ${escapeHtml(discovered || total)}<br>Total analyzed: ${escapeHtml(total)}</p></div>`;
      }
      if (source === "provided" && total) {
        return `${renderDiscoveredCompetitors(competitorDiscovery)}<div class="item"><strong>Competitor discovery</strong><p>Provided competitors: ${escapeHtml(provided || total)}<br>Automatic discovery: off<br>Total analyzed: ${escapeHtml(total)}</p>${warning ? `<p>${escapeHtml(warning)}</p>` : ""}</div>`;
      }
      if (source === "provided" && !total) {
        const reason = String(competitorDiscovery.reason_message || warning || "No valid provided competitors after filtering.").trim();
        const rejected = Array.isArray(competitorDiscovery.rejected_samples) ? competitorDiscovery.rejected_samples : [];
        const rejectedHtml = rejected.slice(0, 3).map(item => `<div>${escapeHtml(item.url || "")} — ${escapeHtml(item.reason || item.reason_code || "rejected")}</div>`).join("");
        return `<div class="notice"><strong>Competitor discovery: WARNING</strong><p>Automatic discovery is disabled. ${escapeHtml(reason)}</p>${rejectedHtml ? `<p><strong>Rejected URLs:</strong></p>${rejectedHtml}` : ""}<p><strong>Competitor analysis: SKIPPED</strong><br>No competitors available.</p></div>`;
      }
      if (!total) {
        const reason = String(competitorDiscovery.reason_message || warning || "No competitors could be identified automatically.").trim();
        const checkedHtml = (competitorDiscovery.sources_checked || []).map(item => {
          const label = {
            comparison_pages: "Comparison pages",
            outbound_domains: "Outbound domains",
            niche_peers: "Historical niche peers",
            workspace_history: "History",
            competitor_snapshots: "Competitor snapshots",
            web_search: "Web search",
          }[item] || item;
          return `<div>✓ ${escapeHtml(label)}</div>`;
        }).join("");
        const skippedHtml = (competitorDiscovery.sources_skipped || []).map(item => {
          if (!item || typeof item !== "object") return "";
          const label = { web_search: "Web search" }[item.source] || item.source;
          if (item.detail === "API key missing") return `<div>✗ ${escapeHtml(label)} (API key missing)</div>`;
          if (item.reason === "disabled") return `<div>✗ ${escapeHtml(label)} (disabled${item.detail ? ": " + item.detail : ""})</div>`;
          return `<div>✗ ${escapeHtml(label)} (${escapeHtml(item.reason || "skipped")})</div>`;
        }).filter(Boolean).join("");
        const webSummary = webSearchSummary || (String(skippedHtml).includes("API key missing") ? "Web search skipped: API key missing" : "");
        const candidatesFound = Number(competitorDiscovery.candidates_found ?? 0);
        const selected = Number(competitorDiscovery.selected_count ?? competitorDiscovery.competitors_selected ?? 0);
        return `<div class="notice"><strong>Competitor discovery: WARNING</strong><p>No competitors could be identified automatically.</p><p><strong>Reason:</strong> ${escapeHtml(reason)}</p>${webSummary ? `<p>${escapeHtml(webSummary)}</p>` : ""}${checkedHtml ? `<p><strong>Checked:</strong></p>${checkedHtml}` : ""}${skippedHtml ? `<p><strong>Skipped:</strong></p>${skippedHtml}` : ""}<p>Candidates found: ${escapeHtml(candidatesFound)}<br>Selected: ${escapeHtml(selected)}</p><p><strong>Competitor analysis: SKIPPED</strong><br>No competitors available.</p></div>`;
      }
      return "";
    }

    function renderSummary(summary) {
      const site = summary.site || {};
      const recs = summary.recommendations || {};
      const competitorDiscovery = summary.competitor_discovery || {};
      const competitorIntel = summary.competitor_intelligence || {};
      const coverageGaps = Array.isArray(competitorIntel.coverage_gaps) ? competitorIntel.coverage_gaps : [];
      const observations = Array.isArray(competitorIntel.seo_observations) ? competitorIntel.seo_observations : [];
      const competitorPages = ((competitorIntel.pages_analyzed || {}).total_competitor_pages) || 0;
      $("tab-summary").innerHTML = `
        <div class="cards">
          <div class="metric"><span>Pages analyzed</span><strong>${escapeHtml(site.pages_analyzed ?? 0)}</strong></div>
          <div class="metric"><span>Niche confidence</span><strong>${escapeHtml(site.confidence ?? "n/a")}</strong></div>
          <div class="metric"><span>Recommendations</span><strong>${escapeHtml(recs.total ?? 0)}</strong></div>
        </div>
        <div class="list">
          <div class="item"><strong>${escapeHtml((summary.workspace || {}).name || "Workspace")}</strong><p>${escapeHtml(site.url || "")} · ${escapeHtml(site.niche || "generic")}</p></div>
          ${renderCompetitorDiscoverySummary(competitorDiscovery)}
          ${competitorPages ? `<div class="item"><strong>Competitor Intelligence</strong><p>Competitor pages analyzed: ${escapeHtml(competitorPages)} · Coverage gaps: ${escapeHtml(coverageGaps.length)}</p>${coverageGaps.length ? `<p>Top gaps: ${coverageGaps.slice(0, 5).map(item => escapeHtml(item.topic || "")).filter(Boolean).join(", ")}</p>` : ""}${observations.length ? `<p>${observations.slice(0, 2).map(item => escapeHtml(item)).join(" · ")}</p>` : ""}</div>` : ""}
          ${(summary.warnings || []).map(w => `<div class="notice">${escapeHtml(w)}</div>`).join("")}
        </div>
      `;
    }

    let recommendationQueueFilter = "create";
    let recommendationItemsCache = { workspaceId: null, items: null };
    let manualIdeaState = {
      open: false,
      step: "form",
      manual: null,
      catalogProducts: [],
      selectedProducts: [],
      loading: false,
      error: "",
      duplicateWarnings: [],
    };

    function clearRecommendationCache() {
      recommendationItemsCache = { workspaceId: null, items: null };
    }

    function recommendationItems(summary) {
      const recs = (summary && summary.recommendations) || {};
      if (Array.isArray(recs.items) && recs.items.length) return recs.items;
      return recs.top || [];
    }

    function recommendationsIncomplete(summary, items) {
      const recs = (summary && summary.recommendations) || {};
      const total = Number(recs.total ?? 0);
      if (!total) return false;
      if (items.length < total) return true;
      const actual = recommendationActionCounts(items);
      return ["create", "refresh", "monitor", "ignore"].some(action => {
        const expected = Number(recs[action] ?? 0);
        return expected > 0 && actual[action] < expected;
      });
    }

    async function resolveRecommendationItems(summary, workspaceId) {
      const embedded = recommendationItems(summary);
      if (!recommendationsIncomplete(summary, embedded)) {
        return embedded;
      }
      if (!workspaceId) return embedded;
      if (recommendationItemsCache.workspaceId === workspaceId && recommendationItemsCache.items) {
        return recommendationItemsCache.items;
      }
      try {
        const payload = await api(`/autopilot/workspaces/${encodeURIComponent(workspaceId)}`);
        const full = payload.opportunity_recommendations
          || ((payload.opportunity_intelligence || {}).recommendations)
          || embedded;
        recommendationItemsCache = { workspaceId, items: full };
        return full;
      } catch (error) {
        return embedded;
      }
    }

    function recommendationActionCounts(items) {
      const counts = { create: 0, refresh: 0, monitor: 0, ignore: 0, all: items.length };
      items.forEach(item => {
        const action = String(item.action || "").toLowerCase();
        if (action in counts) counts[action] += 1;
      });
      return counts;
    }

    function recommendationQueueCounts(summary, items) {
      const recs = (summary && summary.recommendations) || {};
      const fromItems = recommendationActionCounts(items);
      return {
        create: Number(recs.create ?? fromItems.create),
        refresh: Number(recs.refresh ?? fromItems.refresh),
        monitor: Number(recs.monitor ?? fromItems.monitor),
        ignore: Number(recs.ignore ?? fromItems.ignore),
        all: Number(recs.total ?? fromItems.all),
      };
    }

    function recommendationCountMismatches(summary, items) {
      const recs = summary.recommendations || {};
      const actual = recommendationActionCounts(items);
      const mismatches = [];
      ["create", "refresh", "monitor", "ignore"].forEach(action => {
        const summaryCount = Number(recs[action] ?? 0);
        if (summaryCount !== actual[action]) {
          mismatches.push(`Recommendation count mismatch: summary says ${action}=${summaryCount}, list contains ${actual[action]} ${action} items.`);
        }
      });
      const totalSummary = Number(recs.total ?? 0);
      if (items.length && totalSummary !== items.length) {
        mismatches.push(`Recommendation count mismatch: summary total=${totalSummary}, list contains ${items.length} items.`);
      }
      return mismatches;
    }

    function filteredRecommendations(items, filter) {
      if (filter === "all") return items;
      return items.filter(item => String(item.action || "").toLowerCase() === filter);
    }

    function recommendationExplanation(item) {
      return String(item.explanation || (item.reasons || []).join(" ") || "").trim();
    }

    function existingContentLabel(item) {
      const meta = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
      const url = meta.inventory_url || meta.url || meta.existing_url;
      if (url) return String(url);
      if (item.related_content_id) return `Content record: ${item.related_content_id}`;
      return "";
    }

    function recommendationMetaLine(item) {
      const meta = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
      const ai = meta.ai_review && typeof meta.ai_review === "object" ? meta.ai_review : {};
      const classification = meta.recommendation_classification || "";
      const origin = meta.recommendation_source_bucket || "";
      const typeLabel = classification ? classification.replace(/_/g, " ").replace(/\\b\\w/g, c => c.toUpperCase()) : "";
      const originMap = { entity: "Entity", coverage: "Coverage Gap", competitor: "Competitor Gap", demand: "Demand Intent", trend: "Trend", research: "Research" };
      let originLabel = originMap[origin] || (item.source_type || "").replace(/_/g, " ");
      if (item.source_type === "manual_recommendation" || meta.manual_source) {
        originLabel = "Manual · AI-enhanced";
      } else if (item.source_type === "ai_opportunity_ideation" || meta.source_label) {
        originLabel = "AI opportunity ideation";
      }
      const commercial = ai.commercial_value;
      const dup = ai.duplicate_risk;
      const commercialLabel = commercial === undefined || commercial === null ? "" : (commercial >= 0.65 ? "High" : commercial >= 0.4 ? "Medium" : "Low");
      const dupLabel = dup === undefined || dup === null ? "" : (dup >= 0.55 ? "High" : dup <= 0.25 ? "Low" : "Medium");
      const parts = [];
      if (typeLabel) parts.push(`Type: ${typeLabel}`);
      if (originLabel) parts.push(`Origin: ${originLabel}`);
      if (meta.search_intent) parts.push(`Intent: ${meta.search_intent.replace(/_/g, " ")}`);
      if (meta.content_type) parts.push(`Content: ${meta.content_type.replace(/_/g, " ")}`);
      if (meta.recommendation_type) parts.push(`Rec: ${meta.recommendation_type.replace(/_/g, " ")}`);
      if (commercialLabel) parts.push(`Commercial Value: ${commercialLabel}`);
      if (dupLabel) parts.push(`Duplicate Risk: ${dupLabel}`);
      return parts.length ? `<p class="muted">${escapeHtml(parts.join(" · "))}</p>` : "";
    }

    function ideationOpportunityDetails(item) {
      const meta = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
      if (item.source_type !== "ai_opportunity_ideation" && !meta.abstract) return "";
      const abstract = meta.abstract || item.demand_summary || "";
      const products = Array.isArray(meta.related_products) ? meta.related_products : [];
      const reason = meta.priority_reason || item.explanation || "";
      const parts = [];
      if (abstract) parts.push(`<p>${escapeHtml(abstract)}</p>`);
      if (products.length) parts.push(`<p><strong>Products:</strong> ${escapeHtml(products.join(", "))}</p>`);
      if (reason && reason !== abstract) parts.push(`<p><strong>Reason:</strong> ${escapeHtml(reason)}</p>`);
      return parts.join("");
    }

    function renderIdeationRecommendationCard(item, index) {
      const meta = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
      const isManual = item.source_type === "manual_recommendation" || meta.manual_source;
      const abstract = meta.abstract || item.demand_summary || item.explanation || "";
      const products = Array.isArray(meta.related_products) ? meta.related_products : [];
      const safetyNotes = Array.isArray(meta.safety_notes) ? meta.safety_notes : [];
      const recType = meta.recommendation_type ? meta.recommendation_type.replace(/_/g, " ") : String(item.action || "create");
      const intent = meta.search_intent ? meta.search_intent.replace(/_/g, " ") : "";
      const contentType = meta.content_type ? meta.content_type.replace(/_/g, " ") : "";
      const pills = [
        isManual ? `<span>Manual</span><span>AI-enhanced</span>` : `<span>AI opportunity</span>`,
        `<span>${escapeHtml(recType)}</span>`,
        intent ? `<span>${escapeHtml(intent)}</span>` : "",
        contentType ? `<span>${escapeHtml(contentType)}</span>` : "",
      ].filter(Boolean).join("");
      return `<article class="item ideation-rec" data-rec-action="${escapeHtml(String(item.action || ""))}">
        <strong>${escapeHtml(item.title || item.topic)}</strong>
        <div class="meta-pills">${pills}</div>
        ${abstract ? `<p class="ideation-abstract">${escapeHtml(abstract)}</p>` : ""}
        ${products.length ? `<p><strong>Products:</strong> ${escapeHtml(products.join(", "))}</p>` : ""}
        ${safetyNotes.length ? `<p class="muted"><strong>Safety:</strong> ${escapeHtml(safetyNotes.join(" · "))}</p>` : ""}
        <div class="actions">${renderRecommendationActions(item, index)}</div>
      </article>`;
    }

    function renderRecommendationList(items, filter) {
      const filtered = filteredRecommendations(items, filter);
      if (!filtered.length) {
        return `<p class="notice">No recommendations in this queue.</p>`;
      }
      return filtered.map((item, index) => {
        if (
          item.source_type === "ai_opportunity_ideation"
          || item.source_type === "manual_recommendation"
          || (item.metadata && (item.metadata.direct_from_ideation || item.metadata.manual_source))
        ) {
          return renderIdeationRecommendationCard(item, index);
        }
        const existing = existingContentLabel(item);
        const existingHtml = existing
          ? `<p><strong>Existing page:</strong> ${escapeHtml(existing)}</p>`
          : "";
        const meta = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
        const showGenericExplain = !meta.abstract && recommendationExplanation(item);
        return `<article class="item" data-rec-action="${escapeHtml(String(item.action || ""))}">
          <strong>${escapeHtml(item.title || item.topic)}</strong>${item.metadata && item.metadata.ai_review ? ' <span class="pill">AI reviewed</span>' : ""}
          <p>${escapeHtml(item.action || "")} · ${escapeHtml(item.priority || "")} · score ${escapeHtml(item.score ?? "n/a")}</p>
          ${recommendationMetaLine(item)}
          ${ideationOpportunityDetails(item)}
          ${showGenericExplain ? `<p>${escapeHtml(recommendationExplanation(item))}</p>` : ""}
          ${existingHtml}
          <div class="actions">${renderRecommendationActions(item, index)}</div>
        </article>`;
      }).join("");
    }

    function renderRecommendationActions(item, index) {
      const action = String(item.action || "").toLowerCase();
      if (action === "create") {
        return `<button type="button" class="secondary" data-rec-index="${index}">Select for draft</button>`;
      }
      if (action === "refresh") {
        return `<button type="button" class="secondary" data-rec-index="${index}">Review refresh task</button>`;
      }
      if (action === "monitor") {
        return `<span class="pill">Keep monitoring</span><button type="button" class="secondary" data-rec-index="${index}">Promote to draft</button>`;
      }
      return "";
    }

    function wireRecommendationList(container, items, filter) {
      const filtered = filteredRecommendations(items, filter);
      container.querySelectorAll("[data-rec-index]").forEach(button => {
        button.addEventListener("click", () => {
          const match = filtered[Number(button.dataset.recIndex)];
          if (match) {
            selectedRecommendation = match;
            showTab("draft");
            renderDraft(currentStatus.summary || {});
          }
        });
      });
    }

    async function loadCatalogProductsForManual(workspaceId) {
      if (!workspaceId) return [];
      try {
        const payload = await api(`/workspaces/${encodeURIComponent(workspaceId)}/manual-recommendations/catalog-products`);
        return Array.isArray(payload.catalog_products) ? payload.catalog_products : [];
      } catch (_error) {
        return [];
      }
    }

    function renderManualSelectedChips(selected) {
      if (!selected.length) {
        return `<p class="muted manual-chip-empty">None selected. AI will infer products from your headline.</p>`;
      }
      return `<div class="manual-selected-chips">${selected.map(product => `
        <span class="pill manual-product-chip" data-product="${escapeHtml(product)}">
          ${escapeHtml(product)}
          <button type="button" class="manual-product-remove" aria-label="Remove ${escapeHtml(product)}">×</button>
        </span>`).join("")}</div>`;
    }

    function renderManualProductField(products, selected) {
      const countLabel = products.length
        ? `${products.length} catalog product${products.length === 1 ? "" : "s"} available`
        : "Run website analysis to load catalog products";
      return `
        <div class="manual-product-field">
          <p class="muted manual-field-help">
            Optional. Pin specific catalog products only when the idea should focus on them
            (for example a comparison or relationship article). Leave empty and AI will infer products from your headline.
          </p>
          <div id="manual-selected-products">${renderManualSelectedChips(selected)}</div>
          <input id="manual-product-search" type="search" placeholder="Search products to add…" autocomplete="off"${products.length ? "" : " disabled"}>
          <div id="manual-product-suggestions" class="manual-product-suggestions" hidden></div>
          <p class="muted" style="font-size:.85rem;margin-top:6px">${escapeHtml(countLabel)}</p>
        </div>`;
    }

    function wireManualProductPicker(products) {
      const selected = manualIdeaState.selectedProducts || [];
      const searchEl = $("manual-product-search");
      const suggestionsEl = $("manual-product-suggestions");
      const selectedEl = $("manual-selected-products");
      if (!searchEl || !suggestionsEl || !selectedEl) return;

      function refreshSelectedUi() {
        selectedEl.innerHTML = renderManualSelectedChips(manualIdeaState.selectedProducts || []);
        selectedEl.querySelectorAll(".manual-product-remove").forEach(button => {
          button.addEventListener("click", () => {
            const chip = button.closest("[data-product]");
            const value = chip && chip.dataset.product;
            manualIdeaState.selectedProducts = (manualIdeaState.selectedProducts || []).filter(item => item !== value);
            refreshSelectedUi();
            renderSuggestions(searchEl.value || "");
          });
        });
      }

      function renderSuggestions(query) {
        const q = String(query || "").trim().toLowerCase();
        const chosen = new Set(manualIdeaState.selectedProducts || []);
        const matches = products
          .filter(product => !chosen.has(product))
          .filter(product => !q || String(product).toLowerCase().includes(q))
          .slice(0, 8);
        if (!matches.length) {
          suggestionsEl.hidden = true;
          suggestionsEl.innerHTML = "";
          return;
        }
        suggestionsEl.hidden = false;
        suggestionsEl.innerHTML = matches.map(product => `
          <button type="button" class="manual-product-suggestion" data-product="${escapeHtml(product)}">${escapeHtml(product)}</button>
        `).join("");
        suggestionsEl.querySelectorAll(".manual-product-suggestion").forEach(button => {
          button.addEventListener("click", () => {
            const value = button.dataset.product;
            if (!value || chosen.has(value)) return;
            manualIdeaState.selectedProducts = [...(manualIdeaState.selectedProducts || []), value];
            searchEl.value = "";
            refreshSelectedUi();
            renderSuggestions("");
          });
        });
      }

      searchEl.addEventListener("input", () => renderSuggestions(searchEl.value || ""));
      searchEl.addEventListener("focus", () => renderSuggestions(searchEl.value || ""));
      refreshSelectedUi();
      renderSuggestions("");
    }

    function summaryFromStatus() {
      return (currentStatus && currentStatus.summary) || {};
    }

    function closeManualIdeaModal() {
      manualIdeaState = {
        open: false,
        step: "form",
        manual: null,
        catalogProducts: [],
        selectedProducts: [],
        loading: false,
        error: "",
        duplicateWarnings: [],
      };
      const overlay = $("manual-idea-overlay");
      if (overlay) overlay.hidden = true;
    }

    function renderManualIdeaModal() {
      let overlay = $("manual-idea-overlay");
      if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "manual-idea-overlay";
        overlay.className = "manual-idea-overlay";
        overlay.hidden = true;
        document.body.appendChild(overlay);
      }
      if (!manualIdeaState.open) {
        overlay.hidden = true;
        return;
      }
      overlay.hidden = false;
      const manual = manualIdeaState.manual || {};
      const products = manualIdeaState.catalogProducts || [];
      const productPicker = renderManualProductField(products, manualIdeaState.selectedProducts || []);
      const preview = manualIdeaState.step === "preview" ? `
        <div class="manual-idea-preview">
          <p><strong>Improved headline</strong><br>${escapeHtml(manual.enhanced_headline || manual.headline || "")}</p>
          <p><strong>Abstract</strong><br>${escapeHtml(manual.abstract || "")}</p>
          <p><strong>Content type</strong> ${escapeHtml(manual.content_type || "auto")}</p>
          <p><strong>Related products</strong> ${escapeHtml((manual.related_products || []).join(", ") || "—")}</p>
          ${Array.isArray(manual.safety_notes) && manual.safety_notes.length
            ? `<p><strong>Safety notes</strong><br>${escapeHtml(manual.safety_notes.join(" · "))}</p>`
            : ""}
          ${manualIdeaState.duplicateWarnings.length
            ? `<div class="notice">A similar recommendation or article may already exist.</div>`
            : ""}
        </div>
        <div class="modal-actions">
          <button type="button" id="manual-queue-btn" ${manualIdeaState.loading ? "disabled" : ""}>Add to recommendations</button>
          <button type="button" class="secondary" id="manual-edit-btn">Edit</button>
          <button type="button" class="secondary" id="manual-generate-btn" ${manualIdeaState.loading ? "disabled" : ""}>Generate article</button>
          <button type="button" class="secondary" id="manual-close-btn">Close</button>
        </div>` : `
        <label>Headline or idea
          <input id="manual-headline" type="text" value="${escapeHtml(manual.raw_headline || "")}" placeholder="BPC-157 and TB-500 are often discussed together. Why?">
        </label>
        <label>Optional notes
          <textarea id="manual-notes" placeholder="Explain why researchers compare them. Avoid combined-use advice.">${escapeHtml(manual.raw_notes || "")}</textarea>
        </label>
        ${productPicker}
        <label>Optional type
          <select id="manual-content-type">
            ${["auto", "research_overview", "comparison", "relationship", "mechanism", "faq", "handling"].map(type => `
              <option value="${escapeHtml(type)}" ${(manual.content_type_hint || manual.content_type || "auto") === type ? "selected" : ""}>${escapeHtml(type.replace(/_/g, " "))}</option>
            `).join("")}
          </select>
        </label>
        ${manualIdeaState.error ? `<div class="notice">${escapeHtml(manualIdeaState.error)}</div>` : ""}
        <div class="modal-actions">
          <button type="button" id="manual-enrich-btn" ${manualIdeaState.loading ? "disabled" : ""}>Improve with AI</button>
          <button type="button" class="secondary" id="manual-close-btn">Cancel</button>
        </div>`;
      overlay.innerHTML = `<div class="manual-idea-modal" role="dialog" aria-modal="true" aria-labelledby="manual-idea-title">
        <h3 id="manual-idea-title">Manual recommendation</h3>
        ${preview}
      </div>`;
      overlay.onclick = event => {
        if (event.target === overlay) closeManualIdeaModal();
      };
      $("manual-close-btn")?.addEventListener("click", closeManualIdeaModal);
      $("manual-enrich-btn")?.addEventListener("click", () => enrichManualIdea(workspaceIdFromStatus()));
      $("manual-edit-btn")?.addEventListener("click", () => {
        manualIdeaState.step = "form";
        renderManualIdeaModal();
      });
      $("manual-queue-btn")?.addEventListener("click", () => queueManualIdea(workspaceIdFromStatus(), false));
      $("manual-generate-btn")?.addEventListener("click", () => queueManualIdea(workspaceIdFromStatus(), true));
      if (manualIdeaState.step === "form") {
        wireManualProductPicker(products);
      }
    }

    function workspaceIdFromStatus() {
      return (currentStatus && currentStatus.workspace_id) || (summaryFromStatus().workspace || {}).id || "";
    }

    function readManualForm() {
      const contentType = $("manual-content-type")?.value || "auto";
      return {
        raw_headline: ($("manual-headline")?.value || "").trim(),
        raw_notes: ($("manual-notes")?.value || "").trim(),
        selected_products: manualIdeaState.selectedProducts || [],
        content_type: contentType === "auto" ? null : contentType,
      };
    }

    async function openManualIdeaModal(workspaceId) {
      const prior = manualIdeaState.manual || {};
      manualIdeaState = {
        open: true,
        step: "form",
        manual: prior,
        catalogProducts: await loadCatalogProductsForManual(workspaceId),
        selectedProducts: manualIdeaState.selectedProducts?.length
          ? manualIdeaState.selectedProducts
          : [...(prior.selected_products || prior.related_products || [])],
        loading: false,
        error: "",
        duplicateWarnings: [],
      };
      renderManualIdeaModal();
    }

    async function enrichManualIdea(workspaceId) {
      if (!workspaceId) return;
      const form = readManualForm();
      if (!form.raw_headline) {
        manualIdeaState.error = "Headline or idea is required.";
        renderManualIdeaModal();
        return;
      }
      manualIdeaState.loading = true;
      manualIdeaState.error = "";
      renderManualIdeaModal();
      try {
        const result = await api(`/workspaces/${encodeURIComponent(workspaceId)}/manual-recommendations/create-and-enrich`, {
          method: "POST",
          body: JSON.stringify(form),
        });
        manualIdeaState.manual = result.manual_recommendation || {};
        manualIdeaState.duplicateWarnings = manualIdeaState.manual.duplicate_warnings || [];
        manualIdeaState.step = "preview";
        manualIdeaState.loading = false;
        renderManualIdeaModal();
      } catch (error) {
        manualIdeaState.loading = false;
        manualIdeaState.error = error.message || "Enrichment failed.";
        renderManualIdeaModal();
      }
    }

    async function queueManualIdea(workspaceId, generateAfter) {
      const manual = manualIdeaState.manual || {};
      if (!workspaceId || !manual.id) return;
      manualIdeaState.loading = true;
      renderManualIdeaModal();
      try {
        let queueResult = await api(`/workspaces/${encodeURIComponent(workspaceId)}/manual-recommendations/${encodeURIComponent(manual.id)}/queue`, {
          method: "POST",
          body: JSON.stringify({ allow_duplicates: manualIdeaState.duplicateWarnings.length > 0 }),
        });
        if (queueResult.requires_confirmation) {
          manualIdeaState.duplicateWarnings = queueResult.duplicate_warnings || [];
          manualIdeaState.loading = false;
          renderManualIdeaModal();
          return;
        }
        invalidateRecommendationItemsCache();
        const summary = summaryFromStatus();
        const items = await resolveRecommendationItems(summary, workspaceId);
        if (currentStatus?.summary) {
          currentStatus.summary.recommendations = currentStatus.summary.recommendations || {};
          currentStatus.summary.recommendations.items = items;
        }
        const recommendation = queueResult.recommendation;
        closeManualIdeaModal();
        await renderRecommendations(summary, workspaceId);
        if (generateAfter && recommendation) {
          selectedRecommendation = recommendation;
          showTab("draft");
          renderDraft(summary);
          await generateDraft(recommendation);
        }
      } catch (error) {
        manualIdeaState.loading = false;
        manualIdeaState.error = error.message || "Queue failed.";
        renderManualIdeaModal();
      }
    }

    async function renderRecommendations(summary, workspaceId) {
      const embedded = recommendationItems(summary);
      const counts = recommendationQueueCounts(summary, embedded);
      const filters = [
        { key: "create", label: "Create" },
        { key: "refresh", label: "Refresh" },
        { key: "monitor", label: "Monitor" },
        { key: "ignore", label: "Ignore" },
        { key: "all", label: "All" },
      ];
      const filterButtons = filters.map(({ key, label }) => {
        const active = recommendationQueueFilter === key ? " active" : "";
        const count = counts[key] ?? 0;
        return `<button type="button" class="rec-queue-filter${active}" data-rec-filter="${escapeHtml(key)}">${escapeHtml(label)} <span class="count">${escapeHtml(count)}</span></button>`;
      }).join("");
      const shortCircuitBanner = summary.ideation_short_circuit
        ? `<div class="notice" style="margin-bottom:10px"><strong>AI opportunity mode.</strong> Recommendations come directly from website analysis + AI ideation — no market intelligence, competitor scoring, or reviewer filtering.</div>`
        : "";
      $("tab-recommendations").innerHTML = `
        ${shortCircuitBanner}
        <div class="rec-queue-toolbar">
          <div class="rec-queue-filters" role="tablist" aria-label="Recommendation queues">${filterButtons}</div>
          <div class="actions" style="margin:0">
            <button type="button" class="secondary" id="open-manual-idea"${workspaceId ? "" : " disabled"}>+ Manual idea</button>
            <button type="button" class="secondary" id="export-recommendations-csv"${workspaceId ? "" : " disabled"} title="Download create, refresh, and monitor recommendations as CSV">Export CSV</button>
          </div>
        </div>
        <div id="rec-queue-list" class="list">${renderRecommendationList(embedded, recommendationQueueFilter)}</div>`;
      const items = await resolveRecommendationItems(summary, workspaceId);
      if (items !== embedded) {
        $("rec-queue-list").innerHTML = renderRecommendationList(items, recommendationQueueFilter);
        wireRecommendationList($("rec-queue-list"), items, recommendationQueueFilter);
      } else {
        wireRecommendationList($("rec-queue-list"), items, recommendationQueueFilter);
      }
      $("tab-recommendations").querySelectorAll("[data-rec-filter]").forEach(button => {
        button.addEventListener("click", () => {
          recommendationQueueFilter = button.dataset.recFilter || "create";
          renderRecommendations(summary, workspaceId);
        });
      });
      $("export-recommendations-csv")?.addEventListener("click", () => exportRecommendationsCsv(workspaceId));
      $("open-manual-idea")?.addEventListener("click", () => openManualIdeaModal(workspaceId));
      return items;
    }

    function exportRecommendationsCsv(workspaceId) {
      if (!workspaceId) return;
      const url = `/autopilot/workspaces/${encodeURIComponent(workspaceId)}/recommendations/export?actions=create,refresh,monitor`;
      window.location.assign(url);
    }

    function renderSchedule(summary) {
      const schedule = summary.schedule || [];
      $("tab-schedule").innerHTML = `<div class="list">${schedule.length ? schedule.map((item, index) => `
        <article class="item">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.suggested_publish_date || "unscheduled")} · ${escapeHtml(item.content_type || "content")} · ${escapeHtml(item.priority || "")}</p>
          <p>Source: ${escapeHtml(item.recommendation_source || "recommendation")}</p>
          <div class="actions"><button type="button" data-schedule-index="${index}">Generate draft</button></div>
        </article>`).join("") : `<p class="notice">No schedule generated yet.</p>`}</div>`;
      document.querySelectorAll("[data-schedule-index]").forEach(button => button.addEventListener("click", () => {
        selectedScheduleItem = schedule[Number(button.dataset.scheduleIndex)];
        showTab("draft");
        renderDraft(summary);
      }));
    }

    function draftStorageKey(workspaceId) {
      const id = workspaceId || currentStatus?.workspace_id;
      return id ? `analyze-draft:${id}` : "";
    }

    function saveDraftState() {
      const key = draftStorageKey();
      if (!key) return;
      sessionStorage.setItem(key, JSON.stringify({
        activeDraftJobId,
        latestDraftJobId: latestDraftJob?.job_id || ""
      }));
    }

    function renderDraftConsole(logs, job) {
      const el = $("draft-console");
      if (!el) return;
      const status = job?.status || "queued";
      const lines = (logs || []).map(entry => {
        const level = entry.level === "error" ? "error" : (entry.level === "warning" ? "warn" : "");
        const step = entry.step ? `[${entry.step}] ` : "";
        const time = entry.created_at ? `${formatTime(entry.created_at)} ` : "";
        return `<div class="log-line ${level}">${escapeHtml(time + step + (entry.message || ""))}</div>`;
      });
      const header = `<div class="log-line"><strong>Status:</strong> ${escapeHtml(status)}</div>`;
      el.innerHTML = header + (lines.length ? lines.join("") : `<div class="log-line">Waiting for pipeline steps…</div>`);
      el.scrollTop = el.scrollHeight;
    }

    function draftJobIsActive(job) {
      return job && DRAFT_ACTIVE_STATUSES.has(job.status || "");
    }

    function wordpressPublishNeedsRetry(job) {
      if (wordpressPostIsMissing(job)) return false;
      return Boolean(job?.wordpress_publish_error) && !job?.wordpress_post_id;
    }

    function wordpressPostIsPublished(job) {
      const status = String(job?.wordpress_status || "").trim().toLowerCase();
      return WORDPRESS_PUBLISHED_STATUSES.has(status);
    }

    function wordpressDraftIsEditable(job) {
      return Boolean(job?.wordpress_post_id) && !wordpressPostIsPublished(job) && !wordpressPostNotManaged(job);
    }

    function wordpressPostIsMissing(job) {
      return String(job?.wordpress_publish_error || "").startsWith("missing_draft:");
    }

    function wordpressPostNotManaged(job) {
      return String(job?.wordpress_publish_error || "").startsWith("not_trendplot_draft:");
    }

    function refreshWordPressDisabledReason(job, settings) {
      if (!connectorIsReady(settings)) return "Configure and enable the WordPress connector.";
      if (!job?.wordpress_post_id) return "No WordPress post is linked to this article.";
      return "";
    }

    function canRefreshWordPressStatus(job, settings) {
      return !refreshWordPressDisabledReason(job, settings);
    }

    function renderWordPressRefreshButton(job, { compact = false } = {}) {
      const jobId = job?.job_id || job?.id;
      if (!jobId || !job?.wordpress_post_id) return "";
      const settings = connectorSettingsCache.settings;
      const reason = refreshWordPressDisabledReason(job, settings);
      const canRefresh = canRefreshWordPressStatus(job, settings);
      return `<button type="button" class="${compact ? "secondary" : ""}" data-refresh-wordpress-status="${escapeHtml(jobId)}" ${canRefresh ? "" : "disabled"}${reason ? ` title="${escapeHtml(reason)}"` : ""}>Refresh WordPress status</button>`;
    }

    function updateWordPressDisabledReason(job, settings) {
      if (!connectorIsReady(settings)) return "Configure and enable the WordPress connector.";
      if (!job?.wordpress_post_id) return "No WordPress draft is linked to this article.";
      if (wordpressPostIsPublished(job)) return "This post is published in WordPress.";
      const status = job.status || "";
      if (DRAFT_ACTIVE_STATUSES.has(status)) return "Wait for article generation to finish.";
      if (["failed_generation", "cancelled"].includes(status)) return "Article generation did not complete successfully.";
      if (job.publishable_html_available === false) return "Publishable HTML is not available yet.";
      return "";
    }

    function canUpdateWordPressDraft(job, settings) {
      return !updateWordPressDisabledReason(job, settings);
    }

    function effectiveArticleJobStatus(job) {
      const status = job?.status || "";
      if (wordpressPublishNeedsRetry(job)) return "failed_publish";
      if (status === "published_draft" && !job?.wordpress_post_id) return "failed_publish";
      return status;
    }

    function formatArticleJobStatus(status) {
      const labels = {
        queued: "Queued",
        running_generation: "Generating",
        running_repair: "Repairing",
        running_expansion: "Expanding",
        running_review: "Reviewing",
        running_rendering: "Rendering",
        running_publish: "Sending to WordPress",
        generated: "Generated",
        ready_for_review: "Ready for review",
        published_draft: "WordPress draft created",
        failed_publish: "Failed to send",
        failed_generation: "Generation failed",
        failed_quality: "Quality check failed",
        failed_sanity: "Sanity check failed",
        cancelled: "Cancelled",
      };
      return labels[status] || String(status || "unknown").replace(/_/g, " ");
    }

    function articleJobTitle(job) {
      const input = job?.request_input || {};
      return job?.structured_article?.title || input.title || `Article ${job?.job_id || job?.id || ""}`;
    }

    function connectorEnvironmentProfile(settings, environment) {
      const s = settings || {};
      const envName = environment || s.active_environment || "staging";
      const profile = s.environments?.[envName];
      if (profile) {
        return { ...profile, environment: envName, label: profile.label || envName };
      }
      return {
        environment: envName,
        label: envName === "production" ? "Production" : "Staging",
        wordpress_base_url: s.wordpress_base_url || "",
        trendplot_site_id: s.trendplot_site_id || "",
        shared_secret_configured: Boolean(s.shared_secret_configured),
        last_connection_status: s.last_connection_status,
        last_connection_checked_at: s.last_connection_checked_at,
        last_connection_error: s.last_connection_error,
        connector_plugin_version: s.connector_plugin_version,
        connector_api_version: s.connector_api_version,
      };
    }

    function connectorIsReady(settings, environment) {
      const s = settings || {};
      if (!s.connector_enabled) return false;
      const profile = connectorEnvironmentProfile(s, environment);
      return Boolean(profile.wordpress_base_url && profile.trendplot_site_id && profile.shared_secret_configured);
    }

    function connectorActiveLabel(settings) {
      const profile = connectorEnvironmentProfile(settings);
      const host = (profile.wordpress_base_url || "").replace(/^https?:\\/\\//, "").replace(/\\/$/, "");
      return host ? `${profile.label} (${host})` : profile.label;
    }

    function mergeJobWordPressState(jobId, fields) {
      if (latestDraftJob?.job_id === jobId) {
        latestDraftJob = { ...latestDraftJob, ...fields };
      }
      workspaceDraftJobs = workspaceDraftJobs.map(job => job.id === jobId ? { ...job, ...fields } : job);
    }

    function sendToWordPressDisabledReason(job, settings) {
      if (!connectorIsReady(settings)) return "Configure and enable the WordPress connector.";
      if (!job?.job_id && !job?.id) return "Select an article draft first.";
      const jobId = job.job_id || job.id;
      if (!jobId) return "Select an article draft first.";
      const status = job.status || "";
      if (DRAFT_ACTIVE_STATUSES.has(status)) return "Wait for article generation to finish.";
      if (["failed_generation", "cancelled"].includes(status)) return "Article generation did not complete successfully.";
      if (job.publishable_html_available === false) return "Publishable HTML is not available yet.";
      if (job.wordpress_post_id && !wordpressPublishNeedsRetry(job)) {
        return "WordPress draft already exists for this article.";
      }
      return "";
    }

    function canSendJobToWordPress(job, settings) {
      return !sendToWordPressDisabledReason(job, settings);
    }

    function renderWordPressSendStatus(job) {
      if (!job) return `<p class="muted" style="font-size:.88rem;margin-top:6px">Select an article draft first.</p>`;
      if (wordpressPostIsMissing(job)) {
        return `<div class="notice" style="margin-top:8px">
          <strong>WordPress post missing</strong>
          <p style="margin:4px 0 0">${escapeHtml(job.wordpress_publish_error || "The linked WordPress post was not found.")}</p>
          <p class="muted" style="margin:6px 0 0;font-size:.85rem">Use <strong>Send to WordPress as draft</strong> to create a new draft.</p>
        </div>`;
      }
      if (job.wordpress_post_id) {
        let headline = "WordPress draft";
        if (wordpressPostIsPublished(job)) headline = "Published in WordPress";
        else if (wordpressPostNotManaged(job)) headline = "WordPress post no longer managed by Trendplot";
        const synced = job.last_wordpress_sync_at ? ` · Synced ${escapeHtml(formatTime(job.last_wordpress_sync_at))}` : "";
        const updated = job.wordpress_draft_updated_at ? ` · Updated ${escapeHtml(formatTime(job.wordpress_draft_updated_at))}` : "";
        return `<div class="notice" style="margin-top:8px">
          <strong>${escapeHtml(headline)}</strong>
          <p style="margin:4px 0 0">Post ID: ${escapeHtml(job.wordpress_post_id)}${job.wordpress_draft_created_at ? ` · Sent ${escapeHtml(formatTime(job.wordpress_draft_created_at))}` : ""}${updated}${synced}</p>
          ${job.wordpress_publish_error && !wordpressPostNotManaged(job) ? `<p class="muted" style="margin:4px 0 0">${escapeHtml(job.wordpress_publish_error)}</p>` : ""}
          ${wordpressPostNotManaged(job) ? `<p class="muted" style="margin:4px 0 0">${escapeHtml(job.wordpress_publish_error)}</p>` : ""}
          ${wordpressDraftIsEditable(job) ? `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Regenerated this article in Trendplot? Use <strong>Update WordPress draft</strong> to sync the same post.</p>` : ""}
          ${wordpressPostIsPublished(job) ? `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Published manually in WordPress. Use <strong>Refresh WordPress status</strong> after changes there.</p>` : ""}
          ${wordpressDraftIsEditable(job) ? `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Deleted the post in WordPress? Use <strong>Send to WordPress again</strong> to create a new draft.</p>` : ""}
        </div>`;
      }
      if (job.wordpress_publish_error) {
        const reason = sendToWordPressDisabledReason(job, connectorSettingsCache.settings);
        return `<div class="notice" style="margin-top:8px">
          <strong>WordPress send failed</strong>
          <p style="margin:4px 0 0">${escapeHtml(job.wordpress_publish_error)}</p>
          ${reason ? `<p class="muted" style="margin:6px 0 0;font-size:.85rem">${escapeHtml(reason)}</p>` : `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Fix the issue above, then use <strong>Try WordPress send again</strong>.</p>`}
        </div>`;
      }
      if (canSendJobToWordPress(job, connectorSettingsCache.settings)) {
        return `<p class="muted" style="font-size:.88rem;margin-top:6px">This will create a draft post in WordPress for the selected Trendplot article.</p>`;
      }
      const reason = sendToWordPressDisabledReason(job, connectorSettingsCache.settings);
      return reason ? `<p class="muted" style="font-size:.88rem;margin-top:6px">${escapeHtml(reason)}</p>` : "";
    }

    function renderSendToWordPressButton(job, { compact = false } = {}) {
      const jobId = job?.job_id || job?.id;
      if (!jobId) {
        return `<button type="button" class="${compact ? "secondary" : ""}" data-send-wordpress disabled title="Select an article draft first.">Send to WordPress as draft</button>`;
      }
      const settings = connectorSettingsCache.settings;
      const canSend = canSendJobToWordPress(job, settings);
      const sendDisabledReason = sendToWordPressDisabledReason(job, settings);
      const canUpdate = canUpdateWordPressDraft(job, settings);
      const updateDisabledReason = updateWordPressDisabledReason(job, settings);
      if (wordpressPostIsMissing(job)) {
        return `<button type="button" class="${compact ? "secondary" : ""}" data-send-wordpress="${escapeHtml(jobId)}" ${canSend ? "" : "disabled"}${sendDisabledReason ? ` title="${escapeHtml(sendDisabledReason)}"` : ""}>Send to WordPress as draft</button>`;
      }
      const retry = wordpressPublishNeedsRetry(job);
      if (retry) {
        return `<button type="button" class="${compact ? "secondary" : ""}" data-send-wordpress="${escapeHtml(jobId)}" ${canSend ? "" : "disabled"}${sendDisabledReason ? ` title="${escapeHtml(sendDisabledReason)}"` : ""}>Try WordPress send again</button>`;
      }
      const sent = Boolean(job.wordpress_post_id);
      if (sent) {
        const open = job.wordpress_edit_url
          ? `<a class="pill" href="${escapeHtml(job.wordpress_edit_url)}" target="_blank" rel="noreferrer">Open in WordPress</a>`
          : "";
        const refresh = renderWordPressRefreshButton(job, { compact });
        if (wordpressPostNotManaged(job)) {
          return `${open ? `${open} ` : ""}${refresh}`;
        }
        if (wordpressPostIsPublished(job)) {
          return `${open ? `${open} ` : ""}${refresh}`;
        }
        const update = `<button type="button" class="${compact ? "" : ""}" data-update-wordpress="${escapeHtml(jobId)}" ${canUpdate ? "" : "disabled"}${updateDisabledReason ? ` title="${escapeHtml(updateDisabledReason)}"` : ""}>Update WordPress draft</button>`;
        const canResend = connectorIsReady(settings)
          && !DRAFT_ACTIVE_STATUSES.has(job.status || "")
          && !["failed_generation", "cancelled"].includes(job.status || "");
        const resend = canResend
          ? `<button type="button" class="secondary" data-resend-wordpress="${escapeHtml(jobId)}">Send to WordPress again</button>`
          : "";
        return `${update}${open ? ` ${open}` : ""}${refresh ? ` ${refresh}` : ""}${resend ? ` ${resend}` : ""}`;
      }
      return `<button type="button" class="${compact ? "secondary" : ""}" data-send-wordpress="${escapeHtml(jobId)}" ${canSend ? "" : "disabled"}${sendDisabledReason ? ` title="${escapeHtml(sendDisabledReason)}"` : ""}>Send to WordPress as draft</button>`;
    }

    function renderDraftJobActions(job, { active = false } = {}) {
      const cardJob = job.id === latestDraftJob?.job_id ? { ...job, ...latestDraftJob, job_id: job.id } : { ...job, job_id: job.id };
      return `
        <a class="pill" href="/jobs/${encodeURIComponent(job.id)}/preview" target="_blank" rel="noreferrer">Preview HTML</a>
        <a class="pill" href="/jobs/${encodeURIComponent(job.id)}" target="_blank" rel="noreferrer">Job JSON</a>
        ${renderSendToWordPressButton(cardJob, { compact: true })}
        <button type="button" class="secondary" data-generate-seo="${escapeHtml(job.id)}">Generate SEO</button>
        ${active ? `<button type="button" class="secondary draft-stop-btn" data-stop-draft-job="${escapeHtml(job.id)}">Stop</button>` : ""}
        <button type="button" class="secondary draft-delete-btn" data-delete-draft-job="${escapeHtml(job.id)}">Delete</button>`;
    }

    function seoFieldValue(job, field) {
      const value = job?.[field];
      return value == null ? "" : String(value);
    }

    function renderJobSeoOptimizationReport(job) {
      const report = job?.seo_optimization_report || job?.optimization_report;
      if (!report || typeof report !== "object") return "";
      const items = [];
      if (report.focus_keyword_intro) items.push("Focus keyword added to intro");
      if (report.focus_keyword_heading) items.push("Focus keyword added to heading");
      if (report.seo_title_improved) items.push("SEO title improved");
      if (report.meta_description_improved) items.push("Meta description improved");
      if (report.slug_recommended) items.push(`Slug recommended: ${report.slug_recommended}`);
      if (report.canonical_url_improved && report.canonical_url_recommended) {
        items.push("Canonical URL shortened");
      }
      if (report.internal_links_added) items.push(`${report.internal_links_added} internal article link(s) added`);
      if (report.paragraphs_split) items.push(`${report.paragraphs_split} long paragraph(s) split`);
      if (report.image_alt_suggestions) items.push("Image alt suggestions created");
      if (!items.length && Array.isArray(report.changes) && report.changes.length) {
        items.push(...report.changes.slice(0, 4));
      }
      if (!items.length) return "";
      return `<p class="muted" style="margin:8px 0 0;font-size:.85rem"><strong>SEO optimization:</strong> ${escapeHtml(items.join(" · "))}</p>`;
    }

    function renderJobSeoStatus(job) {
      const lines = [];
      if (job?.seo_optimized_at) {
        lines.push(`Optimized ${escapeHtml(formatTime(job.seo_optimized_at))}`);
      }
      if (job?.seo_generated_at) {
        lines.push(`Generated ${escapeHtml(formatTime(job.seo_generated_at))}`);
      }
      if (job?.seo_synced_at) {
        lines.push(`Synced to WordPress ${escapeHtml(formatTime(job.seo_synced_at))}`);
      }
      if (job?.rank_math_score != null && job.rank_math_score !== "") {
        lines.push(`Rank Math score ${escapeHtml(String(job.rank_math_score))}`);
      }
      const errorText = job?.seo_last_error || (String(job?.seo_status_message || "").toLowerCase().includes("fail") ? job.seo_status_message : "");
      if (errorText) {
        lines.push(`<span style="color:#8b2e2e">${escapeHtml(errorText)}</span>`);
      } else if (job?.seo_status_message && !String(job.seo_status_message).toLowerCase().includes("fail")) {
        lines.push(escapeHtml(job.seo_status_message));
      }
      if (!lines.length) {
        return `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Generate SEO from the article, review fields, then sync to Rank Math in WordPress.</p>`;
      }
      return `<p class="muted" style="margin:6px 0 0;font-size:.85rem">${lines.join(" · ")}</p>`;
    }

    function canSyncJobSeo(job, settings) {
      if (!connectorIsReady(settings)) return false;
      if (!job?.wordpress_post_id) return false;
      return Boolean(seoFieldValue(job, "seo_title") && seoFieldValue(job, "seo_description"));
    }

    function wordpressSlugFromJob(job) {
      const url = String(job?.wordpress_public_url || "").trim();
      if (!url) return "";
      try {
        const parts = new URL(url).pathname.replace(/\/+$/, "").split("/").filter(Boolean);
        return parts[parts.length - 1] || "";
      } catch (error) {
        return "";
      }
    }

    function renderSlugSyncWarning(job) {
      const warning = String(job?.slug_sync_warning || "").trim();
      if (warning) {
        return `<p class="muted" style="margin:8px 0 0;font-size:.85rem;padding:8px 10px;background:#fff8e8;border:1px solid #f0d9a8;border-radius:8px">${escapeHtml(warning)}</p>`;
      }
      const recommended = seoFieldValue(job, "recommended_slug");
      const actual = wordpressSlugFromJob(job);
      if (!recommended || !actual || recommended === actual) return "";
      return `<p class="muted" style="margin:8px 0 0;font-size:.85rem;padding:8px 10px;background:#fff8e8;border:1px solid #f0d9a8;border-radius:8px">WordPress slug is <strong>${escapeHtml(actual)}</strong> but Trendplot recommends <strong>${escapeHtml(recommended)}</strong>. Update the Trendplot Connector plugin to apply the <code>slug</code> field, then use <strong>Update WordPress draft</strong>. Until then, edit the permalink in WordPress manually.</p>`;
    }

    function renderJobSeoWorkflowNotice() {
      return `<p class="muted" style="margin:6px 0 0;font-size:.85rem">Run SEO Optimization updates Trendplot. <strong>Sync SEO to WordPress</strong> pushes title, description, canonical URL, and focus keyword only — not the post permalink. Use <strong>Update WordPress draft</strong> to push article body and the recommended slug (requires connector plugin support).</p>`;
    }

    function renderPublishedSeoOptimizationNotice(job) {
      if (!wordpressPostIsPublished(job)) return "";
      const report = job?.seo_optimization_report || job?.optimization_report;
      const hasLocalBodyChanges = Boolean(
        report && (
          report.internal_links_added
          || report.paragraphs_split
          || report.focus_keyword_intro
          || report.focus_keyword_heading
          || report.slug_recommended
        )
      );
      if (!hasLocalBodyChanges && !job?.seo_optimized_at) return "";
      return `<p class="muted" style="margin:8px 0 0;font-size:.85rem;padding:8px 10px;background:#fff8e8;border:1px solid #f0d9a8;border-radius:8px"><strong>Published in WordPress:</strong> body, internal links, and permalink changes from SEO optimization stay in Trendplot until you edit the post in WordPress. Sync SEO can still update Rank Math metadata (title, description, canonical).</p>`;
    }

    function renderJobSeoSection(job) {
      const jobId = job?.job_id || job?.id;
      if (!jobId) return "";
      const settings = connectorSettingsCache.settings;
      const canSync = canSyncJobSeo(job, settings);
      const syncTitle = !connectorIsReady(settings)
        ? "Configure and enable the WordPress connector."
        : (!job?.wordpress_post_id ? "Link a WordPress post first." : "");
      const fields = [
        ["seo_title", "SEO Title"],
        ["seo_description", "Meta Description"],
        ["seo_focus_keyword", "Focus Keyword"],
        ["seo_canonical_url", "Canonical URL"],
        ["seo_robots", "Robots"],
        ["seo_schema_type", "Schema Type"],
      ];
      const inputs = fields.map(([name, label]) => {
        const multiline = name === "seo_description";
        const value = escapeHtml(seoFieldValue(job, name));
        if (multiline) {
          return `<label style="display:block;margin:8px 0 0;font-size:.88rem">${escapeHtml(label)}<textarea data-seo-field="${name}" data-seo-job="${escapeHtml(jobId)}" rows="3" style="width:100%;margin-top:4px">${value}</textarea></label>`;
        }
        return `<label style="display:block;margin:8px 0 0;font-size:.88rem">${escapeHtml(label)}<input data-seo-field="${name}" data-seo-job="${escapeHtml(jobId)}" type="text" value="${value}" style="width:100%;margin-top:4px"></label>`;
      }).join("");
      const recommendedSlug = escapeHtml(seoFieldValue(job, "recommended_slug"));
      const slugHint = recommendedSlug
        ? `<label style="display:block;margin:8px 0 0;font-size:.88rem">Recommended slug (Trendplot)<input type="text" value="${recommendedSlug}" readonly style="width:100%;margin-top:4px;background:#f8fafc" title="Sent on Update WordPress draft for draft posts. Does not change the live permalink for published posts."></label>`
        : "";
      return `<div class="seo-panel" data-seo-panel="${escapeHtml(jobId)}" style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border,#ddd)">
        <strong>SEO (Rank Math)</strong>
        ${renderJobSeoWorkflowNotice()}
        ${inputs}
        ${slugHint}
        ${renderSlugSyncWarning(job)}
        ${renderPublishedSeoOptimizationNotice(job)}
        ${renderJobSeoStatus(job)}
        ${renderJobSeoOptimizationReport(job)}
        <div class="actions" style="margin-top:10px;flex-wrap:wrap">
          <button type="button" data-generate-seo="${escapeHtml(jobId)}">Generate SEO</button>
          <button type="button" class="secondary" data-run-seo-optimization="${escapeHtml(jobId)}">Run SEO Optimization</button>
          <button type="button" class="secondary" data-save-seo="${escapeHtml(jobId)}">Save SEO</button>
          <button type="button" class="secondary" data-sync-seo="${escapeHtml(jobId)}" ${canSync ? "" : "disabled"}${syncTitle ? ` title="${escapeHtml(syncTitle)}"` : ""}>Sync SEO to WordPress</button>
          <button type="button" class="secondary" data-refresh-seo="${escapeHtml(jobId)}" ${job?.wordpress_post_id && connectorIsReady(settings) ? "" : "disabled"}${syncTitle ? ` title="${escapeHtml(syncTitle)}"` : ""}>Refresh SEO from WordPress</button>
        </div>
      </div>`;
    }

    function readSeoFieldsFromPanel(jobId) {
      const panel = document.querySelector(`[data-seo-panel="${CSS.escape(jobId)}"]`);
      if (!panel) return {};
      const fields = {};
      panel.querySelectorAll("[data-seo-field]").forEach(input => {
        fields[input.getAttribute("data-seo-field")] = input.value || "";
      });
      return fields;
    }

    function applyJobSeoResult(jobId, result) {
      const fields = {
        seo_title: result.seo_title ?? undefined,
        seo_description: result.seo_description ?? undefined,
        seo_focus_keyword: result.seo_focus_keyword ?? undefined,
        seo_canonical_url: result.seo_canonical_url ?? result.canonical_url_recommended ?? undefined,
        seo_robots: result.seo_robots ?? undefined,
        seo_schema_type: result.seo_schema_type ?? undefined,
        seo_generated_at: result.seo_generated_at ?? undefined,
        seo_synced_at: result.seo_synced_at ?? undefined,
        seo_last_error: result.seo_last_error ?? undefined,
        rank_math_score: result.rank_math_score ?? undefined,
        recommended_slug: result.recommended_slug ?? undefined,
        seo_optimized_at: result.seo_optimized_at ?? undefined,
        seo_optimization_report: result.optimization_report ?? result.seo_optimization_report ?? undefined,
        suggested_featured_image_alt: result.suggested_featured_image_alt ?? undefined,
        suggested_inline_image_alt: result.suggested_inline_image_alt ?? undefined,
      };
      Object.keys(fields).forEach(key => {
        if (fields[key] === undefined) delete fields[key];
      });
      if (result.status === "failed") {
        fields.seo_last_error = result.seo_last_error || result.message || "SEO sync failed.";
        fields.seo_status_message = fields.seo_last_error;
      } else if (result.status === "synced") {
        fields.seo_last_error = null;
        fields.seo_status_message = "SEO synced to WordPress";
        if (result.last_wordpress_sync_at) fields.last_wordpress_sync_at = result.last_wordpress_sync_at;
      } else if (result.status === "refreshed") {
        fields.seo_last_error = null;
        fields.seo_status_message = "SEO refreshed from WordPress";
        if (result.last_wordpress_sync_at) fields.last_wordpress_sync_at = result.last_wordpress_sync_at;
      } else if (result.status === "generated") {
        fields.seo_last_error = null;
        fields.seo_status_message = "SEO generated — review fields before syncing";
      } else if (result.status === "saved") {
        fields.seo_status_message = "SEO saved";
      } else if (result.status === "optimized") {
        fields.seo_last_error = null;
        fields.seo_status_message = "SEO optimization complete";
      }
      mergeJobWordPressState(jobId, fields);
    }

    async function runJobSeoOptimization(jobId) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await api(`/jobs/${encodeURIComponent(jobId)}/seo/optimize`, { method: "POST" });
        applyJobSeoResult(jobId, result);
        refreshDraftWordPressControls();
      } catch (error) {
        mergeJobWordPressState(jobId, { seo_status_message: error.message || "SEO optimization failed." });
        refreshDraftWordPressControls();
        alert(error.message || "SEO optimization failed.");
      }
    }

    async function generateJobSeo(jobId) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await api(`/jobs/${encodeURIComponent(jobId)}/seo/generate`, { method: "POST" });
        applyJobSeoResult(jobId, result);
        refreshDraftWordPressControls();
      } catch (error) {
        mergeJobWordPressState(jobId, { seo_status_message: error.message || "SEO generation failed." });
        refreshDraftWordPressControls();
        alert(error.message || "SEO generation failed.");
      }
    }

    async function saveJobSeo(jobId, { silent = false } = {}) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const payload = readSeoFieldsFromPanel(jobId);
        const result = await api(`/jobs/${encodeURIComponent(jobId)}/seo`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        applyJobSeoResult(jobId, result);
        refreshDraftWordPressControls();
      } catch (error) {
        mergeJobWordPressState(jobId, { seo_status_message: error.message || "Failed to save SEO." });
        refreshDraftWordPressControls();
        if (!silent) alert(error.message || "Failed to save SEO.");
        throw error;
      }
    }

    async function syncJobSeo(jobId) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        await saveJobSeo(jobId, { silent: true });
        const result = await api(`/jobs/${encodeURIComponent(jobId)}/seo/sync`, { method: "POST" });
        applyJobSeoResult(jobId, result);
        refreshDraftWordPressControls();
        if (result.status === "failed") alert(result.message || "SEO sync failed.");
      } catch (error) {
        mergeJobWordPressState(jobId, { seo_status_message: error.message || "SEO sync failed." });
        refreshDraftWordPressControls();
        alert(error.message || "SEO sync failed.");
      }
    }

    async function refreshJobSeo(jobId) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await api(`/jobs/${encodeURIComponent(jobId)}/seo/refresh`, { method: "POST" });
        applyJobSeoResult(jobId, result);
        refreshDraftWordPressControls();
        if (result.status === "failed") alert(result.message || "SEO refresh failed.");
      } catch (error) {
        mergeJobWordPressState(jobId, { seo_status_message: error.message || "SEO refresh failed." });
        refreshDraftWordPressControls();
        alert(error.message || "SEO refresh failed.");
      }
    }

    function refreshDraftWordPressControls() {
      const resultEl = $("draft-result");
      if (latestDraftJob && resultEl && !isDraftJobRunning()) {
        resultEl.innerHTML = renderDraftJob(latestDraftJob);
      }
      workspaceDraftJobs.forEach(job => {
        const actions = document.querySelector(`[data-draft-job-actions="${job.id}"]`);
        if (!actions) return;
        actions.innerHTML = renderDraftJobActions(job, { active: draftJobIsActive(job) });
      });
      wireSendToWordPressButtons();
    }

    function renderWorkspaceDraftJobsList() {
      if (!workspaceDraftJobs.length) return "";
      return `<div class="draft-jobs-list"><h3 style="margin: 12px 0 8px; font-size: 1rem;">Recent Trendplot article drafts</h3><div class="list">${workspaceDraftJobs.map(job => {
        const input = job.request_input || {};
        const selected = job.id === selectedArticleJobId;
        const active = draftJobIsActive(job);
        const cardJob = job.id === latestDraftJob?.job_id ? { ...job, ...latestDraftJob, job_id: job.id } : { ...job, job_id: job.id };
        return `<article class="item${selected ? " selected" : ""}" data-draft-job-id="${escapeHtml(job.id)}">
          <strong>${escapeHtml(articleJobTitle(cardJob))}</strong>
          <p>${escapeHtml(formatArticleJobStatus(effectiveArticleJobStatus(cardJob)))} · ${escapeHtml(formatTime(job.updated_at || job.created_at))}</p>
          <p>${escapeHtml(input.target_keyword || "")}</p>
          ${job.wordpress_post_id ? `<p class="muted" style="font-size:.85rem">WordPress draft #${escapeHtml(job.wordpress_post_id)}</p>` : ""}
          <div class="actions" data-draft-job-actions="${escapeHtml(job.id)}">
            ${renderDraftJobActions(job, { active })}
          </div>
        </article>`;
      }).join("")}</div></div>`;
    }

    async function loadWorkspaceDraftJobs(workspaceId) {
      if (!workspaceId) {
        workspaceDraftJobs = [];
        return;
      }
      try {
        workspaceDraftJobs = await api(`/jobs/recent?workspace_id=${encodeURIComponent(workspaceId)}&limit=15`);
      } catch (error) {
        workspaceDraftJobs = [];
      }
    }

    async function restoreDraftState(workspaceId) {
      await loadWorkspaceDraftJobs(workspaceId);
      const key = draftStorageKey(workspaceId);
      if (!key) return;
      let stored = null;
      try {
        stored = JSON.parse(sessionStorage.getItem(key) || "null");
      } catch (error) {
        stored = null;
      }
      const jobId = stored?.activeDraftJobId || stored?.latestDraftJobId || "";
      if (!jobId) return;
      activeDraftJobId = jobId;
      try {
        const detail = await api(`/jobs/${encodeURIComponent(jobId)}`);
        if (DRAFT_ACTIVE_STATUSES.has(detail.job?.status)) {
          startDraftPolling();
          return;
        }
        latestDraftJob = await api(`/jobs/${encodeURIComponent(jobId)}/generation-result`);
        selectedArticleJobId = jobId;
      } catch (error) {
        if (DRAFT_ACTIVE_STATUSES.has(workspaceDraftJobs.find(j => j.id === jobId)?.status)) {
          startDraftPolling();
        }
      }
    }

    function stopDraftPolling() {
      if (draftPollTimer) {
        clearInterval(draftPollTimer);
        draftPollTimer = null;
      }
    }

    async function pollDraftJobOnce() {
      if (!activeDraftJobId) return;
      const detail = await api(`/jobs/${encodeURIComponent(activeDraftJobId)}`);
      renderDraftConsole(detail.logs || [], detail.job || {});
      const status = detail.job?.status || "";
      if (!DRAFT_ACTIVE_STATUSES.has(status)) {
        stopDraftPolling();
        const generateBtn = $("generate-draft");
        if (generateBtn) generateBtn.disabled = false;
        if (status === "cancelled") {
          $("draft-result").innerHTML = `<div class="notice">Draft generation stopped.</div>`;
          activeDraftJobId = "";
          latestDraftJob = null;
          saveDraftState();
          await loadWorkspaceDraftJobs(currentStatus?.workspace_id);
          if (currentStatus?.summary) renderDraft(currentStatus.summary);
          return;
        }
        if (status === "failed_generation") {
          $("draft-result").innerHTML = `<div class="notice">${escapeHtml(detail.job?.last_error || "Draft generation failed.")}</div>`;
          saveDraftState();
          await loadWorkspaceDraftJobs(currentStatus?.workspace_id);
          if (currentStatus?.summary) renderDraft(currentStatus.summary);
          return;
        }
        try {
          latestDraftJob = await api(`/jobs/${encodeURIComponent(activeDraftJobId)}/generation-result`);
          selectedArticleJobId = activeDraftJobId;
        } catch (error) {
          latestDraftJob = { job_id: activeDraftJobId, status, last_error: detail.job?.last_error };
          selectedArticleJobId = activeDraftJobId;
        }
        activeDraftJobId = "";
        saveDraftState();
        await loadWorkspaceDraftJobs(currentStatus?.workspace_id);
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      }
    }

    function startDraftPolling() {
      stopDraftPolling();
      if (!activeDraftJobId) return;
      const tick = async () => {
        try {
          await pollDraftJobOnce();
        } catch (error) {
          stopDraftPolling();
          const consoleEl = $("draft-console");
          if (consoleEl) consoleEl.innerHTML += `<div class="log-line error">${escapeHtml(error.message)}</div>`;
        }
      };
      tick();
      draftPollTimer = setInterval(tick, 1500);
    }

    function wireDraftJobList() {
      document.querySelectorAll("[data-draft-job-id]").forEach(item => {
        item.addEventListener("click", async event => {
          if (event.target.closest("[data-stop-draft-job], [data-delete-draft-job]")) return;
          activeDraftJobId = item.dataset.draftJobId;
          selectedArticleJobId = activeDraftJobId;
          saveDraftState();
          const listed = workspaceDraftJobs.find(j => j.id === activeDraftJobId);
          if (draftJobIsActive(listed)) {
            startDraftPolling();
          } else {
            stopDraftPolling();
            try {
              latestDraftJob = await api(`/jobs/${encodeURIComponent(activeDraftJobId)}/generation-result`);
            } catch (error) {
              latestDraftJob = { job_id: activeDraftJobId, status: listed?.status || "unknown", request_input: listed?.request_input || {} };
            }
          }
          if (currentStatus?.summary) renderDraft(currentStatus.summary);
        });
      });
      document.querySelectorAll("[data-stop-draft-job]").forEach(button => {
        button.addEventListener("click", event => {
          event.stopPropagation();
          stopDraftJob(button.dataset.stopDraftJob);
        });
      });
      document.querySelectorAll("[data-delete-draft-job]").forEach(button => {
        button.addEventListener("click", event => {
          event.stopPropagation();
          deleteDraftJob(button.dataset.deleteDraftJob);
        });
      });
    }

    async function stopDraftJob(jobId) {
      const targetId = jobId || activeDraftJobId;
      if (!targetId) return;
      try {
        await api(`/jobs/${encodeURIComponent(targetId)}/cancel`, { method: "POST" });
        stopDraftPolling();
        if (activeDraftJobId === targetId) {
          activeDraftJobId = "";
          latestDraftJob = null;
        }
        saveDraftState();
        await loadWorkspaceDraftJobs(currentStatus?.workspace_id);
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      } catch (error) {
        $("draft-result").innerHTML = `<div class="notice">${escapeHtml(error.message)}</div>`;
      }
    }

    async function deleteDraftJob(jobId) {
      if (!jobId) return;
      const job = workspaceDraftJobs.find(entry => entry.id === jobId);
      const title = job?.request_input?.title || "this article job";
      if (!window.confirm(`Delete "${title}" and remove its saved artifacts? This cannot be undone.`)) return;
      try {
        if (draftJobIsActive(job)) {
          await api(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
        }
        await api(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
        stopDraftPolling();
        if (activeDraftJobId === jobId) activeDraftJobId = "";
        if (latestDraftJob?.job_id === jobId) latestDraftJob = null;
        if (selectedArticleJobId === jobId) selectedArticleJobId = "";
        saveDraftState();
        await loadWorkspaceDraftJobs(currentStatus?.workspace_id);
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      } catch (error) {
        $("draft-result").innerHTML = `<div class="notice">${escapeHtml(error.message)}</div>`;
      }
    }

    function isDraftJobRunning() {
      if (draftPollTimer) return true;
      const listed = activeDraftJobId ? workspaceDraftJobs.find(j => j.id === activeDraftJobId) : null;
      if (draftJobIsActive(listed)) return true;
      return false;
    }

    async function loadConnectorSettings(workspaceId) {
      if (!workspaceId) return null;
      if (connectorSettingsCache.workspaceId === workspaceId && connectorSettingsCache.settings) {
        return connectorSettingsCache.settings;
      }
      try {
        const payload = await api(`/workspaces/${encodeURIComponent(workspaceId)}/wordpress-connector`);
        connectorSettingsCache = { workspaceId, settings: payload.settings || {} };
        return connectorSettingsCache.settings;
      } catch (_error) {
        return null;
      }
    }

    function renderConnectorEnvironmentFields(settings, environment) {
      const profile = connectorEnvironmentProfile(settings, environment);
      const prefix = `wp-connector-${environment}`;
      const secretConfigured = Boolean(profile.shared_secret_configured);
      return `
        <fieldset class="wp-connector-env-fields" data-connector-env="${escapeHtml(environment)}">
          <legend>${escapeHtml(profile.label)} server</legend>
          <p class="muted" style="font-size:.85rem;margin:0 0 8px">
            Status: ${escapeHtml(profile.last_connection_status || "not tested")}
            ${profile.wordpress_base_url ? ` · ${escapeHtml(profile.wordpress_base_url)}` : ""}
          </p>
          <label>WordPress base URL
            <input id="${prefix}-base-url" type="url" value="${escapeHtml(profile.wordpress_base_url || "")}" placeholder="https://example.com">
          </label>
          <label>Trendplot site ID
            <input id="${prefix}-site-id" value="${escapeHtml(profile.trendplot_site_id || "")}">
          </label>
          <label>Shared secret ${secretConfigured ? `<span class="muted">(configured — leave blank to keep)</span>` : ""}
            <input id="${prefix}-secret" type="password" placeholder="${secretConfigured ? "Leave blank to keep existing secret" : "Paste shared secret"}">
          </label>
          <button type="button" class="secondary" data-connector-test-env="${escapeHtml(environment)}">Test ${escapeHtml(profile.label)} connection</button>
        </fieldset>`;
    }

    function renderWordPressConnectorPanel(settings) {
      const s = settings || {};
      const active = connectorEnvironmentProfile(s);
      const status = active.last_connection_status || "not tested";
      const statusLabel = status === "connected" ? "Connected" : status === "failed" ? "Failed" : "Not tested";
      return `
        <section class="wp-connector-panel" id="wp-connector-panel">
          <h3>WordPress connector</h3>
          <p class="wp-connector-status">
            Upload target: <strong>${escapeHtml(connectorActiveLabel(s))}</strong>
            · Active connection: <strong>${escapeHtml(statusLabel)}</strong>
            ${active.connector_plugin_version ? ` · Plugin ${escapeHtml(active.connector_plugin_version)}` : ""}
            ${active.connector_api_version ? ` · API ${escapeHtml(active.connector_api_version)}` : ""}
            ${active.last_connection_checked_at ? ` · Checked ${escapeHtml(active.last_connection_checked_at)}` : ""}
          </p>
          ${active.last_connection_error && status === "failed" ? `<div class="notice">${escapeHtml(active.last_connection_error)}</div>` : ""}
          <label style="display:block;margin:8px 0 0">Send drafts to
            <select id="wp-connector-active-env">
              <option value="staging" ${(s.active_environment || "staging") === "staging" ? "selected" : ""}>Staging</option>
              <option value="production" ${s.active_environment === "production" ? "selected" : ""}>Production</option>
            </select>
          </label>
          <p class="muted" style="font-size:.88rem;margin:8px 0 0">Configure both servers below. Switch the upload target when you are ready to publish to production.</p>
          <details class="wp-connector-settings">
            <summary>Connector settings</summary>
            <label style="display:flex;align-items:center;gap:8px;margin-top:8px">
              <input type="checkbox" id="wp-connector-enabled" ${s.connector_enabled ? "checked" : ""}> Enable connector
            </label>
            ${renderConnectorEnvironmentFields(s, "staging")}
            ${renderConnectorEnvironmentFields(s, "production")}
            <div class="modal-actions">
              <button type="button" class="secondary" id="wp-connector-save">Save all connector settings</button>
            </div>
          </details>
        </section>`;
    }

    function readConnectorEnvironmentPayload(environment) {
      const prefix = `wp-connector-${environment}`;
      const payload = {
        wordpress_base_url: ($(prefix + "-base-url")?.value || "").trim(),
        trendplot_site_id: ($(prefix + "-site-id")?.value || "").trim(),
      };
      const secret = ($(prefix + "-secret")?.value || "").trim();
      if (secret) payload.trendplot_shared_secret = secret;
      return payload;
    }

    async function saveConnectorSettings(workspaceId) {
      const payload = {
        connector_enabled: Boolean($("wp-connector-enabled")?.checked),
        active_environment: ($("wp-connector-active-env")?.value || "staging").trim(),
        environments: {
          staging: readConnectorEnvironmentPayload("staging"),
          production: readConnectorEnvironmentPayload("production"),
        },
      };
      const result = await api(`/workspaces/${encodeURIComponent(workspaceId)}/wordpress-connector`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      connectorSettingsCache = { workspaceId, settings: result.settings || {} };
      return connectorSettingsCache.settings;
    }

    async function testConnectorSettings(workspaceId, environment) {
      return api(`/workspaces/${encodeURIComponent(workspaceId)}/wordpress-connector/test`, {
        method: "POST",
        body: JSON.stringify({ environment: environment || ($("wp-connector-active-env")?.value || "staging") }),
      });
    }

    async function setConnectorActiveEnvironment(workspaceId, environment) {
      const result = await api(`/workspaces/${encodeURIComponent(workspaceId)}/wordpress-connector`, {
        method: "PUT",
        body: JSON.stringify({ active_environment: environment }),
      });
      connectorSettingsCache = { workspaceId, settings: result.settings || {} };
      return connectorSettingsCache.settings;
    }

    async function createConnectorDraft(jobId, { force = false } = {}) {
      return api(`/jobs/${encodeURIComponent(jobId)}/wordpress-connector/draft`, {
        method: "POST",
        body: JSON.stringify({ force }),
      });
    }

    async function updateConnectorDraft(jobId) {
      return api(`/jobs/${encodeURIComponent(jobId)}/wordpress-connector/draft/update`, {
        method: "POST",
      });
    }

    async function refreshConnectorStatus(jobId) {
      return api(`/jobs/${encodeURIComponent(jobId)}/wordpress-connector/status/refresh`, {
        method: "POST",
      });
    }

    function applyWordPressRefreshResult(jobId, result) {
      const syncedAt = result.last_wordpress_sync_at || new Date().toISOString();
      if (result.status === "failed") {
        const code = result.error_code || "failed";
        mergeJobWordPressState(jobId, {
          wordpress_publish_error: result.message ? `${code}: ${result.message}` : `${code}: WordPress status refresh failed.`,
          last_wordpress_sync_at: syncedAt,
        });
        return;
      }
      if (result.status === "missing") {
        mergeJobWordPressState(jobId, {
          wordpress_post_id: "",
          wordpress_edit_url: "",
          wordpress_public_url: "",
          wordpress_status: "",
          wordpress_publish_error: result.message ? `missing_draft: ${result.message}` : "missing_draft: WordPress post was not found.",
          last_wordpress_sync_at: syncedAt,
        });
        return;
      }
      const fields = {
        wordpress_post_id: String(result.wordpress_post_id || ""),
        wordpress_edit_url: result.wordpress_edit_url || "",
        wordpress_public_url: result.wordpress_public_url || "",
        wordpress_status: result.wordpress_status || "",
        wordpress_draft_updated_at: result.wordpress_draft_updated_at || "",
        last_wordpress_sync_at: syncedAt,
      };
      if (result.status === "not_managed") {
        fields.wordpress_publish_error = result.message ? `not_trendplot_draft: ${result.message}` : "not_trendplot_draft: WordPress post is not managed by Trendplot.";
      } else {
        fields.wordpress_publish_error = null;
      }
      mergeJobWordPressState(jobId, fields);
    }

    async function refreshArticleWordPressStatus(jobId, { silent = false } = {}) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await refreshConnectorStatus(jobId);
        applyWordPressRefreshResult(jobId, result);
        refreshDraftWordPressControls();
      } catch (error) {
        mergeJobWordPressState(jobId, {
          wordpress_publish_error: error.message || "Failed to refresh WordPress status.",
          last_wordpress_sync_at: new Date().toISOString(),
        });
        refreshDraftWordPressControls();
        if (!silent) {
          alert(error.message || "Failed to refresh WordPress status.");
        }
      }
    }

    async function maybeAutoRefreshWordPressStatus(job) {
      const jobId = job?.job_id || job?.id;
      if (!jobId || !job?.wordpress_post_id) return;
      if (!connectorIsReady(connectorSettingsCache.settings)) return;
      const lastSync = job.last_wordpress_sync_at;
      if (lastSync) {
        const age = Date.now() - Date.parse(lastSync);
        if (!Number.isNaN(age) && age >= 0 && age < WP_STATUS_AUTO_REFRESH_MS) return;
      }
      await refreshArticleWordPressStatus(jobId, { silent: true });
    }

    async function updateArticleWordPressDraft(jobId) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await updateConnectorDraft(jobId);
        const syncedAt = result.last_wordpress_sync_at || new Date().toISOString();
        mergeJobWordPressState(jobId, {
          wordpress_post_id: String(result.wordpress_post_id || ""),
          wordpress_edit_url: result.wordpress_edit_url || "",
          wordpress_public_url: result.wordpress_public_url || "",
          wordpress_status: result.wordpress_status || "draft",
          wordpress_draft_updated_at: result.wordpress_draft_updated_at || syncedAt,
          last_wordpress_sync_at: syncedAt,
          wordpress_publish_error: null,
          slug_sync_warning: result.slug_sync_warning || null,
          status: "published_draft",
        });
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      } catch (error) {
        mergeJobWordPressState(jobId, {
          wordpress_publish_error: error.message || "Failed to update WordPress draft.",
        });
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      }
    }

    async function sendArticleToWordPress(jobId, { force = false } = {}) {
      if (!jobId) return;
      selectedArticleJobId = jobId;
      try {
        const result = await createConnectorDraft(jobId, { force });
        const sentAt = new Date().toISOString();
        const fields = {
          wordpress_post_id: String(result.wordpress_post_id || ""),
          wordpress_edit_url: result.wordpress_edit_url || "",
          wordpress_public_url: result.wordpress_public_url || "",
          wordpress_status: result.wordpress_status || "draft",
          wordpress_draft_created_at: sentAt,
          wordpress_publish_error: null,
          slug_sync_warning: result.slug_sync_warning || null,
          status: result.status === "created" || result.status === "duplicate" || result.status === "existing"
            ? "published_draft"
            : (latestDraftJob?.status || "published_draft"),
        };
        mergeJobWordPressState(jobId, fields);
        if (result.status === "duplicate" && result.message) {
          alert(result.message);
        }
        refreshDraftWordPressControls();
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      } catch (error) {
        mergeJobWordPressState(jobId, {
          wordpress_post_id: "",
          wordpress_edit_url: "",
          wordpress_public_url: "",
          wordpress_status: "",
          wordpress_draft_created_at: "",
          wordpress_publish_error: error.message || "Failed to send to WordPress.",
          status: "failed_publish",
        });
        if (currentStatus?.summary) renderDraft(currentStatus.summary);
      }
    }

    function renderDraft(summary) {
      const safety = summary.publishing_safety || {};
      const candidate = selectedScheduleItem || selectedRecommendation;
      const generating = isDraftJobRunning();
      const canGenerate = Boolean(candidate) && !generating;
      const connectorPanel = renderWordPressConnectorPanel(connectorSettingsCache.settings);
      $("tab-draft").innerHTML = `
        ${candidate ? `<div class="item"><strong>${escapeHtml(candidate.title || candidate.topic)}</strong><p>${escapeHtml(candidate.target_keyword || candidate.topic || "")}</p></div>` : `<div class="notice">Select a recommendation or schedule item first.</div>`}
        <div class="notice" style="font-size: .9rem;">OpenAI enforces tokens-per-minute on your API key (shown in 429 responses, e.g. 30k TPM). That limit is not set in this app; upgrading your OpenAI tier raises it and reduces failed reruns.</div>
        <div class="actions">
          <button type="button" id="generate-draft" ${canGenerate && !generating ? "" : "disabled"}>${generating ? "Generating…" : "Generate article draft"}</button>
          ${generating ? `<button type="button" class="secondary" id="stop-active-draft">Stop running</button>` : ""}
        </div>
        ${safety.draft_disabled_reason ? `<div class="notice">${escapeHtml(safety.draft_disabled_reason)}</div>` : ""}
        ${generating || activeDraftJobId ? `<div id="draft-console" class="draft-console"></div>` : ""}
        ${connectorPanel}
        <div id="draft-result" class="list" style="margin-top: 10px">${latestDraftJob && !generating ? renderDraftJob(latestDraftJob) : (generating ? `<div class="notice">Pipeline running — see log above.</div>` : `<div class="notice">Select a Trendplot article draft below, or generate one first.</div>`)}</div>
        ${renderWorkspaceDraftJobsList()}
      `;
      if (generating || activeDraftJobId) {
        api(`/jobs/${encodeURIComponent(activeDraftJobId)}`).then(detail => {
          renderDraftConsole(detail.logs || [], detail.job || {});
        }).catch(() => {});
      }
      $("generate-draft")?.addEventListener("click", () => generateDraft(candidate));
      $("stop-active-draft")?.addEventListener("click", () => stopDraftJob(activeDraftJobId));
      const workspaceId = currentStatus?.workspace_id;
      loadConnectorSettings(workspaceId).then(async () => {
        const panel = $("wp-connector-panel");
        if (panel) panel.outerHTML = renderWordPressConnectorPanel(connectorSettingsCache.settings);
        wireWordPressConnectorPanel(workspaceId);
        refreshDraftWordPressControls();
        if (latestDraftJob && !isDraftJobRunning()) {
          await maybeAutoRefreshWordPressStatus(latestDraftJob);
        }
      });
      wireWordPressConnectorPanel(workspaceId);
      wireDraftJobList();
      wireSendToWordPressButtons();
    }

    function wireSendToWordPressButtons() {
      document.querySelectorAll("[data-send-wordpress]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-send-wordpress");
          if (!jobId) return;
          button.disabled = true;
          try {
            await sendArticleToWordPress(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-resend-wordpress]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-resend-wordpress");
          if (!jobId) return;
          if (!window.confirm("Create a new WordPress draft for this Trendplot article? Use this if the previous WordPress post was deleted.")) {
            return;
          }
          button.disabled = true;
          try {
            await sendArticleToWordPress(jobId, { force: true });
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-update-wordpress]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-update-wordpress");
          if (!jobId) return;
          button.disabled = true;
          try {
            await updateArticleWordPressDraft(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-refresh-wordpress-status]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-refresh-wordpress-status");
          if (!jobId) return;
          button.disabled = true;
          try {
            await refreshArticleWordPressStatus(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-generate-seo]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-generate-seo");
          if (!jobId) return;
          button.disabled = true;
          try {
            await generateJobSeo(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-run-seo-optimization]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-run-seo-optimization");
          if (!jobId) return;
          button.disabled = true;
          try {
            await runJobSeoOptimization(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-save-seo]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-save-seo");
          if (!jobId) return;
          button.disabled = true;
          try {
            await saveJobSeo(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-sync-seo]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-sync-seo");
          if (!jobId) return;
          button.disabled = true;
          try {
            await syncJobSeo(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
      document.querySelectorAll("[data-refresh-seo]").forEach(button => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          const jobId = button.getAttribute("data-refresh-seo");
          if (!jobId) return;
          button.disabled = true;
          try {
            await refreshJobSeo(jobId);
          } finally {
            button.disabled = false;
          }
        });
      });
    }

    function wireWordPressConnectorPanel(workspaceId) {
      $("wp-connector-save")?.addEventListener("click", async () => {
        if (!workspaceId) return;
        try {
          await saveConnectorSettings(workspaceId);
          $("wp-connector-panel").outerHTML = renderWordPressConnectorPanel(connectorSettingsCache.settings);
          wireWordPressConnectorPanel(workspaceId);
          refreshDraftWordPressControls();
        } catch (error) {
          alert(error.message || "Failed to save connector settings.");
        }
      });
      $("wp-connector-active-env")?.addEventListener("change", async event => {
        if (!workspaceId) return;
        const environment = event.target.value || "staging";
        if (environment === "production" && !window.confirm("Switch WordPress upload target to Production? New drafts will be created on the production server.")) {
          event.target.value = connectorSettingsCache.settings?.active_environment || "staging";
          return;
        }
        try {
          await setConnectorActiveEnvironment(workspaceId, environment);
          $("wp-connector-panel").outerHTML = renderWordPressConnectorPanel(connectorSettingsCache.settings);
          wireWordPressConnectorPanel(workspaceId);
          refreshDraftWordPressControls();
        } catch (error) {
          alert(error.message || "Failed to switch upload target.");
          event.target.value = connectorSettingsCache.settings?.active_environment || "staging";
        }
      });
      document.querySelectorAll("[data-connector-test-env]").forEach(button => {
        button.addEventListener("click", async () => {
          if (!workspaceId) return;
          const environment = button.getAttribute("data-connector-test-env") || "staging";
          button.disabled = true;
          try {
            const result = await testConnectorSettings(workspaceId, environment);
            if (result.settings) connectorSettingsCache = { workspaceId, settings: result.settings };
            $("wp-connector-panel").outerHTML = renderWordPressConnectorPanel(connectorSettingsCache.settings);
            wireWordPressConnectorPanel(workspaceId);
            refreshDraftWordPressControls();
          } catch (error) {
            alert(error.message || "Connection test failed.");
          } finally {
            button.disabled = false;
          }
        });
      });
    }

    function buildGeneratePayload(candidate) {
      const meta = candidate.metadata && typeof candidate.metadata === "object" ? candidate.metadata : {};
      const payload = {
        title: candidate.title || candidate.topic,
        target_keyword: candidate.target_keyword || candidate.topic || candidate.title,
        product_name: (Array.isArray(meta.related_products) && meta.related_products[0]) || candidate.product_name || candidate.target_keyword || candidate.topic || candidate.title,
        product_url: (currentStatus.summary.workspace || {}).website_url || (currentStatus.summary.site || {}).url,
        publish_policy: "manual_review",
        workspace_id: currentStatus.workspace_id,
        content_plan_item_id: candidate.id || null,
        origin_type: candidate.id ? "content_plan_item" : "operator_recommendation"
      };
      const isManual = candidate.source_type === "manual_recommendation" || meta.manual_source;
      const isIdeation = candidate.source_type === "ai_opportunity_ideation" || meta.abstract || isManual;
      if (isIdeation) {
        payload.opportunity_context = meta.article_brief && typeof meta.article_brief === "object"
          ? { ...meta.article_brief }
          : {
            headline: candidate.title || candidate.topic,
            abstract: meta.abstract || candidate.demand_summary || "",
            search_intent: meta.search_intent || "",
            content_type: meta.content_type || "",
            recommendation_type: meta.recommendation_type || "",
            related_products: meta.related_products || [],
            related_topics: meta.related_topics || [],
            target_audience: meta.target_audience || "",
            safety_notes: meta.safety_notes || [],
            science_focus: meta.science_focus === true,
            raw_notes: meta.raw_notes || "",
            source: isManual ? "manual_recommendation" : "ai_opportunity_ideation",
            manual_recommendation_id: meta.manual_recommendation_id || null,
          };
        if (isManual) {
          payload.origin_type = "manual_recommendation";
          payload.opportunity_context.source = "manual_recommendation";
          payload.opportunity_context.raw_notes = meta.raw_notes || payload.opportunity_context.raw_notes || "";
          payload.opportunity_context.manual_recommendation_id = meta.manual_recommendation_id || payload.opportunity_context.manual_recommendation_id || null;
        }
      }
      return payload;
    }

    async function generateDraft(candidate) {
      if (!candidate) return;
      const payload = buildGeneratePayload(candidate);
      latestDraftJob = null;
      selectedArticleJobId = "";
      activeDraftJobId = "";
      stopDraftPolling();
      renderDraft(currentStatus.summary || {});
      try {
        const started = await api("/generate-article/async", { method: "POST", body: JSON.stringify(payload) });
        activeDraftJobId = started.job_id;
        selectedArticleJobId = started.job_id;
        saveDraftState();
        await loadWorkspaceDraftJobs(currentStatus.workspace_id);
        renderDraft(currentStatus.summary || {});
        startDraftPolling();
      } catch (error) {
        activeDraftJobId = "";
        $("draft-result").innerHTML = `<div class="notice">${escapeHtml(error.message)}</div>`;
      }
    }

    function renderDraftJob(job) {
      const title = articleJobTitle(job);
      return `<article class="item selected-article-card">
        <p class="muted" style="font-size:.82rem;margin:0 0 4px">Selected Trendplot article</p>
        <strong>${escapeHtml(title)}</strong>
        <p>Trendplot status: ${escapeHtml(formatArticleJobStatus(effectiveArticleJobStatus(job)))} · Quality: ${escapeHtml((job.quality_check || job.final_quality_check || {}).status || "n/a")}</p>
        <p>Focus keyword: ${escapeHtml((job.structured_article || {}).focus_keyword || (job.structured_article || {}).target_keyword || "n/a")}</p>
        ${renderWordPressSendStatus(job)}
        ${renderJobSeoSection(job)}
        <div class="actions">
          <a class="pill" href="/jobs/${encodeURIComponent(job.job_id)}/preview" target="_blank" rel="noreferrer">Preview HTML</a>
          <a class="pill" href="/jobs/${encodeURIComponent(job.job_id)}" target="_blank" rel="noreferrer">Job JSON</a>
          ${renderSendToWordPressButton(job)}
        </div>
      </article>`;
    }

    document.querySelectorAll("[data-tab]").forEach(button => button.addEventListener("click", () => showTab(button.dataset.tab)));
    function showTab(tab) {
      document.querySelectorAll("[data-tab]").forEach(button => button.classList.toggle("active", button.dataset.tab === tab));
      ["summary", "recommendations", "schedule", "draft", "diagnostics"].forEach(name => {
        $(`tab-${name}`).hidden = name !== tab;
      });
    }

    function renderError(message) {
      $("overall").innerHTML = `<span class="dot failed"></span>Failed`;
      $("steps").innerHTML = `<div class="notice">${escapeHtml(message)}</div>`;
    }
  </script>
</body>
</html>
"""
