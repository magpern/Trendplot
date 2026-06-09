TRENDPLOT_WORKSPACE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trendplot Workspace</title>
  <style>
    :root { color-scheme: light dark; --bg: #0f172a; --panel: #111827; --soft: #1f2937; --text: #e5e7eb; --muted: #9ca3af; --brand: #38bdf8; --ok: #22c55e; --warn: #f59e0b; --danger: #ef4444; --border: #334155; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif; background: radial-gradient(circle at top left, #164e63 0, transparent 34rem), var(--bg); color: var(--text); }
    a { color: var(--brand); }
    .shell { width: min(1180px, 94vw); margin: 0 auto; padding: 32px 0 64px; }
    .hero { display: grid; gap: 12px; margin-bottom: 22px; }
    .hero h1 { font-size: clamp(2.4rem, 5vw, 4.5rem); margin: 0; letter-spacing: -0.06em; }
    .hero p { max-width: 760px; color: var(--muted); line-height: 1.6; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
    .card { border: 1px solid var(--border); background: color-mix(in srgb, var(--panel) 90%, transparent); border-radius: 18px; padding: 18px; box-shadow: 0 24px 60px rgba(0,0,0,0.18); }
    .card h2, .card h3 { margin: 0 0 12px; }
    label { display: block; color: var(--muted); margin: 12px 0 6px; }
    input, select, textarea, button { width: 100%; border-radius: 12px; border: 1px solid var(--border); padding: 11px 13px; font: inherit; }
    input, select, textarea { background: #020617; color: var(--text); }
    button { border: 0; background: linear-gradient(135deg, #0284c7, #2563eb); color: white; font-weight: 800; cursor: pointer; margin-top: 14px; }
    button.primary { background: linear-gradient(135deg, #0ea5e9, #2563eb); }
    button.secondary { background: var(--soft); border: 1px solid var(--border); }
    button:disabled { opacity: 0.6; cursor: wait; }
    .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .pill { display: inline-flex; gap: 7px; align-items: center; padding: 7px 10px; border-radius: 999px; border: 1px solid var(--border); background: rgba(2, 6, 23, .55); color: var(--muted); font-size: .9rem; }
    .dot { width: 9px; height: 9px; border-radius: 999px; background: var(--warn); }
    .dot.ok { background: var(--ok); }
    .dot.bad { background: var(--danger); }
    .muted { color: var(--muted); }
    .stack { display: grid; gap: 12px; }
    .small { font-size: .88rem; }
    .notice { border: 1px solid color-mix(in srgb, var(--warn) 42%, var(--border)); background: rgba(245, 158, 11, .12); border-radius: 14px; padding: 12px; color: #fcd34d; }
    .workspace-list button { text-align: left; background: var(--soft); border: 1px solid var(--border); }
    .calendar-item { display: grid; gap: 6px; padding: 12px; border-radius: 14px; border: 1px solid var(--border); background: rgba(2, 6, 23, .42); }
    .calendar-item strong { line-height: 1.3; }
    .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
    .actions button { margin: 0; padding: 9px; }
    .action-group { display: grid; gap: 10px; margin-top: 14px; }
    .action-group h3 { margin: 0; color: var(--muted); font-size: .92rem; text-transform: uppercase; letter-spacing: .08em; }
    .advanced-actions summary { cursor: pointer; color: var(--brand); font-weight: 800; }
    .inline-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .inline-actions button { width: auto; margin: 0; padding: 9px 12px; }
    .mini-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
    .status-card { border: 1px solid var(--border); background: rgba(2, 6, 23, .38); border-radius: 14px; padding: 12px; display: grid; gap: 6px; }
    .status-name { font-weight: 800; }
    .status-ok { color: var(--ok); }
    .status-warn { color: var(--warn); }
    .status-bad { color: var(--danger); }
    pre { white-space: pre-wrap; word-break: break-word; max-height: 280px; overflow: auto; background: #020617; border: 1px solid var(--border); padding: 12px; border-radius: 12px; }
    @media (max-width: 850px) { .grid, .actions { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="row">
        <span class="pill"><span class="dot ok"></span>Trendplot is running</span>
        <a class="pill" href="/">Operator UI</a>
        <a class="pill" href="/docs">API Docs</a>
      </div>
      <h1>Autonomous publishing intelligence.</h1>
      <p>Enter a website. Trendplot understands the business, finds opportunities, builds a publishing plan, and helps run content on autopilot while keeping the advanced engine behind the scenes.</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Create Trendplot Workspace</h2>
        <label>Website URL</label>
        <input id="website_url" placeholder="https://example.com">
        <label>Workspace name</label>
        <input id="workspace_name" placeholder="Example Brand">
        <label>Competitors (one per line, optional)</label>
        <textarea id="competitors" placeholder="https://competitor.com"></textarea>
        <label>Publishing mode</label>
        <select id="mode">
          <option value="manual_review">Manual review</option>
          <option value="auto_draft">Auto-draft</option>
          <option value="auto_publish">Auto-publish</option>
        </select>
        <label>Cadence</label>
        <select id="cadence">
          <option value="weekly">Weekly</option>
          <option value="daily">Daily</option>
          <option value="custom">Custom</option>
        </select>
        <button id="create-workspace">Create Workspace</button>
      </div>

      <div class="card">
        <h2>Workspaces</h2>
        <div id="workspace-list" class="workspace-list stack muted">Loading...</div>
      </div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2 id="workspace-title">Trendplot Workspace</h2>
      <div id="workspace-status" class="row muted"></div>
      <div class="action-group">
        <h3>Primary Actions</h3>
        <div class="actions">
          <button id="analyze-site" class="primary">Analyze Website</button>
          <button id="refresh-intelligence" class="primary">Refresh Intelligence</button>
          <button id="generate-plan" class="primary">Generate Plan</button>
        </div>
        <details class="advanced-actions">
          <summary>Advanced operator actions</summary>
          <div class="actions" style="margin-top: 10px">
            <button id="refresh-niche" class="secondary">Refresh Niche</button>
            <button id="discover-trends" class="secondary">Discover Trends</button>
            <button id="refresh-memory" class="secondary">Refresh Coverage</button>
            <button id="refresh-opportunities" class="secondary">Refresh Recommendations</button>
            <button id="reassess" class="secondary">Reassess Strategy</button>
            <button id="performance-refresh" class="secondary">Refresh Performance</button>
            <button id="connector-sync" class="secondary">Sync Connector Inventory</button>
          </div>
        </details>
      </div>
    </section>

    <section class="grid" style="margin-top: 16px">
      <div class="card">
        <h2>Provider Status</h2>
        <div id="provider-status-summary" class="stack muted">Select a workspace to inspect providers.</div>
      </div>
      <div class="card">
        <h2>Recent Operator Activity</h2>
        <div id="recent-activity" class="stack muted">Loading recent jobs and analyses...</div>
      </div>
    </section>

    <section class="grid" style="margin-top: 16px">
      <div class="card">
        <h2>Site Understanding</h2>
        <div id="site-understanding" class="stack muted">No workspace selected.</div>
      </div>
      <div class="card">
        <h2>Niche Intelligence</h2>
        <div id="niche-profile" class="stack muted">No niche profile yet.</div>
      </div>
    </section>

    <section class="grid" style="margin-top: 16px">
      <div class="card">
        <h2>Trend Insights</h2>
        <div id="trend-insights" class="stack muted">No trends yet.</div>
      </div>
      <div class="card">
        <h2>Signals</h2>
        <div id="signal-summary" class="stack muted">Signals will appear after analysis.</div>
      </div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2>Demand Observations</h2>
      <div class="inline-actions" style="margin-bottom: 12px">
        <button id="fetch-demand" class="secondary">Fetch Demand Observations</button>
        <button id="refresh-demand" class="secondary">Refresh Demand Insights</button>
      </div>
      <div id="demand-observations" class="stack muted">Select a workspace to inspect demand observations.</div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2>Opportunity Intelligence</h2>
      <div id="opportunity-intelligence" class="stack muted">Recommendations will appear after analysis.</div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2>Your Coverage</h2>
      <div id="coverage-summary" class="stack muted">Coverage memory will appear after analysis or connector inventory sync.</div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2>This Week's Publishing Plan</h2>
      <div id="generated-job-result" class="stack muted" style="margin-bottom: 12px"></div>
      <div id="calendar" class="stack muted">Generate a plan to see upcoming posts.</div>
    </section>

    <section class="card" style="margin-top: 16px">
      <h2>Performance Summary</h2>
      <div id="performance-summary" class="stack muted">Connect feedback providers to adapt future plans from real performance.</div>
    </section>
  </main>

  <script>
    let selectedWorkspaceId = "";
    let selectedWorkspaceData = null;

    const $ = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
    const formatJson = (value) => JSON.stringify(value ?? {}, null, 2);
    async function api(path, options = {}) {
      const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    async function loadWorkspaces() {
      const data = await api("/autopilot/workspaces");
      $("workspace-list").innerHTML = data.workspaces.length ? data.workspaces.map(workspace => `
        <button type="button" data-workspace="${escapeHtml(workspace.id)}">
          <strong>${escapeHtml(workspace.name)}</strong><br>
          <span class="muted">${escapeHtml(workspace.website_url)} · ${escapeHtml(workspace.status)} · ${escapeHtml(workspace.mode)}</span>
        </button>
      `).join("") : "No workspaces yet.";
      document.querySelectorAll("[data-workspace]").forEach(button => button.addEventListener("click", () => selectWorkspace(button.dataset.workspace)));
      if (!selectedWorkspaceId && data.workspaces[0]) await selectWorkspace(data.workspaces[0].id);
    }

    async function selectWorkspace(id) {
      selectedWorkspaceId = id;
      const data = await api(`/autopilot/workspaces/${encodeURIComponent(id)}`);
      selectedWorkspaceData = data;
      renderWorkspace(data);
      await Promise.allSettled([
        loadProviderDiagnostics(data),
        loadDemandDiagnostics(id),
        loadRecentActivity(),
        loadCalendarJobDiagnostics(data.calendar_items || []),
      ]);
    }

    function renderWorkspace(data) {
      const workspace = data.workspace || {};
      const summary = data.status_summary || {};
      $("workspace-title").textContent = workspace.name || "Trendplot Workspace";
      $("workspace-status").innerHTML = `
        <span class="pill"><span class="dot ${summary.autopilot === "on" ? "ok" : ""}"></span>Autopilot ${escapeHtml(summary.autopilot || "off")}</span>
        <span class="pill">Mode: ${escapeHtml(summary.mode || "manual_review")}</span>
        <span class="pill">${escapeHtml(summary.upcoming_posts || 0)} scheduled</span>
        <span class="pill">${escapeHtml(summary.needs_review || 0)} need review</span>
        <span class="pill">${escapeHtml(summary.trend_alerts || 0)} trend signals</span>
      `;
      renderProviderStatus(data.provider_status || [], null, null);
      renderDemandPanel(data, null);
      const understanding = data.site_understanding || {};
      $("site-understanding").innerHTML = understanding.id ? `
        <strong>${escapeHtml(understanding.detected_niche || "Generic niche")}</strong>
        <span>${escapeHtml(understanding.summary || "")}</span>
        <span>Products/services: ${escapeHtml((understanding.products_services || []).slice(0, 6).map(item => item.name || item.title || item).join(", ") || "n/a")}</span>
        <span>Audiences: ${escapeHtml((understanding.audiences || []).slice(0, 4).map(item => item.name || item).join(", ") || "n/a")}</span>
      ` : "Analyze the site to create a simple business understanding summary.";
      const profile = data.niche_profile || {};
      $("niche-profile").innerHTML = profile.id ? `
        <strong>${escapeHtml(profile.primary_niche || "Generic niche")}</strong>
        <span class="muted">Confidence ${escapeHtml(profile.confidence ?? "n/a")} · updated ${escapeHtml(profile.last_updated || "n/a")}</span>
        <span>Secondary niches: ${escapeHtml((profile.secondary_niches || []).slice(0, 6).join(", ") || "n/a")}</span>
        <span>Known entities: ${escapeHtml((profile.known_entities || []).slice(0, 10).join(", ") || "n/a")}</span>
        <span>Audiences: ${escapeHtml((profile.known_audiences || []).slice(0, 6).join(", ") || "n/a")}</span>
      ` : "Analyze the site or refresh the niche profile to persist stable business context between runs.";
      $("trend-insights").innerHTML = (data.trend_signals || []).length ? data.trend_signals.map(signal => `
        <div class="calendar-item">
          <strong>${escapeHtml(signal.trend_topic)}</strong>
          <span class="muted">${escapeHtml(signal.recommended_format || "trend_article")} · score ${escapeHtml(signal.opportunity_score ?? signal.confidence ?? "n/a")} · ${escapeHtml(signal.source_provider || "trendplot")}</span>
          <span>${escapeHtml(signal.why_it_matters || signal.recommended_angle || "")}</span>
        </div>
      `).join("") : "Trend signals will appear after analysis.";
      $("signal-summary").innerHTML = `
        <span>Trend queries: ${escapeHtml((data.trend_discovery_queries || []).length)}</span>
        <span>Trend signals: ${escapeHtml((data.trend_signals || []).length)}</span>
        <span>Coverage records: ${escapeHtml((data.coverage || []).length)}</span>
        <span>Demand observations: ${escapeHtml((data.demand_observations || []).length)}</span>
        <span>Recent analyses: ${escapeHtml((data.approval_events || []).filter(event => event.event_type === "workspace_analyzed").length)}</span>
      `;
      const intelligence = data.opportunity_intelligence || {};
      const groups = intelligence.groups || {};
      $("opportunity-intelligence").innerHTML = renderOpportunityGroup("Recommended Now", groups.recommended_now || [])
        + renderOpportunityGroup("Refresh Existing Content", groups.refresh_existing || [])
        + renderOpportunityGroup("Monitor", groups.monitor || [])
        + renderOpportunityGroup("Ignore", groups.ignore || [], true)
        || "Recommendations will appear after analysis.";
      const coverage = data.coverage || [];
      const gaps = coverage.filter(item => Number(item.gap_score || 0) >= 0.5).slice(0, 5);
      const refreshes = data.refresh_candidates || [];
      $("coverage-summary").innerHTML = coverage.length ? `
        <div class="row">
          <span class="pill">${escapeHtml(coverage.length)} coverage records</span>
          <span class="pill">${escapeHtml(gaps.length)} visible gaps</span>
          <span class="pill">${escapeHtml(refreshes.length)} refresh candidates</span>
        </div>
        ${[...gaps, ...refreshes.slice(0, 5)].slice(0, 8).map(item => `
          <div class="calendar-item">
            <strong>${escapeHtml(item.name)}</strong>
            <span class="muted">${escapeHtml(item.coverage_type)} · gap ${escapeHtml(item.gap_score ?? "n/a")} · refresh ${escapeHtml(item.refresh_score ?? "n/a")} · cannibalization ${escapeHtml(item.cannibalization_risk ?? "n/a")}</span>
            <span>${escapeHtml(item.refresh_reason || "Use this signal to decide whether to create, refresh, merge, or choose an alternate angle.")}</span>
          </div>
        `).join("")}
      ` : "Coverage memory will appear after analysis, generated plans, published content, or connector inventory sync.";
      $("calendar").innerHTML = (data.calendar_items || []).length ? data.calendar_items.map(item => `
        <div class="calendar-item">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.scheduled_for || "unscheduled")} · ${escapeHtml(item.state)} · ${escapeHtml(item.content_role || "content")}</span>
          <span class="muted">${escapeHtml(item.notes || "")}</span>
          ${item.generated_job_id ? `
            <div class="status-card">
              <span class="status-name">Generated job ${escapeHtml(item.generated_job_id)}</span>
              <span class="muted">Calendar state: ${escapeHtml(item.state)}</span>
              <span><a href="/jobs/${encodeURIComponent(item.generated_job_id)}" target="_blank" rel="noreferrer">Job JSON</a> · <a href="/jobs/${encodeURIComponent(item.generated_job_id)}/preview" target="_blank" rel="noreferrer">Local preview</a></span>
              <div id="job-summary-${escapeHtml(item.id)}" class="muted small">Loading job diagnostics...</div>
            </div>
          ` : ""}
          <div class="actions">
            <button class="secondary" data-approve="${escapeHtml(item.id)}">Approve</button>
            <button class="secondary" data-generate="${escapeHtml(item.id)}">Generate</button>
            <button class="secondary" data-skip="${escapeHtml(item.id)}">Skip</button>
          </div>
        </div>
      `).join("") : "Generate a publishing plan to see upcoming posts.";
      document.querySelectorAll("[data-approve]").forEach(button => button.addEventListener("click", () => updateItem(button.dataset.approve, { state: "approved" })));
      document.querySelectorAll("[data-skip]").forEach(button => button.addEventListener("click", () => updateItem(button.dataset.skip, { state: "skipped" })));
      document.querySelectorAll("[data-generate]").forEach(button => button.addEventListener("click", () => generateItem(button.dataset.generate)));
      $("performance-summary").innerHTML = `
        <span>${escapeHtml((data.reassessment || {}).summary || "No reassessment report yet.")}</span>
        <span>Published posts: ${escapeHtml((data.published_content || []).length)}</span>
        <span>Provider diagnostics are summarized in the Provider Status panel.</span>
      `;
    }

    async function loadProviderDiagnostics(data) {
      const [keysResult, demandResult] = await Promise.allSettled([
        api("/config/api-keys"),
        api("/developer/demand/providers"),
      ]);
      renderProviderStatus(
        data.provider_status || [],
        keysResult.status === "fulfilled" ? keysResult.value : null,
        demandResult.status === "fulfilled" ? demandResult.value : null,
      );
    }

    function renderProviderStatus(providerStatus, keyStatus, demandStatus) {
      const checks = (keyStatus && keyStatus.checks) || [];
      const providers = providerStatus || [];
      const demandProviders = (demandStatus && demandStatus.providers) || providers.filter(provider => provider.provider_type === "demand");
      const openAi = checks.find(check => String(check.name || "").toLowerCase().includes("openai"));
      const youtube = checks.find(check => String(check.name || "").toLowerCase().includes("youtube"));
      const wordpress = providers.find(provider => ["cms", "cms_connector"].includes(provider.provider_type) || String(provider.provider_name || "").includes("wordpress"));
      const connector = providers.find(provider => provider.provider_type === "cms_connector" || String(provider.provider_name || "").includes("connector"));
      const trends = providers.filter(provider => provider.provider_type === "trend");
      $("provider-status-summary").innerHTML = `
        <div class="mini-grid">
          ${renderStatusCard("OpenAI", openAi?.status || (openAi?.configured ? "configured" : "unknown"), openAi?.detail || "Used for AI analysis and content generation.")}
          ${renderStatusCard("WordPress", wordpress?.status || "not_configured", "Publishing provider and REST fallback status.")}
          ${renderStatusCard("Connector", connector?.status || "not_configured", "Trendplot Connector capability and inventory status.")}
          ${renderStatusCard("YouTube", youtube?.status || (youtube?.configured ? "configured" : "unknown"), youtube?.detail || "Optional video enrichment provider.")}
          ${renderStatusCard("Demand", summarizeStatuses(demandProviders), "Search Console and future demand providers.")}
          ${renderStatusCard("Trend", summarizeStatuses(trends), "Trend provider status from workspace intelligence.")}
        </div>
        <details>
          <summary>Developer diagnostics</summary>
          <pre>${escapeHtml(formatJson({ api_keys: keyStatus, provider_status: providers, demand_providers: demandProviders }))}</pre>
        </details>
      `;
    }

    function renderStatusCard(name, status, detail) {
      const className = statusClass(status);
      return `
        <div class="status-card">
          <span class="status-name">${escapeHtml(name)}</span>
          <span class="${className}">${escapeHtml(status || "unknown")}</span>
          <span class="muted small">${escapeHtml(detail || "")}</span>
        </div>
      `;
    }

    function summarizeStatuses(items) {
      if (!items || !items.length) return "not_configured";
      const statuses = items.map(item => item.status || "unknown");
      if (statuses.some(status => ["ok", "connected", "configured"].includes(status))) return "ok";
      if (statuses.some(status => status === "degraded")) return "degraded";
      if (statuses.some(status => status === "error" || status === "failed")) return "error";
      if (statuses.every(status => status === "not_configured" || status === "not_connected")) return "not_configured";
      return statuses[0] || "unknown";
    }

    function statusClass(status) {
      const clean = String(status || "").toLowerCase();
      if (["ok", "connected", "configured", "ready", "passed", "published_draft", "published_live", "ready_for_review"].includes(clean)) return "status-ok";
      if (["error", "failed", "failed_publish", "failed_quality"].includes(clean) || clean.includes("missing")) return "status-bad";
      return "status-warn";
    }

    async function loadDemandDiagnostics(workspaceId) {
      const [providersResult, insightsResult, runsResult] = await Promise.allSettled([
        api("/developer/demand/providers"),
        api(`/autopilot/workspaces/${encodeURIComponent(workspaceId)}/demand-insights`),
        api(`/developer/demand/workspaces/${encodeURIComponent(workspaceId)}/runs?limit=5`),
      ]);
      renderDemandPanel(selectedWorkspaceData || {}, {
        providers: providersResult.status === "fulfilled" ? providersResult.value.providers || [] : [],
        insights: insightsResult.status === "fulfilled" ? insightsResult.value : {},
        runs: runsResult.status === "fulfilled" ? runsResult.value.runs || [] : [],
      });
    }

    function renderDemandPanel(data, diagnostics) {
      const providers = diagnostics?.providers || (data.provider_status || []).filter(provider => provider.provider_type === "demand");
      const insights = diagnostics?.insights || {};
      const latestRun = insights.latest_run || data.demand_observation_run || (diagnostics?.runs || [])[0] || {};
      const topQueries = insights.top_queries || [];
      const topOpportunities = insights.top_opportunities || data.demand_observations || [];
      const lowCtrPages = insights.pages_with_low_ctr || [];
      const configured = providers.some(provider => ["ok", "configured", "connected"].includes(provider.status));
      const warnings = [
        ...((latestRun.warnings || []).map(warning => String(warning))),
        ...(latestRun.error_message ? [latestRun.error_message] : []),
        ...providers.filter(provider => provider.last_error).map(provider => provider.last_error),
      ];
      $("demand-observations").innerHTML = `
        <div class="row">
          ${(providers.length ? providers : [{ provider_name: "search_console", status: "not_configured" }]).map(provider => `
            <span class="pill"><span class="dot ${statusDot(provider.status)}"></span>${escapeHtml(provider.provider_name || "demand")} ${escapeHtml(provider.status || "unknown")}</span>
          `).join("")}
          <span class="pill">Rows fetched: ${escapeHtml(latestRun.rows_fetched ?? 0)}</span>
          <span class="pill">Rows persisted: ${escapeHtml(latestRun.rows_persisted ?? 0)}</span>
        </div>
        ${configured ? "" : `
          <div class="notice small">
            Search Console is not configured. Set <code>DEMAND_PROVIDER_SEARCH_CONSOLE_ENABLED=true</code>, <code>SEARCH_CONSOLE_SITE_URL</code>, and <code>SEARCH_CONSOLE_CREDENTIALS_JSON_PATH</code> to fetch real demand data.
          </div>
        `}
        ${latestRun.id ? `
          <div class="status-card">
            <span class="status-name">Latest demand fetch run</span>
            <span>${escapeHtml(latestRun.status)} · ${escapeHtml(latestRun.provider || "provider")} · ${escapeHtml(latestRun.date_start || "n/a")} to ${escapeHtml(latestRun.date_end || "n/a")}</span>
            <span class="muted small">Run ${escapeHtml(latestRun.id)}</span>
          </div>
        ` : ""}
        ${warnings.length ? `<div class="notice small">${warnings.map(escapeHtml).join("<br>")}</div>` : ""}
        ${renderDemandList("Top Queries By Impressions", topQueries, "impressions")}
        ${renderDemandList("Top Opportunity Observations", topOpportunities, "normalized_opportunity_score")}
        ${renderDemandList("Low CTR Pages", lowCtrPages, "ctr")}
        <details>
          <summary>Demand diagnostics</summary>
          <pre>${escapeHtml(formatJson({ providers, latest_run: latestRun, insights }))}</pre>
        </details>
      `;
    }

    function renderDemandList(title, items, metric) {
      if (!items || !items.length) return `<div><strong>${escapeHtml(title)}</strong><div class="muted small">No records yet.</div></div>`;
      return `
        <div>
          <h3>${escapeHtml(title)}</h3>
          <div class="stack">
            ${items.slice(0, 6).map(item => `
              <div class="calendar-item">
                <strong>${escapeHtml(item.query || item.topic || item.page_url || "Demand observation")}</strong>
                <span class="muted">Impressions ${escapeHtml(item.impressions ?? 0)} · Clicks ${escapeHtml(item.clicks ?? 0)} · CTR ${escapeHtml(formatPercent(item.ctr))} · Position ${escapeHtml(formatNumber(item.position))}</span>
                <span class="muted">${escapeHtml(metric)}: ${escapeHtml(formatNumber(item[metric]))}${item.page_url ? ` · ${escapeHtml(item.page_url)}` : ""}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }

    function statusDot(status) {
      const clean = String(status || "").toLowerCase();
      if (["ok", "configured", "connected", "completed"].includes(clean)) return "ok";
      if (["error", "failed"].includes(clean)) return "bad";
      return "";
    }

    async function updateItem(id, payload) {
      await api(`/autopilot/calendar-items/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) });
      await selectWorkspace(selectedWorkspaceId);
    }

    async function generateItem(id) {
      const result = await api(`/autopilot/calendar-items/${encodeURIComponent(id)}/generate`, { method: "POST", body: "{}" });
      renderGeneratedJobResult(result.article_job || result);
      await selectWorkspace(selectedWorkspaceId);
    }

    function renderGeneratedJobResult(job) {
      if (!job || !job.job_id) return;
      $("generated-job-result").innerHTML = `
        <div class="status-card">
          <strong>Latest generated article job</strong>
          <span>Job ${escapeHtml(job.job_id)} · ${escapeHtml(job.status || "unknown")}</span>
          <span class="muted small">Quality: ${escapeHtml(passLabel(job.quality_check || job.final_quality_check))} · Sanity: ${escapeHtml(passLabel(job.sanity_check))}</span>
          <span>
            <a href="/jobs/${encodeURIComponent(job.job_id)}" target="_blank" rel="noreferrer">Job JSON</a>
            · <a href="/jobs/${encodeURIComponent(job.job_id)}/preview" target="_blank" rel="noreferrer">Local preview</a>
            ${job.wordpress_post?.link ? ` · <a href="${escapeHtml(job.wordpress_post.link)}" target="_blank" rel="noreferrer">WordPress post</a>` : ""}
          </span>
          ${job.last_error ? `<span class="status-bad">${escapeHtml(job.last_error)}</span>` : ""}
        </div>
      `;
    }

    async function loadCalendarJobDiagnostics(items) {
      const generated = (items || []).filter(item => item.generated_job_id).slice(0, 8);
      await Promise.allSettled(generated.map(async item => {
        const detail = await api(`/jobs/${encodeURIComponent(item.generated_job_id)}`);
        const target = document.getElementById(`job-summary-${item.id}`);
        if (target) target.innerHTML = renderJobDetailSummary(detail);
      }));
    }

    function renderJobDetailSummary(detail) {
      const job = detail.job || {};
      const artifacts = detail.artifacts || [];
      const logs = detail.logs || [];
      const quality = artifactJson(artifacts, ["final_quality_check", "quality_check"]);
      const sanity = artifactJson(artifacts, ["sanity_check"]);
      const wordpress = artifactJson(artifacts, ["wordpress_post", "wordpress_publish_response"]);
      const errors = logs.filter(log => log.level === "error").slice(-2).map(log => log.message || log.error_message);
      return `
        <span>Status: <span class="${statusClass(job.status)}">${escapeHtml(job.status || "unknown")}</span></span>
        <span>Quality: ${escapeHtml(passLabel(quality))} · Sanity: ${escapeHtml(passLabel(sanity))}</span>
        ${wordpress?.link ? `<span><a href="${escapeHtml(wordpress.link)}" target="_blank" rel="noreferrer">WordPress post</a></span>` : ""}
        ${job.last_error ? `<span class="status-bad">${escapeHtml(job.last_error)}</span>` : ""}
        ${errors.length ? `<span class="status-bad">${escapeHtml(errors.join(" | "))}</span>` : ""}
      `;
    }

    async function loadRecentActivity() {
      const [jobsResult, analysesResult] = await Promise.allSettled([
        api("/jobs/recent?limit=6"),
        api("/analysis-jobs?limit=6"),
      ]);
      const jobs = jobsResult.status === "fulfilled" ? jobsResult.value : [];
      const analyses = analysesResult.status === "fulfilled" ? analysesResult.value : [];
      $("recent-activity").innerHTML = `
        <div>
          <h3>Recent Jobs</h3>
          ${jobs.length ? jobs.map(job => `
            <div class="calendar-item">
              <strong>${escapeHtml(job.request_input?.title || job.id)}</strong>
              <span class="muted">${escapeHtml(job.status)} · ${escapeHtml(job.created_at)}</span>
              <span><a href="/jobs/${encodeURIComponent(job.id)}" target="_blank" rel="noreferrer">Job JSON</a> · <a href="/jobs/${encodeURIComponent(job.id)}/preview" target="_blank" rel="noreferrer">Preview</a></span>
              ${job.last_error ? `<span class="status-bad">${escapeHtml(job.last_error)}</span>` : ""}
            </div>
          `).join("") : `<span class="muted small">No recent jobs.</span>`}
        </div>
        <div>
          <h3>Recent Analyses</h3>
          ${analyses.length ? analyses.map(job => `
            <div class="calendar-item">
              <strong>${escapeHtml(job.website_url || job.id)}</strong>
              <span class="muted">${escapeHtml(job.status)} · ${escapeHtml(job.created_at)}</span>
              <span><a href="/analysis-jobs/${encodeURIComponent(job.id)}" target="_blank" rel="noreferrer">Analysis JSON</a></span>
              ${job.error_message ? `<span class="status-bad">${escapeHtml(job.error_message)}</span>` : ""}
            </div>
          `).join("") : `<span class="muted small">No recent analyses.</span>`}
        </div>
      `;
    }

    function artifactJson(artifacts, types) {
      const found = artifacts.filter(artifact => types.includes(artifact.artifact_type)).slice(-1)[0];
      return found ? found.content_json : null;
    }

    function passLabel(report) {
      if (!report) return "n/a";
      if (report.passed === true) return "passed";
      if (report.passed === false) return "needs review";
      return report.status || "available";
    }

    function formatNumber(value) {
      if (value === null || value === undefined || value === "") return "n/a";
      const number = Number(value);
      return Number.isFinite(number) ? number.toFixed(number >= 10 ? 1 : 3).replace(/\\.0+$/, "") : String(value);
    }

    function formatPercent(value) {
      const number = Number(value);
      return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : "n/a";
    }

    function renderOpportunityGroup(title, items, collapsed = false) {
      if (!items.length) return "";
      const body = items.slice(0, 20).map(item => `
        <div class="calendar-item">
          <strong>${escapeHtml(item.title || item.topic)}</strong>
          <span class="muted">${escapeHtml(item.action)} · ${escapeHtml(item.priority)} · confidence ${escapeHtml(item.confidence ?? "n/a")} · score ${escapeHtml(item.score ?? "n/a")}</span>
          <span class="muted">Demand ${escapeHtml(item.demand_score ?? "n/a")} · ${escapeHtml(item.has_external_evidence ? "external evidence" : "internal evidence only")}</span>
          <span>${escapeHtml(item.explanation || (item.reasons || []).slice(0, 2).join(" "))}</span>
        </div>
      `).join("");
      if (collapsed) {
        return `<details><summary>${escapeHtml(title)} (${escapeHtml(items.length)})</summary><div class="stack" style="margin-top: 10px">${body}</div></details>`;
      }
      return `<h3>${escapeHtml(title)}</h3>${body}`;
    }

    $("create-workspace").addEventListener("click", async () => {
      const payload = {
        website_url: $("website_url").value,
        name: $("workspace_name").value,
        competitor_urls: $("competitors").value.split(/\\n+/).map(value => value.trim()).filter(Boolean),
        mode: $("mode").value,
        cadence: $("cadence").value
      };
      const data = await api("/autopilot/workspaces", { method: "POST", body: JSON.stringify(payload) });
      selectedWorkspaceId = data.workspace.id;
      await loadWorkspaces();
      await selectWorkspace(selectedWorkspaceId);
    });
    $("analyze-site").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/analyze`, { method: "POST", body: JSON.stringify({ max_pages_per_site: 30 }) });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("refresh-intelligence").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/niche-profile/refresh`, { method: "POST", body: "{}" });
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/discover-trends`, { method: "POST", body: "{}" });
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/publishing-memory/refresh`, { method: "POST", body: "{}" });
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/opportunity-intelligence/refresh`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("refresh-niche").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/niche-profile/refresh`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("discover-trends").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/discover-trends`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("refresh-memory").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/publishing-memory/refresh`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("refresh-opportunities").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/opportunity-intelligence/refresh`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("generate-plan").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/generate-plan`, { method: "POST", body: JSON.stringify({ horizon_days: 30 }) });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("reassess").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/reassess`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("performance-refresh").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/performance-refresh`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("connector-sync").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/autopilot/workspaces/${encodeURIComponent(selectedWorkspaceId)}/connector-sync`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("fetch-demand").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await api(`/developer/demand/workspaces/${encodeURIComponent(selectedWorkspaceId)}/fetch`, { method: "POST", body: "{}" });
      await selectWorkspace(selectedWorkspaceId);
    });
    $("refresh-demand").addEventListener("click", async () => {
      if (!selectedWorkspaceId) return;
      await loadDemandDiagnostics(selectedWorkspaceId);
    });

    loadWorkspaces().catch(error => { $("workspace-list").textContent = error.message; });
  </script>
</body>
</html>
"""
