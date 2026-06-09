# Deprecated legacy developer UI.
# app/trendplot_ui.py is the active Trendplot operator UI. A separate polished
# end-user UI may be introduced later, but this legacy dashboard should not be
# served from /developer or /admin.
DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trendplot Developer UI</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #0f172a;
      --panel: #111827;
      --panel-soft: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --brand: #38bdf8;
      --ok: #22c55e;
      --warn: #f59e0b;
      --danger: #ef4444;
      --border: #334155;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #1e3a8a 0, transparent 30rem), var(--bg);
      color: var(--text);
    }
    a { color: var(--brand); }
    .shell { width: min(80vw, 1680px); max-width: none; margin: 0 auto; padding: 32px 20px 56px; }
    .hero { display: grid; gap: 16px; margin-bottom: 24px; }
    .hero h1 { margin: 0; font-size: clamp(2rem, 4vw, 4rem); letter-spacing: -0.05em; }
    .hero p { color: var(--muted); max-width: 760px; font-size: 1.05rem; line-height: 1.6; }
    .grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; align-items: start; }
    .card {
      background: color-mix(in srgb, var(--panel) 92%, transparent);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
    }
    .card h2, .card h3 { margin: 0 0 14px; }
    label { display: block; margin: 14px 0 6px; color: var(--muted); font-size: 0.92rem; }
    input, select, textarea, button {
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--border);
      padding: 12px 14px;
      font: inherit;
    }
    input, select, textarea {
      background: #020617;
      color: var(--text);
    }
    button {
      margin-top: 18px;
      border: 0;
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: white;
      cursor: pointer;
      font-weight: 700;
    }
    button:disabled { opacity: 0.6; cursor: wait; }
    .quick-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .quick-actions button {
      margin: 0;
      background: var(--panel-soft);
      border: 1px solid var(--border);
      text-align: left;
      font-weight: 600;
    }
    .status-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 11px;
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--muted);
      background: rgba(15, 23, 42, 0.7);
      font-size: 0.9rem;
    }
    .dot { width: 9px; height: 9px; border-radius: 999px; background: var(--warn); }
    .dot.ok { background: var(--ok); }
    .dot.bad { background: var(--danger); }
    .guide { display: grid; gap: 12px; }
    .guide-item {
      padding: 14px;
      border-radius: 14px;
      background: rgba(31, 41, 55, 0.65);
      border: 1px solid var(--border);
    }
    .guide-item strong { display: block; margin-bottom: 5px; }
    .muted { color: var(--muted); }
    textarea { min-height: 110px; resize: vertical; }
    .result, .jobs { margin-top: 20px; }
    .analysis-card { margin-bottom: 20px; }
    .analysis-artifacts { margin-top: 10px; }
    .analysis-artifacts summary { cursor: pointer; color: var(--brand); }
    .analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .suggestions {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .suggestion {
      padding: 14px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(15, 23, 42, 0.65);
    }
    .suggestion h3 { margin: 0 0 8px; font-size: 1rem; }
    .suggestion input { margin-bottom: 8px; }
    .opportunity-workbench {
      display: block;
      margin-top: 18px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(15, 23, 42, 0.62);
      min-width: 0;
      overflow: hidden;
    }
    .opportunity-workbench.compact { font-size: 0.84rem; }
    .opportunity-workbench.comfortable { font-size: 0.92rem; }
    .opportunity-workbench.detailed { font-size: 0.96rem; }
    .workspace-header {
      display: grid;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid var(--border);
      background: rgba(2, 6, 23, 0.42);
    }
    .workspace-tabs,
    .workspace-stats,
    .workspace-filter-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .workspace-tab {
      width: auto;
      margin-top: 0;
      padding: 7px 10px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.9);
      color: var(--muted);
      font-size: 0.82rem;
    }
    .workspace-tab.active {
      color: white;
      border-color: rgba(56, 189, 248, 0.55);
      background: rgba(2, 132, 199, 0.45);
    }
    .stat-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 5px 8px;
      background: rgba(2, 6, 23, 0.55);
      color: var(--muted);
      font-size: 0.8rem;
      white-space: nowrap;
    }
    .stat-chip strong { color: var(--text); }
    .workspace-filter-panel {
      border-top: 1px solid rgba(51, 65, 85, 0.55);
      padding-top: 8px;
    }
    .workspace-filter-panel summary {
      cursor: pointer;
      color: var(--brand);
      font-weight: 700;
      list-style-position: inside;
    }
    .workspace-filter-grid {
      margin-top: 8px;
    }
    .workspace-filter-grid label {
      margin: 0;
      display: grid;
      gap: 3px;
      min-width: 130px;
    }
    .workspace-filter-grid select,
    .workspace-filter-grid input {
      width: 100%;
      padding: 7px 9px;
    }
    .cluster-filter-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      max-height: 86px;
      overflow: auto;
      margin-top: 8px;
    }
    .cluster-filter-strip label {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin: 0;
      padding: 5px 8px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(2, 6, 23, 0.45);
      cursor: pointer;
      font-size: 0.8rem;
    }
    .cluster-filter-strip input { width: auto; }
    .workbench-toolbar,
    .bulk-toolbar,
    .pagination-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px;
      align-items: center;
      border-bottom: 1px solid var(--border);
      background: rgba(2, 6, 23, 0.18);
    }
    .workbench-toolbar input,
    .workbench-toolbar select,
    .bulk-toolbar select,
    .pagination-row select {
      width: auto;
      min-width: 140px;
      padding: 8px 10px;
    }
    .workbench-toolbar input { flex: 1 1 240px; }
    .workbench-toolbar button,
    .bulk-toolbar button,
    .pagination-row button,
    .row-actions button {
      width: auto;
      margin-top: 0;
      padding: 8px 10px;
      border-radius: 10px;
      font-size: 0.82rem;
    }
    .opportunity-table-wrap {
      overflow: auto;
      max-height: 72vh;
    }
    .opportunity-table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1120px;
    }
    .opportunity-table th,
    .opportunity-table td {
      padding: 9px 10px;
      border-bottom: 1px solid rgba(51, 65, 85, 0.75);
      text-align: left;
      vertical-align: middle;
    }
    .opportunity-workbench.compact .opportunity-table th,
    .opportunity-workbench.compact .opportunity-table td { padding: 4px 7px; }
    .opportunity-workbench.comfortable .opportunity-table th,
    .opportunity-workbench.comfortable .opportunity-table td { padding: 8px 9px; }
    .opportunity-workbench.detailed .opportunity-table th,
    .opportunity-workbench.detailed .opportunity-table td { padding: 11px 10px; }
    .opportunity-workbench.compact .row-actions button {
      padding: 5px 7px;
      font-size: 0.76rem;
    }
    .opportunity-table th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #0b1220;
      color: var(--muted);
      font-size: 0.8rem;
      white-space: nowrap;
    }
    .opportunity-table th[data-sort] { cursor: pointer; }
    .opportunity-row { cursor: pointer; }
    .opportunity-row:hover,
    .opportunity-row.selected {
      background: rgba(56, 189, 248, 0.08);
    }
    .opportunity-row { position: relative; }
    .opportunity-title {
      min-width: 260px;
      max-width: 380px;
    }
    .opportunity-title strong {
      display: block;
      color: var(--text);
      line-height: 1.25;
    }
    .chip-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
    .mini-chip,
    .score-badge {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 7px;
      color: var(--muted);
      background: rgba(15, 23, 42, 0.9);
      font-size: 0.76rem;
      white-space: nowrap;
    }
    .score-badge.good { color: var(--ok); border-color: rgba(34, 197, 94, 0.45); }
    .score-badge.warn { color: var(--warn); border-color: rgba(245, 158, 11, 0.45); }
    .score-bar {
      display: grid;
      gap: 4px;
      min-width: 80px;
    }
    .score-bar-track {
      width: 100%;
      height: 6px;
      border-radius: 999px;
      background: rgba(51, 65, 85, 0.8);
      overflow: hidden;
    }
    .score-bar-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #0284c7, #22c55e);
    }
    .cluster-nav {
      display: grid;
      gap: 6px;
      margin-top: 10px;
      max-height: 300px;
      overflow: auto;
    }
    .cluster-nav label {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin: 0;
      padding: 8px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(2, 6, 23, 0.4);
      cursor: pointer;
    }
    .cluster-nav input { width: auto; }
    .drawer-section {
      border-top: 1px solid var(--border);
      margin-top: 10px;
      padding-top: 10px;
    }
    .drawer-section h4 { margin: 0 0 8px; }
    .drawer-list { margin: 0; padding-left: 18px; }
    .opportunity-hover-preview {
      display: none;
      position: fixed;
      z-index: 20;
      left: min(70vw, 1100px);
      right: 24px;
      top: 22vh;
      max-width: 420px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #020617;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
      pointer-events: none;
    }
    .opportunity-row:hover .opportunity-hover-preview { display: block; }
    .opportunity-inspector-backdrop {
      position: fixed;
      inset: 0;
      z-index: 30;
      background: rgba(2, 6, 23, 0.48);
      backdrop-filter: blur(2px);
    }
    .opportunity-inspector {
      position: fixed;
      z-index: 31;
      top: 0;
      right: 0;
      width: min(520px, 92vw);
      height: 100vh;
      overflow: auto;
      padding: 18px;
      border-left: 1px solid var(--border);
      background: #0b1220;
      box-shadow: -30px 0 80px rgba(0, 0, 0, 0.38);
    }
    .inspector-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 10px;
    }
    .inspector-header button {
      width: auto;
      margin-top: 0;
      padding: 7px 10px;
    }
    .workspace-placeholder {
      padding: 18px;
      border-top: 1px solid var(--border);
      background: rgba(2, 6, 23, 0.2);
    }
    .filter-row { display: grid; gap: 8px; margin-top: 10px; }
    .suggestion-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .suggestion-actions button { margin-top: 0; }
    .secondary-button {
      background: var(--panel-soft);
      border: 1px solid var(--border);
    }
    .danger-button { background: linear-gradient(135deg, #dc2626, #b91c1c); }
    .publish-controls {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .publish-controls strong,
    .publish-controls p {
      grid-column: 1 / -1;
    }
    pre {
      max-height: 420px;
      overflow: auto;
      padding: 14px;
      border-radius: 14px;
      background: #020617;
      border: 1px solid var(--border);
      white-space: pre-wrap;
    }
    .job, .analysis-job {
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      margin-top: 10px;
      background: rgba(15, 23, 42, 0.65);
      cursor: pointer;
    }
    .job:hover, .analysis-job:hover { border-color: var(--brand); }
    .job-title { display: flex; justify-content: space-between; gap: 12px; }
    .key-check {
      display: grid;
      gap: 10px;
      margin-top: 20px;
    }
    .key-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(15, 23, 42, 0.65);
    }
    .key-row strong { display: block; }
    .key-status {
      white-space: normal;
      max-width: 100%;
      min-width: 0;
    }
    .key-status.configured { color: var(--ok); }
    .key-status.missing, .key-status.placeholder { color: var(--warn); }
    .key-status, .muted, .small {
      overflow-wrap: anywhere;
      word-break: normal;
      line-height: 1.45;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .detail-panel {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: rgba(15, 23, 42, 0.65);
      min-width: 0;
      overflow: hidden;
      overflow-wrap: anywhere;
    }
    .detail-panel summary,
    .result-expander summary {
      cursor: pointer;
      font-weight: 800;
      font-size: 1.05rem;
      list-style-position: inside;
    }
    .detail-panel > *:not(summary),
    .result-expander > *:not(summary) {
      margin-top: 10px;
    }
    .result-expander {
      margin-top: 14px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: rgba(15, 23, 42, 0.65);
    }
    .rendered-preview {
      width: 100%;
      height: 720px;
      min-height: 420px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: white;
    }
    .small { font-size: 0.85rem; }
    @media (max-width: 860px) {
      .shell { width: 100%; }
      .grid { grid-template-columns: 1fr; }
      .analysis-grid { grid-template-columns: 1fr; }
      .workspace-tabs,
      .workspace-stats,
      .workbench-toolbar,
      .bulk-toolbar,
      .pagination-row { align-items: stretch; }
      .workbench-toolbar input { flex-basis: 100%; }
      .opportunity-table-wrap { max-height: none; }
      .opportunity-hover-preview { display: none !important; }
      .quick-actions { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="pill"><span class="dot ok"></span>Trendplot developer engine is running</div>
      <h1>Inspect publishing intelligence without leaving the browser.</h1>
      <p>Use this local dashboard to guide article generation, test different keywords, create social copy, review local previews, and publish to WordPress when ready.</p>
      <div class="status-row">
        <a class="pill" href="/health">Health</a>
        <a class="pill" href="/docs">API docs</a>
        <span class="pill">WordPress status: manual publish</span>
        <span class="pill">Review policy: manual by default</span>
      </div>
    </section>

    <section class="card">
      <h2>Unattended Mode</h2>
      <div id="unattended-status" class="muted">Loading unattended publish policy...</div>
    </section>

    <section class="card analysis-card">
      <h2>Analyze A Website First</h2>
      <p class="muted">Paste your website and optional competitors. The worker will fetch lightweight page signals and suggest keywords, article titles, product names, and URLs.</p>

      <form id="analysis-form">
        <div class="analysis-grid">
          <div>
            <label for="website_url">Your website</label>
            <input id="website_url" name="website_url" type="url" required placeholder="https://example.com">
          </div>
          <div>
            <label for="max_pages_per_site">Pages per site</label>
            <select id="max_pages_per_site" name="max_pages_per_site">
              <option value="1">1 page</option>
              <option value="2">2 pages</option>
              <option value="3">3 pages</option>
              <option value="4">4 pages</option>
              <option value="5">5 pages</option>
              <option value="10">10 pages</option>
              <option value="15">15 pages</option>
              <option value="25">25 pages</option>
              <option value="30" selected>30 pages</option>
            </select>
          </div>
          <div>
            <label for="vertical">Site vertical</label>
            <select id="vertical" name="vertical">
              <option value="auto" selected>Auto detect</option>
              <option value="generic">Generic</option>
              <option value="peptides">Peptides / research</option>
              <option value="shoes">Shoes</option>
              <option value="fashion">Fashion / bags</option>
              <option value="supplements">Supplements</option>
              <option value="software">Software / SaaS</option>
            </select>
          </div>
        </div>

        <label for="competitor_urls">Competitors, one URL per line</label>
        <textarea id="competitor_urls" name="competitor_urls" placeholder="https://competitor-one.com&#10;https://competitor-two.com"></textarea>

        <div class="suggestion-actions">
          <button id="analysis-button" type="submit">Analyze Website And Suggest Opportunities</button>
          <button id="stop-analysis-button" class="secondary-button" type="button" disabled>Stop Analysis</button>
        </div>
      </form>

      <div id="analysis-result" class="result" hidden>
        <h3>Intelligence Explorer</h3>
        <p id="analysis-summary" class="muted"></p>
        <div id="opportunity-explorer" class="opportunity-explorer"></div>
        <details class="analysis-artifacts">
          <summary>Legacy suggestion editor</summary>
          <p class="muted small">These suggestions are preserved for compatibility with the original workflow.</p>
          <div id="suggestions" class="suggestions"></div>
        </details>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Generate Article</h2>
        <p class="muted">Try different titles and target keywords. The worker generates, enriches, checks, and stores a local preview for review before WordPress publishing.</p>

        <div class="quick-actions">
          <button type="button" data-sample="running">Sample: running shoes</button>
          <button type="button" data-sample="coffee">Sample: coffee grinder</button>
        </div>

        <form id="generate-form">
          <label for="title">Article title</label>
          <input id="title" name="title" required placeholder="How to choose the best running shoes">

          <label for="target_keyword">Target keyword</label>
          <input id="target_keyword" name="target_keyword" required placeholder="best running shoes">

          <label for="product_name">Product name</label>
          <input id="product_name" name="product_name" required placeholder="Acme Runner Pro">

          <label for="product_url">Product URL</label>
          <input id="product_url" name="product_url" type="url" required placeholder="https://example.com/products/acme-runner-pro">

          <label for="publish_policy">Publish policy</label>
          <select id="publish_policy" name="publish_policy">
            <option value="manual_review" selected>Manual review, no WordPress publish</option>
            <option value="draft_after_review">Draft after review</option>
            <option value="live_after_review">Live after review</option>
            <option value="auto_draft">Auto publish draft after quality pass</option>
            <option value="auto_live">Auto publish live if explicitly enabled</option>
          </select>

          <label>
            <input id="unattended_mode" name="unattended_mode" type="checkbox" value="true">
            Request unattended mode for this generation
          </label>

          <label for="category_id">WordPress category</label>
          <select id="category_id" name="category_id">
            <option value="">No category selected</option>
          </select>

          <label for="wordpress_template">WordPress template/layout</label>
          <select id="wordpress_template" name="wordpress_template">
            <option value="elementor_header_footer" selected>Elementor Full Width</option>
            <option value="">Default theme template</option>
          </select>

          <label for="wordpress_tags">WordPress tags</label>
          <input id="wordpress_tags" name="wordpress_tags" placeholder="research, glossary, comparisons">

          <label for="featured_image_url">Featured image URL (optional)</label>
          <input id="featured_image_url" name="featured_image_url" type="url" placeholder="Leave blank unless a real image is available">

          <label for="featured_image_id">Featured image media ID (optional)</label>
          <input id="featured_image_id" name="featured_image_id" type="number" placeholder="Existing WordPress media ID">

          <label for="featured_image_alt">Featured image alt text</label>
          <input id="featured_image_alt" name="featured_image_alt" placeholder="Short descriptive alt text">

          <button id="submit-button" type="submit">Generate Article</button>
        </form>

        <div class="result card" id="result-card" hidden>
          <h3>Latest Result</h3>
          <div id="result-summary" class="muted"></div>
          <div id="result-details"></div>
          <pre id="result-output"></pre>
        </div>
      </div>

      <aside class="card">
        <h2>Guide</h2>
        <div class="guide">
          <div class="guide-item">
            <strong>1. Configure credentials</strong>
            <span class="muted">Set OpenAI, WordPress, and YouTube values in <code>.env</code>.</span>
          </div>
          <div class="guide-item">
            <strong>2. Choose a keyword</strong>
            <span class="muted">Start specific. Product-led keywords are easiest to review.</span>
          </div>
          <div class="guide-item">
            <strong>3. Review before publishing</strong>
            <span class="muted">Use the local preview first, then publish a WordPress draft or live post explicitly.</span>
          </div>
        </div>

        <div class="jobs">
          <h3>Recent Analyses</h3>
          <div id="analysis-jobs-list" class="muted">Loading recent analyses...</div>
        </div>

        <div class="jobs">
          <h3>Recent Jobs</h3>
          <div id="jobs-list" class="muted">Loading recent jobs...</div>
        </div>

        <div class="key-check">
          <h3>API Keys</h3>
          <p class="muted small">Checks what the running app has loaded. Restart after changing <code>.env</code>.</p>
          <button id="check-api-keys-button" type="button">Check API keys</button>
          <div id="api-key-checks" class="muted">Not checked yet.</div>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const samples = {
      running: {
        title: "How to Choose the Best Running Shoes for Daily Training",
        target_keyword: "best running shoes for daily training",
        product_name: "Acme Runner Pro",
        product_url: "https://example.com/products/acme-runner-pro"
      },
      coffee: {
        title: "How to Pick a Coffee Grinder for Better Espresso at Home",
        target_keyword: "best coffee grinder for espresso",
        product_name: "BrewMaster Precision Grinder",
        product_url: "https://example.com/products/brewmaster-precision-grinder"
      }
    };

    function setFormValues(values) {
      for (const [key, value] of Object.entries(values)) {
        document.getElementById(key).value = value;
      }
    }

    function formatJson(value) {
      return JSON.stringify(value, null, 2);
    }

    function generationSummary(data) {
      const quality = data.quality_check || {};
      const sanity = data.sanity_check || {};
      const status = data.status || "unknown";
      const errors = quality.errors || [];
      const warnings = quality.warnings || [];
      const sanityErrors = sanity.blocking_errors || [];
      const wordpress = data.wordpress_post?.link
        ? ` <a href="${escapeHtml(data.wordpress_post.link)}" target="_blank" rel="noreferrer">Open WordPress post</a>`
        : "";
      const preview = data.job_id
        ? ` <a href="/jobs/${escapeHtml(data.job_id)}/preview" target="_blank" rel="noreferrer">Open local preview</a>`
        : "";
      const warningText = warnings.length ? ` Warnings: ${escapeHtml(warnings.join(" | "))}` : "";
      const errorText = errors.length ? ` Errors: ${escapeHtml(errors.join(" | "))}` : "";
      const sanityText = sanityErrors.length ? ` Sanity blocked: ${escapeHtml(sanityErrors.map(item => item.message || item.code).join(" | "))}` : "";
      return `Status: ${escapeHtml(status)}. Policy: ${escapeHtml(data.publish_policy || "manual_review")}. Quality: ${quality.passed ? "passed" : "needs review"}. Sanity: ${sanity.passed ? "passed" : "needs review"}. Word count: ${quality.word_count ?? "n/a"}.${warningText}${errorText}${sanityText}${preview}${wordpress}`;
    }

    function renderGenerationDetails(data) {
      const container = document.getElementById("result-details");
      const quality = data.final_quality_check || data.quality_check || {};
      const sanity = data.sanity_check || {};
      const sanityRewrite = data.sanity_rewrite_summary || {};
      const initialQuality = data.initial_quality_check || null;
      const repairSummary = data.repair_summary || {};
      const expansionSummary = data.section_expansion_summary || {};
      const backlinkPlan = data.backlink_plan || [];
      const references = data.suggested_external_references || [];
      const rendererLogs = data.renderer_logs || [];
      const modelPipeline = data.model_pipeline || [];
      const promptArtifacts = data.prompt_artifacts || [];
      const structuredArticle = data.structured_article || null;
      const renderedHtml = data.rendered_html || "";
      const previewUrl = data.job_id ? `/jobs/${encodeURIComponent(data.job_id)}/preview` : "";
      const editorialPreviewUrl = data.job_id ? `/jobs/${encodeURIComponent(data.job_id)}/preview?surface=editorial` : "";
      const canPublish = Boolean(data.job_id && quality.passed && sanity.passed);
      const canRunSanity = Boolean(data.job_id && !sanity.passed);
      const presentation = data.wordpress_presentation_metadata || {};
      const publishDecision = data.publish_decision_report || {};
      const redundancy = data.redundancy_review || {};
      const redundancyCleanup = data.redundancy_cleanup_summary || {};
      const internalLinkPlan = data.internal_link_plan || {};
      const studyCards = data.study_cards || [];
      const researchMetadata = data.research_metadata_panel || {};
      const schemaJsonld = data.schema_jsonld || {};
      const jobRunMetrics = data.job_run_metrics || {};
      const stageTiming = data.stage_timing_summary || {};
      const modelCost = data.model_cost_summary || {};
      const aiPatternReport = data.ai_pattern_report || {};
      const humanizationSummary = data.humanization_summary || {};
      const humanizationQuality = data.humanization_quality_report || {};
      const rewrittenSections = data.rewritten_sections?.sections || [];
      const revertedSections = data.reverted_sections?.sections || [];
      const rewriteAttempts = data.rewrite_attempts?.attempts || [];
      const repeatedPhrasesRemoved = data.repeated_phrases_removed?.phrases || humanizationSummary.repeated_phrases_removed || [];
      const postHumanizationRedundancy = data.post_humanization_redundancy_review || {};
      const narrativePatternReport = data.narrative_pattern_report || {};
      const narrativeSummary = data.narrative_editor_summary || {};
      const narrativeEdits = data.narrative_editor_edits || {};
      const narrativeApplied = narrativeEdits.applied || [];
      const narrativeSkipped = narrativeEdits.skipped || [];
      const postNarrativeRedundancy = data.post_narrative_redundancy_review || {};
      const imageResult = data.image_generation_result || {};
      const imagePlacementPlan = data.image_placement_plan || imageResult.placement_plan || {};
      const imageImages = imageResult.images || [];
      const featuredGeneratedImage = imageImages.find(image => image.type === "featured") || imageImages[0] || {};
      const inlinePlacements = imagePlacementPlan.inline_images || [];
      const tagSuggestions = data.wordpress_tag_suggestions || presentation.wordpress_tags || [];
      const selectedTemplate = presentation.wordpress_template || "elementor_header_footer";
      const selectedCategory = presentation.wordpress_category_id || "";
      const featuredStatus = presentation.featured_image_id
        ? `media ID ${presentation.featured_image_id}`
        : presentation.featured_image_url
          ? "URL available"
          : "none";

      container.innerHTML = `
        ${data.job_id ? `
          <div class="detail-panel publish-controls">
            <strong>Job Actions</strong>
            <p class="muted small">Create a fresh job from the saved request input. The original job and artifacts are kept.</p>
            <button type="button" data-rerun-action="run" data-job-id="${escapeHtml(data.job_id)}">Rerun Job</button>
          </div>
        ` : ""}
        ${canPublish ? `
          <div class="detail-panel publish-controls">
            <strong>Publish Controls</strong>
            <p class="muted small">Publish only after you have reviewed the local preview.</p>
            <label class="small" for="publish_wordpress_template">Template</label>
            <select id="publish_wordpress_template">${templateOptions(selectedTemplate)}</select>
            <label class="small" for="publish_category_id">Category</label>
            <select id="publish_category_id">${categoryOptions(selectedCategory)}</select>
            <label class="small" for="publish_wordpress_tags">Tags</label>
            <input id="publish_wordpress_tags" value="${escapeHtml(tagSuggestions.join(", "))}" placeholder="tag one, tag two">
            <label class="small" for="publish_featured_image_id">Featured image media ID</label>
            <input id="publish_featured_image_id" type="number" value="${escapeHtml(presentation.featured_image_id || "")}" placeholder="Optional">
            <label class="small" for="publish_featured_image_url">Featured image URL</label>
            <input id="publish_featured_image_url" type="url" value="${escapeHtml(presentation.featured_image_url || "")}" placeholder="Optional real image URL">
            <label class="small" for="publish_featured_image_alt">Featured image alt</label>
            <input id="publish_featured_image_alt" value="${escapeHtml(presentation.featured_image_alt || "")}" placeholder="Optional alt text">
            <p class="muted small">Featured image status: ${escapeHtml(featuredStatus)}. No placeholder image will be used.</p>
            <button type="button" data-publish-action="draft" data-job-id="${escapeHtml(data.job_id)}">Create WordPress Draft</button>
          </div>
        ` : ""}
        <div class="detail-grid">
          <details class="detail-panel" open>
            <summary>Run Metrics</summary>
            <div class="muted small">Runtime: ${escapeHtml(jobRunMetrics.total_runtime_seconds ?? "n/a")} seconds</div>
            <div class="muted small">Estimated cost: ${escapeHtml(modelCost.total_estimated_cost ?? jobRunMetrics.total_estimated_cost ?? "n/a")}</div>
            <div class="muted small">Tokens: ${escapeHtml(modelCost.token_input ?? jobRunMetrics.token_input ?? "n/a")} in / ${escapeHtml(modelCost.token_output ?? jobRunMetrics.token_output ?? "n/a")} out</div>
            <div class="muted small">Repair passes: ${escapeHtml(jobRunMetrics.repair_pass_count ?? "n/a")}</div>
            <div class="muted small">Expansion passes: ${escapeHtml(jobRunMetrics.expansion_pass_count ?? "n/a")}</div>
            <div class="muted small">Final quality: ${escapeHtml(jobRunMetrics.final_quality_status || "n/a")}</div>
            <div class="muted small">Final sanity: ${escapeHtml(jobRunMetrics.final_sanity_status || "n/a")}</div>
            ${(stageTiming.slowest_stages || []).map(stage => `<div class="small">Slow stage: ${escapeHtml(stage.stage)} (${escapeHtml(stage.runtime_seconds)}s)</div>`).join("")}
          </details>
          <details class="detail-panel" open>
            <summary>Editorial Humanization</summary>
            <div class="muted small">AI pattern score: ${escapeHtml(aiPatternReport.score ?? humanizationQuality.ai_pattern_score_before ?? "n/a")} (${escapeHtml(aiPatternReport.severity || "n/a")})</div>
            <div class="muted small">Rewrite mode: ${escapeHtml(humanizationSummary.rewrite_strength_used || humanizationSummary.rewrite_strength_requested || data.rewrite_strength_used?.value || "n/a")}</div>
            <div class="muted small">Sections rewritten: ${escapeHtml(humanizationSummary.sections_rewritten ?? rewrittenSections.length ?? "0")}</div>
            <div class="muted small">Sections reverted: ${escapeHtml(humanizationSummary.sections_reverted ?? revertedSections.length ?? "0")}</div>
            <div class="muted small">Repeated phrases removed: ${escapeHtml(repeatedPhrasesRemoved.length ? repeatedPhrasesRemoved.join(" | ") : "none")}</div>
            <div class="muted small">Before/after score: ${escapeHtml(humanizationQuality.ai_pattern_score_before ?? "n/a")} -> ${escapeHtml(humanizationQuality.ai_pattern_score_after ?? "n/a")}</div>
            <div class="muted small">Remaining warnings: ${escapeHtml((humanizationQuality.remaining_ai_pattern_warnings || aiPatternReport.warnings || []).join(" | ") || "none")}</div>
            <details class="analysis-artifacts"><summary>AI Pattern Report</summary><pre>${escapeHtml(formatJson(aiPatternReport || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Rewritten Sections</summary><pre>${escapeHtml(formatJson(data.rewritten_sections || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Reverted Sections</summary><pre>${escapeHtml(formatJson(data.reverted_sections || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Rewrite Attempts</summary><pre>${escapeHtml(formatJson(data.rewrite_attempts || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Humanization Quality Report</summary><pre>${escapeHtml(formatJson(humanizationQuality || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Post-Humanization Redundancy</summary><pre>${escapeHtml(formatJson(postHumanizationRedundancy || {}))}</pre></details>
          </details>
          <details class="detail-panel" open>
            <summary>Narrative Editor</summary>
            <div class="muted small">Pattern score: ${escapeHtml(narrativePatternReport.score ?? narrativeSummary.pattern_score_before ?? "n/a")} (${escapeHtml(narrativePatternReport.severity || "n/a")})</div>
            <div class="muted small">Before/after score: ${escapeHtml(narrativeSummary.pattern_score_before ?? "n/a")} -> ${escapeHtml(narrativeSummary.pattern_score_after ?? "n/a")}</div>
            <div class="muted small">Edits applied: ${escapeHtml(narrativeSummary.edits_applied ?? narrativeApplied.length ?? "0")}</div>
            <div class="muted small">Edits skipped: ${escapeHtml(narrativeSummary.edits_skipped ?? narrativeSkipped.length ?? "0")}</div>
            <div class="muted small">Remaining warnings: ${escapeHtml((narrativeSummary.remaining_warnings || narrativePatternReport.warnings || []).join(" | ") || "none")}</div>
            <details class="analysis-artifacts"><summary>Narrative Pattern Report</summary><pre>${escapeHtml(formatJson(narrativePatternReport || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Narrative Edits Applied</summary><pre>${escapeHtml(formatJson(narrativeApplied || []))}</pre></details>
            <details class="analysis-artifacts"><summary>Narrative Edits Skipped</summary><pre>${escapeHtml(formatJson(narrativeSkipped || []))}</pre></details>
            <details class="analysis-artifacts"><summary>Post-Narrative Redundancy</summary><pre>${escapeHtml(formatJson(postNarrativeRedundancy || {}))}</pre></details>
          </details>
          <details class="detail-panel">
            <summary>Media</summary>
            <div class="muted small">AI image generation: ${escapeHtml(imageResult.enabled ? "enabled" : "disabled")}</div>
            <div class="muted small">Active vertical: ${escapeHtml(imagePlacementPlan.active_vertical || imagePlacementPlan.detected_vertical || "generic")}</div>
            <div class="muted small">Image rules source: ${escapeHtml(imagePlacementPlan.image_rules_source || "generic")}</div>
            <div class="muted small">Status: ${escapeHtml(imageResult.status || "not available")}</div>
            <div class="muted small">Image approval: document-level review only</div>
            <div class="muted small">Recommended placements: featured ${escapeHtml(imagePlacementPlan.featured_image?.recommended ? "yes" : "no")} | inline ${escapeHtml(inlinePlacements.length)}</div>
            ${featuredGeneratedImage.url ? `<img class="rendered-preview" style="max-height: 220px" src="${escapeHtml(featuredGeneratedImage.url)}" alt="${escapeHtml(featuredGeneratedImage.alt_text || "")}">` : ""}
            ${featuredGeneratedImage.local_path ? `<div class="muted small">Local image: ${escapeHtml(featuredGeneratedImage.local_path)}</div>` : ""}
            <div class="muted small">Alt text: ${escapeHtml(data.image_alt_text || featuredGeneratedImage.alt_text || "none")}</div>
            <div class="muted small">Caption: ${escapeHtml(data.image_caption || featuredGeneratedImage.caption || "none")}</div>
            <div class="muted small">Safety notes: ${escapeHtml(data.image_safety_notes || imageResult.safety?.rules?.join(" | ") || "none")}</div>
            <div class="muted small">Generated images are inserted into the article when they pass image safety. Approve or reject the whole document before publishing.</div>
            <details class="analysis-artifacts"><summary>Image Placement Plan</summary><pre>${escapeHtml(formatJson(imagePlacementPlan || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Generated Images</summary><pre>${escapeHtml(formatJson(data.generated_images || imageResult || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Renderable Images</summary><pre>${escapeHtml(formatJson(data.approved_images || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Rejected Images</summary><pre>${escapeHtml(formatJson(data.rejected_images || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Image Rendering Summary</summary><pre>${escapeHtml(formatJson(data.image_rendering_summary || {}))}</pre></details>
            <details class="analysis-artifacts"><summary>Image Prompt</summary><pre>${escapeHtml(formatJson(data.image_prompt || {}))}</pre></details>
          </details>
          <details class="detail-panel">
            <summary>Final Quality Gate</summary>
            <div class="muted small">Status: ${escapeHtml(quality.status || data.status || "unknown")}</div>
            <div class="muted small">Word count: ${escapeHtml(quality.word_count ?? "n/a")}</div>
            ${(quality.errors || []).map(error => `<div class="key-status missing small">Error: ${escapeHtml(error)}</div>`).join("")}
            ${(quality.warnings || []).map(warning => `<div class="key-status placeholder small">Warning: ${escapeHtml(warning)}</div>`).join("")}
            ${!quality.passed ? '<div class="key-status missing small">Publishing blocked until review passes.</div>' : ""}
          </details>
          <details class="detail-panel" open>
            <summary>Sanity Check</summary>
            <div class="muted small">Status: ${escapeHtml(sanity.status || "not available")}</div>
            ${(sanity.blocking_errors || []).map(error => `
              <div class="key-status missing small">
                Blocking: ${escapeHtml(error.message || error.code)}<br>
                Matched: ${escapeHtml(error.matched_text || "")}<br>
                Location: ${escapeHtml(error.location || "")}<br>
                ${error.suggested_replacement ? `Suggested: ${escapeHtml(error.suggested_replacement)}` : ""}
              </div>
            `).join("")}
            ${(sanity.warnings || []).map(warning => `
              <div class="key-status placeholder small">
                Warning: ${escapeHtml(warning.message || warning.code)}<br>
                Location: ${escapeHtml(warning.location || "")}
              </div>
            `).join("")}
            ${sanityRewrite.attempted ? `
              <p class="muted small">Rewrite applied: ${escapeHtml((sanityRewrite.changed_locations || []).join(", ") || "none")}</p>
              <p class="muted small">${escapeHtml(sanityRewrite.reason || "")}</p>
            ` : ""}
            ${!sanity.passed ? '<div class="key-status missing small">Publishing blocked until the domain sanity check passes.</div>' : ""}
            ${canRunSanity ? `<button type="button" data-sanity-action="run" data-job-id="${escapeHtml(data.job_id)}">Run Sanity Check</button>` : ""}
          </details>
          <details class="detail-panel">
            <summary>Repair</summary>
            <div class="muted small">Attempted: ${escapeHtml(data.repair_attempted ? "yes" : "no")}</div>
            <div class="muted small">Passes: ${escapeHtml(data.repair_pass_count ?? repairSummary.pass_count ?? 0)}</div>
            ${repairSummary.word_count_before || repairSummary.word_count_after ? `<div class="muted small">Words: ${escapeHtml(repairSummary.word_count_before ?? "n/a")} -> ${escapeHtml(repairSummary.word_count_after ?? "n/a")}</div>` : ""}
            ${(repairSummary.repaired_fields || []).map(field => `<div class="muted small">Field: ${escapeHtml(field)}</div>`).join("")}
            ${(repairSummary.repaired_sections || []).map(section => `<div class="muted small">Section: ${escapeHtml(section)}</div>`).join("")}
            ${(repairSummary.remaining_errors || []).map(error => `<div class="key-status missing small">Remaining: ${escapeHtml(error)}</div>`).join("")}
            ${repairSummary.notes ? `<p class="muted small">${escapeHtml(repairSummary.notes)}</p>` : ""}
          </details>
          <details class="detail-panel">
            <summary>Initial Quality</summary>
            ${initialQuality ? `
              <div class="muted small">Status: ${escapeHtml(initialQuality.status || "unknown")}</div>
              <div class="muted small">Word count: ${escapeHtml(initialQuality.word_count ?? "n/a")}</div>
              ${(initialQuality.errors || []).map(error => `<div class="key-status missing small">Error: ${escapeHtml(error)}</div>`).join("")}
              ${(initialQuality.warnings || []).map(warning => `<div class="key-status placeholder small">Warning: ${escapeHtml(warning)}</div>`).join("")}
            ` : '<p class="muted small">Initial quality result not available.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Section Expansion</summary>
            <div class="muted small">Attempted: ${escapeHtml(data.section_expansion_attempted ? "yes" : "no")}</div>
            <div class="muted small">Passes: ${escapeHtml(expansionSummary.pass_count ?? 0)}</div>
            <div class="muted small">Words: ${escapeHtml(expansionSummary.word_count_before ?? "n/a")} -> ${escapeHtml(expansionSummary.word_count_after ?? "n/a")}</div>
            <div class="muted small">Remaining deficit: ${escapeHtml(expansionSummary.remaining_deficit ?? "n/a")}</div>
            ${(expansionSummary.expanded_sections || []).map(section => `
              <p class="small"><strong>${escapeHtml(section.heading || "Section")}</strong><br>
              ${escapeHtml(section.word_count_before ?? "n/a")} -> ${escapeHtml(section.word_count_after ?? "n/a")} words</p>
            `).join("")}
            ${expansionSummary.stopped_reason ? `<p class="muted small">${escapeHtml(expansionSummary.stopped_reason)}</p>` : ""}
          </details>
          <details class="detail-panel">
            <summary>Redundancy Review</summary>
            <div class="muted small">Duplicate headings: ${escapeHtml((redundancy.duplicate_headings || []).join(", ") || "none")}</div>
            <div class="muted small">Overlapping sections: ${escapeHtml((redundancy.overlapping_sections || []).length || 0)}</div>
            <div class="muted small">Repeated phrases: ${escapeHtml((redundancy.repeated_phrases || []).length || 0)}</div>
            <p class="muted small">${escapeHtml(redundancyCleanup.reason || "No cleanup summary available.")}</p>
          </details>
          <details class="detail-panel">
            <summary>Internal Link Plan</summary>
            <pre>${escapeHtml(formatJson(internalLinkPlan))}</pre>
          </details>
          <details class="detail-panel">
            <summary>Research Metadata</summary>
            <pre>${escapeHtml(formatJson(researchMetadata))}</pre>
          </details>
          <details class="detail-panel">
            <summary>Study Cards</summary>
            ${studyCards.length ? studyCards.map(card => `
              <p class="small"><strong>${escapeHtml(card.title || "Study card")}</strong><br>
              ${escapeHtml(card.source_label || "reference to verify")}<br>
              Finding: ${escapeHtml(card.observed_finding || "")}<br>
              Limitation: ${escapeHtml(card.limitation || "")}</p>
            `).join("") : '<p class="muted small">No study cards returned.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Schema JSON-LD</summary>
            <pre>${escapeHtml(formatJson(schemaJsonld))}</pre>
          </details>
          <details class="detail-panel">
            <summary>Publish Decisions</summary>
            ${publishDecision.template ? `
              <p class="small"><strong>Template</strong><br>${escapeHtml(publishDecision.template.selected_value || "")}<br>Source: ${escapeHtml(publishDecision.template.decision_source || "")}<br>${escapeHtml(publishDecision.template.reason || "")}</p>
              <p class="small"><strong>Category</strong><br>${escapeHtml(publishDecision.category?.selected_value?.name || publishDecision.category?.selected_value?.id || "none")}<br>Source: ${escapeHtml(publishDecision.category?.decision_source || "")}<br>${escapeHtml(publishDecision.category?.reason || "")}</p>
              <p class="small"><strong>Tags</strong><br>${escapeHtml((publishDecision.tags?.selected_value || []).join(", ") || "none")}<br>Source: ${escapeHtml(publishDecision.tags?.decision_source || "")}<br>${escapeHtml(publishDecision.tags?.reason || "")}</p>
              <p class="small"><strong>Featured image</strong><br>${escapeHtml(publishDecision.featured_image?.selected_value?.url || publishDecision.featured_image?.selected_value?.id || "none")}<br>Source: ${escapeHtml(publishDecision.featured_image?.decision_source || "")}<br>${escapeHtml(publishDecision.featured_image?.reason || "")}</p>
              <p class="small"><strong>Publish</strong><br>${escapeHtml(publishDecision.publish?.selected_value || "none")}<br>Source: ${escapeHtml(publishDecision.publish?.decision_source || "")}<br>${escapeHtml(publishDecision.publish?.reason || "")}</p>
            ` : '<p class="muted small">No publish decision report yet.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Backlink Plan</summary>
            ${backlinkPlan.length ? backlinkPlan.map(item => `
              <p class="small"><strong>${escapeHtml(item.target_type || "Opportunity")}</strong><br>
              ${escapeHtml(item.angle || "")}<br>
              Anchor: ${escapeHtml(item.suggested_anchor || "")}</p>
            `).join("") : '<p class="muted small">No backlink recommendations returned.</p>'}
          </details>
          <details class="detail-panel">
            <summary>References To Verify</summary>
            ${references.length ? references.map(item => `
              <p class="small"><strong>${escapeHtml(item.title || "Reference")}</strong><br>
              ${escapeHtml(item.search_query || "")}<br>
              ${escapeHtml(item.reason || "")}</p>
            `).join("") : '<p class="muted small">No reference suggestions returned.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Renderer Logs</summary>
            ${rendererLogs.length ? rendererLogs.map(log => `<div class="muted small">${escapeHtml(log)}</div>`).join("") : '<p class="muted small">No renderer warnings.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Model Pipeline</summary>
            ${modelPipeline.length ? modelPipeline.map(step => `
              <p class="small"><strong>${escapeHtml(step.task_type || step.artifact_type || "task")}</strong><br>
              Model: ${escapeHtml(step.model || "n/a")}<br>
              Prompt: ${escapeHtml(step.prompt_id || "n/a")} v${escapeHtml(step.prompt_version ?? "n/a")}<br>
              Tokens: ${escapeHtml(step.token_input ?? "n/a")} in / ${escapeHtml(step.token_output ?? "n/a")} out<br>
              Cost: ${escapeHtml(step.estimated_cost ?? "n/a")}</p>
            `).join("") : '<p class="muted small">No model usage artifacts yet.</p>'}
          </details>
          <details class="detail-panel">
            <summary>Prompt Templates</summary>
            ${promptArtifacts.length ? promptArtifacts.map(prompt => `
              <details class="analysis-artifacts">
                <summary>${escapeHtml(prompt.prompt_id || prompt.artifact_type || "prompt")} v${escapeHtml(prompt.prompt_version ?? "n/a")} (${escapeHtml(prompt.model_task || prompt.task_type || "task")})</summary>
                <pre>${escapeHtml(prompt.rendered_prompt || "")}</pre>
              </details>
            `).join("") : '<p class="muted small">No prompt metadata artifacts yet.</p>'}
          </details>
        </div>
        ${previewUrl ? `<details class="result-expander" open><summary>Public preview (publishable)</summary><p class="muted small">Reader-facing HTML — matches WordPress publish. <a href="${escapeHtml(previewUrl)}" target="_blank" rel="noreferrer">Open public preview</a>${editorialPreviewUrl ? ` · <a href="${escapeHtml(editorialPreviewUrl)}" target="_blank" rel="noreferrer">Open editorial/full preview</a>` : ""}</p><iframe class="rendered-preview" src="${escapeHtml(previewUrl)}" title="Public article preview"></iframe></details>` : renderedHtml ? `<details class="result-expander"><summary>Rendered Preview</summary><iframe class="rendered-preview" srcdoc="${escapeHtml(renderedHtml)}"></iframe></details>` : ""}
        ${structuredArticle ? `<details class="result-expander"><summary>Structured Article</summary><pre>${escapeHtml(formatJson(structuredArticle))}</pre></details>` : ""}
      `;
    }

    function artifactByType(detail, artifactType) {
      const matches = (detail.artifacts || []).filter(artifact => artifact.artifact_type === artifactType);
      return matches[matches.length - 1];
    }

    function generationDataFromJobDetail(detail) {
      const quality = artifactByType(detail, "final_quality_check_results") || artifactByType(detail, "quality_check_results") || artifactByType(detail, "quality_check");
      const initialQuality = artifactByType(detail, "initial_quality_check_results");
      const sanity = artifactByType(detail, "sanity_check_results");
      const sanityRewrite = artifactByType(detail, "sanity_rewrite_summary");
      const repairSummary = artifactByType(detail, "article_repair_summary");
      const expansionSummary = artifactByType(detail, "section_expansion_summary");
      const rendered = artifactByType(detail, "publishable_html") || artifactByType(detail, "rendered_html") || artifactByType(detail, "article_html");
      const editorialRendered = artifactByType(detail, "article_html_editorial");
      const structured = artifactByType(detail, "structured_article_json") || artifactByType(detail, "structured_article");
      const backlinks = artifactByType(detail, "backlink_plan");
      const references = artifactByType(detail, "references_to_verify") || artifactByType(detail, "suggested_external_references");
      const rendererLogs = artifactByType(detail, "renderer_logs");
      const wordpressPost = artifactByType(detail, "wordpress_post") || artifactByType(detail, "wordpress_publish_response");
      const presentation = artifactByType(detail, "wordpress_presentation_metadata");
      const tagSuggestions = artifactByType(detail, "wordpress_tag_suggestions");
      const publishDecision = artifactByType(detail, "publish_decision_report");
      const redundancy = artifactByType(detail, "redundancy_review_results");
      const redundancyCleanup = artifactByType(detail, "redundancy_cleanup_summary");
      const postHumanizationRedundancy = artifactByType(detail, "post_humanization_redundancy_review");
      const aiPatternReport = artifactByType(detail, "ai_pattern_report");
      const humanizationSummary = artifactByType(detail, "humanization_summary");
      const rewrittenSections = artifactByType(detail, "rewritten_sections");
      const rewriteAttempts = artifactByType(detail, "rewrite_attempts");
      const rewriteStrengthUsed = artifactByType(detail, "rewrite_strength_used");
      const humanizationQuality = artifactByType(detail, "humanization_quality_report");
      const repeatedPhrasesRemoved = artifactByType(detail, "repeated_phrases_removed");
      const sectionsRewritten = artifactByType(detail, "sections_rewritten");
      const revertedSections = artifactByType(detail, "reverted_sections");
      const narrativePatternReport = artifactByType(detail, "narrative_pattern_report");
      const narrativeSummary = artifactByType(detail, "narrative_editor_summary");
      const narrativeEdits = artifactByType(detail, "narrative_editor_edits");
      const postNarrativeRedundancy = artifactByType(detail, "post_narrative_redundancy_review");
      const internalLinkPlan = artifactByType(detail, "internal_link_plan");
      const studyCards = artifactByType(detail, "study_cards");
      const researchMetadata = artifactByType(detail, "research_metadata_panel");
      const richComponents = artifactByType(detail, "rich_components_json");
      const schemaJsonld = artifactByType(detail, "schema_jsonld");
      const jobRunMetrics = artifactByType(detail, "job_run_metrics");
      const stageTiming = artifactByType(detail, "stage_timing_summary");
      const modelCost = artifactByType(detail, "model_cost_summary");
      const imagePlacementPlan = artifactByType(detail, "image_placement_plan");
      const imagePrompt = artifactByType(detail, "image_prompt");
      const imageResult = artifactByType(detail, "image_generation_result");
      const generatedImages = artifactByType(detail, "generated_images");
      const approvedImages = artifactByType(detail, "approved_images");
      const rejectedImages = artifactByType(detail, "rejected_images");
      const imageRenderingSummary = artifactByType(detail, "image_rendering_summary");
      const imageAlt = artifactByType(detail, "image_alt_text");
      const imageCaption = artifactByType(detail, "image_caption");
      const imageSafety = artifactByType(detail, "image_safety_notes");
      const imageReview = artifactByType(detail, "image_review_decision");
      const modelPipeline = modelPipelineFromArtifacts(detail.artifacts || []);
      const promptArtifacts = promptArtifactsFromArtifacts(detail.artifacts || []);
      return {
        job_id: detail.job?.id,
        status: detail.job?.status,
        publish_policy: detail.job?.request_input?.publish_policy,
        wordpress_post: wordpressPost?.content_json,
        quality_check: quality?.content_json,
        initial_quality_check: initialQuality?.content_json,
        final_quality_check: quality?.content_json,
        sanity_check: sanity?.content_json,
        sanity_rewrite_summary: sanityRewrite?.content_json || {},
        repair_attempted: Boolean(repairSummary?.content_json?.attempted),
        repair_pass_count: repairSummary?.content_json?.pass_count || 0,
        repair_summary: repairSummary?.content_json || {},
        section_expansion_attempted: Boolean(expansionSummary?.content_json?.attempted),
        section_expansion_summary: expansionSummary?.content_json || {},
        rendered_html: rendered?.content_text,
        article_html_editorial: editorialRendered?.content_text,
        structured_article: structured?.content_json,
        backlink_plan: backlinks?.content_json?.plan || [],
        suggested_external_references: references?.content_json?.references || [],
        wordpress_presentation_metadata: presentation?.content_json || {},
        wordpress_tag_suggestions: tagSuggestions?.content_json?.tags || presentation?.content_json?.wordpress_tags || [],
        publish_decision_report: publishDecision?.content_json,
        redundancy_review: redundancy?.content_json,
        redundancy_cleanup_summary: redundancyCleanup?.content_json,
        post_humanization_redundancy_review: postHumanizationRedundancy?.content_json,
        ai_pattern_report: aiPatternReport?.content_json,
        humanization_summary: humanizationSummary?.content_json,
        rewritten_sections: rewrittenSections?.content_json,
        rewrite_attempts: rewriteAttempts?.content_json,
        rewrite_strength_used: rewriteStrengthUsed?.content_json,
        humanization_quality_report: humanizationQuality?.content_json,
        repeated_phrases_removed: repeatedPhrasesRemoved?.content_json,
        sections_rewritten: sectionsRewritten?.content_json,
        reverted_sections: revertedSections?.content_json,
        narrative_pattern_report: narrativePatternReport?.content_json,
        narrative_editor_summary: narrativeSummary?.content_json,
        narrative_editor_edits: narrativeEdits?.content_json,
        post_narrative_redundancy_review: postNarrativeRedundancy?.content_json,
        internal_link_plan: internalLinkPlan?.content_json,
        study_cards: studyCards?.content_json?.study_cards || [],
        research_metadata_panel: researchMetadata?.content_json || {},
        rich_components_json: richComponents?.content_json || {},
        schema_jsonld: schemaJsonld?.content_json,
        job_run_metrics: jobRunMetrics?.content_json,
        stage_timing_summary: stageTiming?.content_json,
        model_cost_summary: modelCost?.content_json,
        image_placement_plan: imagePlacementPlan?.content_json,
        image_prompt: imagePrompt?.content_json,
        image_generation_result: imageResult?.content_json,
        generated_images: generatedImages?.content_json,
        approved_images: approvedImages?.content_json,
        rejected_images: rejectedImages?.content_json,
        image_rendering_summary: imageRenderingSummary?.content_json,
        image_alt_text: imageAlt?.content_text,
        image_caption: imageCaption?.content_text,
        image_safety_notes: imageSafety?.content_text,
        image_review_decision: imageReview?.content_json,
        renderer_logs: rendererLogs?.content_json?.logs || [],
        model_pipeline: modelPipeline,
        prompt_artifacts: promptArtifacts
      };
    }

    function modelPipelineFromArtifacts(artifacts) {
      return artifacts
        .filter(artifact => artifact.model || artifact.token_input || artifact.token_output || artifact.estimated_cost || artifact.content_json?.task_type)
        .map(artifact => ({
          artifact_type: artifact.artifact_type,
          task_type: artifact.content_json?.task_type || "",
          prompt_id: artifact.content_json?.prompt_id || artifact.content_json?.prompt_metadata?.prompt_id || "",
          prompt_version: artifact.content_json?.prompt_version || artifact.content_json?.prompt_metadata?.prompt_version || "",
          model: artifact.model || artifact.content_json?.model || "",
          token_input: artifact.token_input ?? artifact.content_json?.usage?.token_input,
          token_output: artifact.token_output ?? artifact.content_json?.usage?.token_output,
          estimated_cost: artifact.estimated_cost ?? artifact.content_json?.usage?.estimated_cost
        }));
    }

    function promptArtifactsFromArtifacts(artifacts) {
      return artifacts
        .filter(artifact => artifact.content_json?.prompt_id || artifact.artifact_type?.includes("prompt"))
        .map(artifact => ({
          artifact_type: artifact.artifact_type,
          prompt_id: artifact.content_json?.prompt_id || "",
          prompt_version: artifact.content_json?.prompt_version || "",
          model_task: artifact.content_json?.model_task || "",
          task_type: artifact.content_json?.task_type || "",
          rendered_prompt: artifact.content_text || ""
        }));
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    let wordpressCategories = [];
    let wordpressTemplates = [
      { key: "elementor_header_footer", label: "Elementor Full Width", default: true },
      { key: "", label: "Default theme template" }
    ];

    function templateOptions(selectedValue) {
      return wordpressTemplates.map(template => {
        const key = template.key ?? "";
        const selected = key === (selectedValue ?? "") ? " selected" : "";
        const label = template.label || key || "Default";
        return `<option value="${escapeHtml(key)}"${selected}>${escapeHtml(label)}</option>`;
      }).join("");
    }

    function categoryOptions(selectedValue) {
      const selected = String(selectedValue || "");
      return '<option value="">No category selected</option>' + wordpressCategories.map(category => {
        const value = String(category.id || "");
        return `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(category.name || category.slug || value)}</option>`;
      }).join("");
    }

    function tagsFromInput(value) {
      return String(value || "").split(",").map(tag => tag.trim()).filter(Boolean).slice(0, 8);
    }

    async function loadJobs() {
      const list = document.getElementById("jobs-list");
      try {
        const response = await fetch("/jobs/recent");
        const jobs = await response.json();
        if (!jobs.length) {
          list.textContent = "No jobs yet. Generate your first draft.";
          return;
        }
        list.innerHTML = jobs.map(job => `
          <div class="job" data-job-id="${escapeHtml(job.id)}">
            <div class="job-title">
              <strong>${escapeHtml(job.request_input.title)}</strong>
              <span class="pill small">${escapeHtml(job.status)}</span>
            </div>
            <div class="muted small">${escapeHtml(job.request_input.target_keyword)}</div>
            <div class="muted small">${escapeHtml(job.created_at)}</div>
          </div>
        `).join("");
      } catch (error) {
        list.textContent = "Could not load recent jobs.";
      }
    }

    async function loadWordPressCategories() {
      const select = document.getElementById("category_id");
      try {
        const response = await fetch("/wordpress/categories");
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not load categories.");
        }
        const categories = data.categories || [];
        wordpressCategories = categories;
        select.innerHTML = '<option value="">No category selected</option>' + categories.map(category =>
          `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name || category.slug || category.id)}</option>`
        ).join("");
      } catch (error) {
        select.innerHTML = '<option value="">Categories unavailable</option>';
      }
    }

    async function loadWordPressTemplates() {
      const select = document.getElementById("wordpress_template");
      try {
        const response = await fetch("/wordpress/templates");
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not load templates.");
        }
        wordpressTemplates = data.templates?.length ? data.templates : wordpressTemplates;
        const defaultTemplate = wordpressTemplates.find(template => template.default)?.key ?? "elementor_header_footer";
        select.innerHTML = templateOptions(defaultTemplate);
      } catch (error) {
        select.innerHTML = templateOptions("elementor_header_footer");
      }
    }

    async function loadUnattendedStatus() {
      const container = document.getElementById("unattended-status");
      try {
        const response = await fetch("/config/unattended-status");
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not load unattended status.");
        }
        const last = data.last_decision_report;
        container.innerHTML = `
          <div class="muted small">Enabled: ${escapeHtml(data.enabled ? "yes" : "no")}</div>
          <div class="muted small">Default policy: ${escapeHtml(data.default_publish_policy || "manual_review")}</div>
          <div class="muted small">Auto-live allowed: ${escapeHtml(data.auto_live_allowed ? "yes" : "no")}</div>
          <div class="muted small">Default template: ${escapeHtml(data.default_template || "default")}</div>
          <div class="muted small">Default category: ${escapeHtml(data.default_category_id || data.default_category_slug || "none")}</div>
          <div class="muted small">Default tags: ${escapeHtml(data.default_tags || "none")}</div>
          ${last ? `<details class="analysis-artifacts"><summary>Last decision report</summary><pre>${escapeHtml(formatJson(last))}</pre></details>` : '<div class="muted small">No publish decision report yet.</div>'}
        `;
      } catch (error) {
        container.textContent = "Could not load unattended status.";
      }
    }

    async function showJob(jobId) {
      const response = await fetch(`/jobs/${jobId}`);
      const detail = await response.json();
      document.getElementById("result-card").hidden = false;
      document.getElementById("result-summary").textContent = `Loaded job ${jobId}`;
      renderGenerationDetails(generationDataFromJobDetail(detail));
      document.getElementById("result-output").textContent = formatJson(detail);
    }

    function renderOpportunityExplorer(detail) {
      const container = document.getElementById("opportunity-explorer");
      latestOpportunities = detail.opportunities || latestOpportunities || [];
      latestClusters = detail.clusters || latestClusters || [];
      latestAudiences = detail.audiences || latestAudiences || [];
      latestAuthorityGraph = detail.authority_graph || latestAuthorityGraph || {};
      opportunityWorkbenchState.selectedIds = new Set(
        [...opportunityWorkbenchState.selectedIds].filter(id => latestOpportunities.some(item => item.id === id))
      );

      if (!latestOpportunities.length) {
        container.innerHTML = '<div class="muted">No opportunity records are stored yet.</div>';
        return;
      }

      const summary = opportunitySummary(latestOpportunities);
      const clusterNav = clusterNavigationHtml(latestOpportunities, latestClusters);
      const audienceOptions = ['<option value="">All audiences</option>']
        .concat(latestAudiences.map(audience => `<option value="${escapeHtml(audience.id)}">${escapeHtml(audience.name)}</option>`))
        .join("");
      const workspaceTabs = ["Opportunities", "Clusters", "Audiences", "Authority Graph", "Campaigns", "Queue"]
        .map(tab => `<button type="button" class="workspace-tab ${opportunityWorkbenchState.activeTab === tab ? "active" : ""}" data-workspace-tab="${escapeHtml(tab)}">${escapeHtml(tab)}</button>`)
        .join("");
      const savedViewOptions = [
        ["all", "All Opportunities"],
        ["high-authority", "High Authority"],
        ["quick-wins", "Quick Wins"],
        ["competitor-gaps", "Competitor Gaps"],
        ["low-competition", "Low Competition"],
        ["geo", "GEO Opportunities"],
        ["research-authority", "Research Authority"],
        ["commercial-support", "Commercial Support"]
      ].map(([value, label]) => `<option value="${value}" ${opportunityWorkbenchState.savedView === value ? "selected" : ""}>${label}</option>`).join("");

      container.innerHTML = `
        <div class="opportunity-workbench ${escapeHtml(opportunityWorkbenchState.density)}">
          <header class="workspace-header">
            <div class="workspace-tabs">${workspaceTabs}</div>
            <div class="workspace-stats">
              ${summaryMetric("opportunities", summary.total)}
              ${summaryMetric("clusters", summary.clusters)}
              ${summaryMetric("audiences", summary.audiences)}
              ${summaryMetric("pillars", summary.pillars)}
              ${summaryMetric("support", summary.support)}
              ${summaryMetric("competitor gaps", summary.competitorGaps)}
              ${summaryMetric("GEO", summary.geo)}
              ${summaryMetric("avg authority", scoreLabel(summary.avgAuthority))}
              ${summaryMetric("avg novelty", scoreLabel(summary.avgNovelty))}
            </div>
            <details id="workspace-filter-panel" class="workspace-filter-panel">
              <summary>Filters, saved views, and cluster navigation</summary>
              <div class="workspace-filter-grid">
                <label>Saved view
                  <select id="opportunity-saved-view">${savedViewOptions}</select>
                </label>
                <label>Audience
                  <select id="opportunity-audience-filter">${audienceOptions}</select>
                </label>
                <label>Type
                  <select id="opportunity-type-filter">
                    <option value="">All types</option>
                    <option value="pillar_page">Pillar page</option>
                    <option value="semantic_support_article">Support article</option>
                    <option value="comparison_article">Comparison</option>
                    <option value="question_article">Question</option>
                    <option value="competitor_gap_article">Competitor gap</option>
                    <option value="buyer_guide">Buyer guide</option>
                  </select>
                </label>
                <label>Intent
                  <select id="opportunity-intent-filter">
                    <option value="">All intents</option>
                    <option value="informational">Informational</option>
                    <option value="commercial">Commercial</option>
                    <option value="comparison">Comparison</option>
                    <option value="transactional">Transactional</option>
                  </select>
                </label>
                <label>Role
                  <select id="opportunity-role-filter">
                    <option value="">All roles</option>
                    <option value="pillar_page">Pillar</option>
                    <option value="supporting_article">Support</option>
                    <option value="cluster_support">Cluster support</option>
                  </select>
                </label>
                <label>Status
                  <select id="opportunity-status-filter">
                    <option value="">All statuses</option>
                    <option value="suggested">Suggested</option>
                    <option value="approved">Approved</option>
                    <option value="planned">Queued</option>
                    <option value="generated">Generated</option>
                    <option value="rejected">Rejected</option>
                    <option value="bookmarked">Bookmarked</option>
                  </select>
                </label>
                <label>Min authority
                  <select id="opportunity-authority-filter">
                    <option value="">Any</option>
                    <option value="0.5">50+</option>
                    <option value="0.7">70+</option>
                    <option value="0.85">85+</option>
                  </select>
                </label>
                <label>Min GEO
                  <select id="opportunity-geo-filter">
                    <option value="">Any</option>
                    <option value="0.5">50+</option>
                    <option value="0.7">70+</option>
                    <option value="0.85">85+</option>
                  </select>
                </label>
                <label>Min novelty
                  <select id="opportunity-novelty-filter">
                    <option value="">Any</option>
                    <option value="0.5">50+</option>
                    <option value="0.7">70+</option>
                    <option value="0.85">85+</option>
                  </select>
                </label>
              </div>
              <div id="cluster-nav" class="cluster-filter-strip">${clusterNav}</div>
            </details>
          </header>

          <section id="workspace-opportunities-view" class="opportunity-main">
            <div class="workbench-toolbar">
              <input id="opportunity-search" type="search" placeholder="Search title, keyword, cluster, audience, entities..." value="${escapeHtml(opportunityWorkbenchState.search)}">
              <button id="opportunity-density-toggle" type="button" class="secondary-button">Density: ${escapeHtml(labelize(opportunityWorkbenchState.density))}</button>
              <button id="opportunity-clear-filters" type="button" class="secondary-button">Clear filters</button>
            </div>
            <div class="bulk-toolbar">
              <label class="muted small"><input id="opportunity-select-page" type="checkbox"> Select page</label>
              <span id="bulk-selection-count" class="muted small">0 selected</span>
              <button type="button" class="secondary-button" data-bulk-action="approved">Bulk approve</button>
              <button type="button" class="secondary-button" data-bulk-action="rejected">Bulk reject</button>
              <button type="button" class="secondary-button" data-bulk-action="planned">Bulk queue</button>
            </div>
            <div class="opportunity-table-wrap">
              <table class="opportunity-table">
                <thead>
                  <tr>
                    <th></th>
                    <th data-sort="title">Title</th>
                    <th data-sort="cluster">Cluster</th>
                    <th data-sort="audience">Audience</th>
                    <th data-sort="opportunity_type">Type</th>
                    <th data-sort="search_intent">Intent</th>
                    <th data-sort="confidence">Conf.</th>
                    <th data-sort="authority">Authority</th>
                    <th data-sort="geo">GEO</th>
                    <th data-sort="novelty">Novelty</th>
                    <th data-sort="saturation">Saturation</th>
                    <th data-sort="editorial_effort">Effort</th>
                    <th data-sort="status">Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody id="opportunity-table-body"></tbody>
              </table>
            </div>
            <div class="pagination-row">
              <button id="opportunity-prev-page" type="button" class="secondary-button">Previous</button>
              <span id="opportunity-page-status" class="muted small"></span>
              <button id="opportunity-next-page" type="button" class="secondary-button">Next</button>
              <select id="opportunity-page-size">
                <option value="25">25 rows</option>
                <option value="50">50 rows</option>
                <option value="100">100 rows</option>
              </select>
            </div>
          </section>
          <section id="workspace-secondary-view" class="workspace-placeholder" hidden></section>
          <div id="opportunity-detail"></div>
        </div>
      `;

      restoreWorkbenchControls();
      bindWorkbenchControls();
      renderWorkspaceTab();
      renderOpportunityRows();
    }

    function renderOpportunityDetail(opportunity) {
      const detail = document.getElementById("opportunity-detail");
      if (!detail || !opportunity) {
        return;
      }
      opportunityWorkbenchState.activeId = opportunity.id;
      const cluster = clusterForOpportunity(opportunity);
      const audience = audienceForOpportunity(opportunity);
      const relationships = opportunityRelationships(opportunity);
      detail.innerHTML = `
        <div class="opportunity-inspector-backdrop" data-inspector-close="true"></div>
        <aside class="opportunity-inspector" role="dialog" aria-label="Opportunity inspector">
          <div class="inspector-header">
            <div>
              <strong>${escapeHtml(opportunity.title)}</strong>
              <div class="muted small">Keyword: ${escapeHtml(opportunity.target_keyword || "n/a")}</div>
            </div>
            <button type="button" class="secondary-button" data-inspector-close="true">Close</button>
          </div>
          <div class="muted small">Cluster: ${escapeHtml(cluster.name || "Unclustered")}</div>
          <div class="muted small">Audience: ${escapeHtml(audience.name || "General")}</div>
          <div class="muted small">Product URL: ${opportunity.product_url ? `<a href="${escapeHtml(opportunity.product_url)}" target="_blank" rel="noreferrer">${escapeHtml(opportunity.product_url)}</a>` : "n/a"}</div>
          <div class="drawer-section">
            <h4>Scoring</h4>
            ${scoreBreakdownHtml(opportunity)}
          </div>
          <div class="drawer-section">
            <h4>Rationale</h4>
            <p class="muted small">${escapeHtml(opportunity.rationale || "No rationale provided.")}</p>
            <p class="muted small">${escapeHtml(opportunity.audience_rationale || "")}</p>
          </div>
          <div class="drawer-section">
            <h4>Evidence</h4>
            <p class="muted small">Source: ${escapeHtml(opportunity.source_type || "inferred")} | Needs verification: ${escapeHtml(opportunity.needs_verification === false ? "no" : "yes")}</p>
            <p class="muted small">${escapeHtml(opportunity.evidence_summary || "No evidence summary stored.")}</p>
          </div>
          <div class="drawer-section">
            <h4>Relationships</h4>
            <p class="muted small">${escapeHtml(relationships.length ? `${relationships.length} semantic relationship(s) exposed.` : "No stored relationships yet.")}</p>
            <ul class="drawer-list small">${relationships.map(item => `<li>${escapeHtml(item.relationship_type || "related")} ${escapeHtml(item.parent_id === opportunity.id ? "to child" : "to parent")}: ${escapeHtml(item.parent_id === opportunity.id ? item.child_id : item.parent_id)}</li>`).join("")}</ul>
          </div>
          ${drawerList("Related entities", opportunity.related_entities)}
          ${drawerList("Related products", opportunity.related_products)}
          ${drawerList("Suggested structure", opportunity.suggested_structure)}
          ${drawerList("Suggested media", opportunity.suggested_media)}
          ${drawerList("Suggested internal links", opportunity.suggested_internal_links)}
          <div class="drawer-section">
            <h4>CTA strategy</h4>
            <p class="muted small">${escapeHtml(opportunity.cta_strategy || "No CTA strategy provided.")}</p>
          </div>
          <details class="analysis-artifacts"><summary>Competitor references</summary><pre>${escapeHtml(formatJson(opportunity.competitor_references || []))}</pre></details>
          <details class="analysis-artifacts"><summary>Evidence items</summary><pre>${escapeHtml(formatJson(opportunity.evidence_items || []))}</pre></details>
          <details class="analysis-artifacts"><summary>Raw opportunity</summary><pre>${escapeHtml(formatJson(opportunity))}</pre></details>
        </aside>
      `;
    }

    function closeOpportunityInspector() {
      const detail = document.getElementById("opportunity-detail");
      if (detail) {
        detail.innerHTML = "";
      }
    }

    function renderWorkspaceTab() {
      const listView = document.getElementById("workspace-opportunities-view");
      const secondary = document.getElementById("workspace-secondary-view");
      if (!listView || !secondary) {
        return;
      }
      const tab = opportunityWorkbenchState.activeTab;
      listView.hidden = tab !== "Opportunities";
      secondary.hidden = tab === "Opportunities";
      if (tab === "Opportunities") {
        return;
      }
      if (tab === "Clusters") {
        secondary.innerHTML = `<h3>Clusters</h3><pre>${escapeHtml(formatJson(latestClusters))}</pre>`;
      } else if (tab === "Audiences") {
        secondary.innerHTML = `<h3>Audiences</h3><pre>${escapeHtml(formatJson(latestAudiences))}</pre>`;
      } else if (tab === "Authority Graph") {
        secondary.innerHTML = `<h3>Authority Graph</h3><pre>${escapeHtml(formatJson(latestAuthorityGraph))}</pre>`;
      } else if (tab === "Campaigns") {
        secondary.innerHTML = '<h3>Campaigns</h3><p class="muted">Campaign planning data is scaffolded. Select opportunities and use queue/status workflows to prepare a campaign sequence.</p>';
      } else if (tab === "Queue") {
        const queued = latestOpportunities.filter(item => item.status === "planned");
        secondary.innerHTML = `<h3>Queue</h3><p class="muted">${escapeHtml(queued.length)} queued opportunities.</p><pre>${escapeHtml(formatJson(queued))}</pre>`;
      }
    }

    function renderOpportunityRows() {
      const body = document.getElementById("opportunity-table-body");
      if (!body) {
        return;
      }
      const filtered = visibleOpportunities();
      const pageCount = Math.max(1, Math.ceil(filtered.length / opportunityWorkbenchState.pageSize));
      opportunityWorkbenchState.page = Math.max(1, Math.min(opportunityWorkbenchState.page, pageCount));
      const start = (opportunityWorkbenchState.page - 1) * opportunityWorkbenchState.pageSize;
      const pageRows = filtered.slice(start, start + opportunityWorkbenchState.pageSize);
      body.innerHTML = pageRows.map(opportunity => opportunityRowHtml(opportunity)).join("");

      const status = document.getElementById("opportunity-page-status");
      if (status) {
        status.textContent = `${filtered.length} matching | page ${opportunityWorkbenchState.page} of ${pageCount}`;
      }
      const prev = document.getElementById("opportunity-prev-page");
      const next = document.getElementById("opportunity-next-page");
      if (prev) prev.disabled = opportunityWorkbenchState.page <= 1;
      if (next) next.disabled = opportunityWorkbenchState.page >= pageCount;
      updateBulkSelectionCount();
    }

    function opportunityRowHtml(opportunity) {
      const cluster = clusterForOpportunity(opportunity);
      const audience = audienceForOpportunity(opportunity);
      const selected = opportunityWorkbenchState.selectedIds.has(opportunity.id);
      const active = opportunityWorkbenchState.activeId === opportunity.id;
      const relationshipCount = opportunityRelationships(opportunity).length;
      return `
        <tr class="opportunity-row ${active ? "selected" : ""}" data-opportunity-id="${escapeHtml(opportunity.id)}">
          <td><input class="opportunity-row-select" type="checkbox" ${selected ? "checked" : ""} aria-label="Select opportunity"></td>
          <td class="opportunity-title">
            <strong>${escapeHtml(opportunity.title)}</strong>
            <span class="muted small">${escapeHtml(opportunity.target_keyword || "no keyword")}</span>
            <div class="chip-row">
              ${relationshipCount ? `<span class="mini-chip">rel ${escapeHtml(relationshipCount)}</span>` : ""}
              ${roleChip(opportunity)}
              ${typeChips(opportunity)}
            </div>
            <div class="opportunity-hover-preview">
              <strong>${escapeHtml(opportunity.title)}</strong>
              <p class="muted small">${escapeHtml(opportunity.rationale || "No rationale provided.")}</p>
              <div class="muted small">Entities: ${escapeHtml((opportunity.related_entities || []).slice(0, 6).join(", ") || "n/a")}</div>
              <div class="muted small">Products: ${escapeHtml((opportunity.related_products || []).slice(0, 4).join(", ") || opportunity.product_name || "n/a")}</div>
              <div class="muted small">Length: ${escapeHtml(opportunity.suggested_article_length || "n/a")} words</div>
            </div>
          </td>
          <td>${escapeHtml(cluster.name || "Unclustered")}</td>
          <td>${escapeHtml(audience.name || "General")}</td>
          <td>${escapeHtml(labelize(opportunity.opportunity_type || "opportunity"))}</td>
          <td>${escapeHtml(labelize(opportunity.search_intent || "informational"))}</td>
          <td>${scoreBadge(scoreValue(opportunity, "confidence"))}</td>
          <td>${scoreBar(scoreValue(opportunity, "authority"))}</td>
          <td>${scoreBar(scoreValue(opportunity, "geo"))}</td>
          <td>${scoreBar(scoreValue(opportunity, "novelty"))}</td>
          <td>${scoreBar(scoreValue(opportunity, "saturation"))}</td>
          <td>${scoreBar(scoreValue(opportunity, "editorial_effort"))}</td>
          <td><span class="mini-chip">${escapeHtml(opportunity.status || "suggested")}</span></td>
          <td class="row-actions">
            <button type="button" class="secondary-button" data-opportunity-action="use">Use</button>
            <button type="button" class="secondary-button" data-opportunity-action="approve">Approve</button>
            <button type="button" class="secondary-button" data-opportunity-action="reject">Reject</button>
            <button type="button" class="secondary-button" data-opportunity-action="bookmark">Bookmark</button>
            <button type="button" class="secondary-button" data-opportunity-action="queue">Queue</button>
            <button type="button" data-opportunity-action="generate">Generate</button>
          </td>
        </tr>
        ${opportunityWorkbenchState.density === "detailed" ? `
          <tr class="opportunity-row-detail">
            <td></td>
            <td colspan="13" class="muted small">${escapeHtml(opportunity.rationale || opportunity.audience_rationale || "No preview available.")}</td>
          </tr>
        ` : ""}
      `;
    }

    function visibleOpportunities() {
      const search = opportunityWorkbenchState.search.trim().toLowerCase();
      const filters = opportunityWorkbenchState.filters;
      const selectedClusters = opportunityWorkbenchState.clusterIds;
      const filtered = latestOpportunities.filter(opportunity => {
        const cluster = clusterForOpportunity(opportunity);
        const audience = audienceForOpportunity(opportunity);
        const haystack = [
          opportunity.title,
          opportunity.target_keyword,
          opportunity.rationale,
          opportunity.audience_rationale,
          opportunity.related_entities?.join(" "),
          opportunity.related_keywords?.join(" "),
          cluster.name,
          audience.name
        ].filter(Boolean).join(" ").toLowerCase();
        if (search && !haystack.includes(search)) return false;
        if (selectedClusters.size && !selectedClusters.has(opportunity.cluster_id || "")) return false;
        if (filters.audienceId && opportunity.primary_audience_id !== filters.audienceId) return false;
        if (filters.type && opportunity.opportunity_type !== filters.type) return false;
        if (filters.intent && opportunity.search_intent !== filters.intent) return false;
        if (filters.role && opportunity.content_role !== filters.role) return false;
        if (filters.status && opportunity.status !== filters.status) return false;
        if (filters.minAuthority && scoreValue(opportunity, "authority") < Number(filters.minAuthority)) return false;
        if (filters.minGeo && scoreValue(opportunity, "geo") < Number(filters.minGeo)) return false;
        if (filters.minNovelty && scoreValue(opportunity, "novelty") < Number(filters.minNovelty)) return false;
        return savedViewMatches(opportunity, opportunityWorkbenchState.savedView);
      });

      return filtered.sort((first, second) => {
        const firstValue = sortValue(first, opportunityWorkbenchState.sortKey);
        const secondValue = sortValue(second, opportunityWorkbenchState.sortKey);
        const direction = opportunityWorkbenchState.sortDirection === "asc" ? 1 : -1;
        if (typeof firstValue === "number" || typeof secondValue === "number") {
          return (Number(firstValue) - Number(secondValue)) * direction;
        }
        return String(firstValue).localeCompare(String(secondValue)) * direction;
      });
    }

    function savedViewMatches(opportunity, view) {
      if (view === "high-authority") return scoreValue(opportunity, "authority") >= 0.75;
      if (view === "quick-wins") return scoreValue(opportunity, "authority") >= 0.55 && scoreValue(opportunity, "editorial_effort") <= 0.55;
      if (view === "competitor-gaps") return opportunity.opportunity_type === "competitor_gap_article" || scoreValue(opportunity, "competitor_gap") >= 0.65;
      if (view === "low-competition") return scoreValue(opportunity, "saturation") <= 0.45 || scoreValue(opportunity, "novelty") >= 0.7;
      if (view === "geo") return scoreValue(opportunity, "geo") >= 0.6 || String(opportunity.opportunity_type || "").toLowerCase().includes("geo");
      if (view === "research-authority") return String(opportunity.search_intent || "").includes("informational") && scoreValue(opportunity, "authority") >= 0.6;
      if (view === "commercial-support") return ["commercial", "comparison", "transactional"].includes(opportunity.search_intent) || opportunity.funnel_stage === "consideration";
      return true;
    }

    function bindWorkbenchControls() {
      document.querySelectorAll("[data-workspace-tab]").forEach(button => {
        button.addEventListener("click", () => {
          opportunityWorkbenchState.activeTab = button.dataset.workspaceTab;
          renderOpportunityExplorer({ opportunities: latestOpportunities, clusters: latestClusters, audiences: latestAudiences, authority_graph: latestAuthorityGraph });
        });
      });
      document.getElementById("opportunity-search")?.addEventListener("input", event => {
        opportunityWorkbenchState.search = event.target.value;
        opportunityWorkbenchState.page = 1;
        renderOpportunityRows();
      });
      document.getElementById("opportunity-density-toggle")?.addEventListener("click", () => {
        const modes = ["compact", "comfortable", "detailed"];
        const currentIndex = modes.indexOf(opportunityWorkbenchState.density);
        opportunityWorkbenchState.density = modes[(currentIndex + 1) % modes.length];
        renderOpportunityExplorer({ opportunities: latestOpportunities, clusters: latestClusters, audiences: latestAudiences, authority_graph: latestAuthorityGraph });
      });
      document.getElementById("opportunity-clear-filters")?.addEventListener("click", () => {
        opportunityWorkbenchState.search = "";
        opportunityWorkbenchState.savedView = "all";
        opportunityWorkbenchState.clusterIds = new Set();
        opportunityWorkbenchState.filters = defaultOpportunityFilters();
        opportunityWorkbenchState.page = 1;
        renderOpportunityExplorer({ opportunities: latestOpportunities, clusters: latestClusters, audiences: latestAudiences, authority_graph: latestAuthorityGraph });
      });
      document.getElementById("opportunity-saved-view")?.addEventListener("change", event => {
        opportunityWorkbenchState.savedView = event.target.value;
        opportunityWorkbenchState.page = 1;
        renderOpportunityRows();
      });
      [
        ["opportunity-audience-filter", "audienceId"],
        ["opportunity-type-filter", "type"],
        ["opportunity-intent-filter", "intent"],
        ["opportunity-role-filter", "role"],
        ["opportunity-status-filter", "status"],
        ["opportunity-authority-filter", "minAuthority"],
        ["opportunity-geo-filter", "minGeo"],
        ["opportunity-novelty-filter", "minNovelty"]
      ].forEach(([id, key]) => {
        document.getElementById(id)?.addEventListener("change", event => {
          opportunityWorkbenchState.filters[key] = event.target.value;
          opportunityWorkbenchState.page = 1;
          renderOpportunityRows();
        });
      });
      document.querySelectorAll("[data-cluster-filter]").forEach(input => {
        input.addEventListener("change", event => {
          if (event.target.checked) {
            opportunityWorkbenchState.clusterIds.add(event.target.value);
          } else {
            opportunityWorkbenchState.clusterIds.delete(event.target.value);
          }
          opportunityWorkbenchState.page = 1;
          renderOpportunityRows();
        });
      });
      document.querySelectorAll(".opportunity-table th[data-sort]").forEach(header => {
        header.addEventListener("click", () => {
          const sortKey = header.dataset.sort;
          if (opportunityWorkbenchState.sortKey === sortKey) {
            opportunityWorkbenchState.sortDirection = opportunityWorkbenchState.sortDirection === "asc" ? "desc" : "asc";
          } else {
            opportunityWorkbenchState.sortKey = sortKey;
            opportunityWorkbenchState.sortDirection = ["title", "cluster", "audience", "status"].includes(sortKey) ? "asc" : "desc";
          }
          renderOpportunityRows();
        });
      });
      document.getElementById("opportunity-prev-page")?.addEventListener("click", () => {
        opportunityWorkbenchState.page -= 1;
        renderOpportunityRows();
      });
      document.getElementById("opportunity-next-page")?.addEventListener("click", () => {
        opportunityWorkbenchState.page += 1;
        renderOpportunityRows();
      });
      document.getElementById("opportunity-page-size")?.addEventListener("change", event => {
        opportunityWorkbenchState.pageSize = Number(event.target.value);
        opportunityWorkbenchState.page = 1;
        renderOpportunityRows();
      });
      document.getElementById("opportunity-select-page")?.addEventListener("change", event => {
        const pageOpportunities = currentPageOpportunities();
        pageOpportunities.forEach(opportunity => {
          if (event.target.checked) {
            opportunityWorkbenchState.selectedIds.add(opportunity.id);
          } else {
            opportunityWorkbenchState.selectedIds.delete(opportunity.id);
          }
        });
        renderOpportunityRows();
      });
      document.querySelectorAll("[data-bulk-action]").forEach(button => {
        button.addEventListener("click", async () => {
          await bulkUpdateOpportunities(button.dataset.bulkAction);
        });
      });
    }

    function restoreWorkbenchControls() {
      const pageSize = document.getElementById("opportunity-page-size");
      if (pageSize) pageSize.value = String(opportunityWorkbenchState.pageSize);
      const savedView = document.getElementById("opportunity-saved-view");
      if (savedView) savedView.value = opportunityWorkbenchState.savedView;
      Object.entries({
        "opportunity-audience-filter": "audienceId",
        "opportunity-type-filter": "type",
        "opportunity-intent-filter": "intent",
        "opportunity-role-filter": "role",
        "opportunity-status-filter": "status",
        "opportunity-authority-filter": "minAuthority",
        "opportunity-geo-filter": "minGeo",
        "opportunity-novelty-filter": "minNovelty"
      }).forEach(([id, key]) => {
        const element = document.getElementById(id);
        if (element) element.value = opportunityWorkbenchState.filters[key] || "";
      });
    }

    function currentPageOpportunities() {
      const filtered = visibleOpportunities();
      const start = (opportunityWorkbenchState.page - 1) * opportunityWorkbenchState.pageSize;
      return filtered.slice(start, start + opportunityWorkbenchState.pageSize);
    }

    async function bulkUpdateOpportunities(status) {
      const ids = [...opportunityWorkbenchState.selectedIds];
      if (!ids.length) {
        return;
      }
      await Promise.all(ids.map(id => patchOpportunity(id, { status })));
      latestOpportunities = latestOpportunities.map(opportunity => ids.includes(opportunity.id) ? { ...opportunity, status } : opportunity);
      opportunityWorkbenchState.selectedIds = new Set();
      renderOpportunityRows();
    }

    function updateBulkSelectionCount() {
      const count = document.getElementById("bulk-selection-count");
      if (count) {
        count.textContent = `${opportunityWorkbenchState.selectedIds.size} selected`;
      }
      const checkbox = document.getElementById("opportunity-select-page");
      if (checkbox) {
        const pageIds = currentPageOpportunities().map(item => item.id);
        checkbox.checked = pageIds.length > 0 && pageIds.every(id => opportunityWorkbenchState.selectedIds.has(id));
      }
    }

    function opportunitySummary(opportunities) {
      const clusterIds = new Set(opportunities.map(item => item.cluster_id).filter(Boolean));
      const audienceIds = new Set(opportunities.map(item => item.primary_audience_id).filter(Boolean));
      const pillars = opportunities.filter(item => String(item.content_role || "").includes("pillar")).length;
      const support = opportunities.length - pillars;
      const competitorGaps = opportunities.filter(item => item.opportunity_type === "competitor_gap_article" || scoreValue(item, "competitor_gap") >= 0.65).length;
      const geo = opportunities.filter(item => scoreValue(item, "geo") >= 0.6).length;
      return {
        total: opportunities.length,
        clusters: clusterIds.size || latestClusters.length,
        audiences: audienceIds.size || latestAudiences.length,
        pillars,
        support,
        competitorGaps,
        geo,
        avgAuthority: averageScore(opportunities, "authority"),
        avgNovelty: averageScore(opportunities, "novelty")
      };
    }

    function clusterNavigationHtml(opportunities, clusters) {
      const counts = new Map();
      opportunities.forEach(opportunity => counts.set(opportunity.cluster_id || "", (counts.get(opportunity.cluster_id || "") || 0) + 1));
      return clusters.map(cluster => {
        const clusterOpportunities = opportunities.filter(opportunity => opportunity.cluster_id === cluster.id);
        const avgAuthority = averageScore(clusterOpportunities, "authority");
        const checked = opportunityWorkbenchState.clusterIds.has(cluster.id) ? "checked" : "";
        return `
          <label>
            <span><input data-cluster-filter type="checkbox" value="${escapeHtml(cluster.id)}" ${checked}> ${escapeHtml(cluster.name)}</span>
            <span class="muted small">${escapeHtml(counts.get(cluster.id) || 0)} | ${escapeHtml(scoreLabel(avgAuthority))}</span>
          </label>
        `;
      }).join("") || '<div class="muted small">No clusters stored.</div>';
    }

    function scoreBreakdownHtml(opportunity) {
      const scores = opportunity.scores || {};
      return Object.entries(scores).map(([key, value]) => `
        <div class="muted small">${escapeHtml(labelize(key))}: ${scoreBar(Number(value || 0))}</div>
      `).join("") || '<p class="muted small">No scoring breakdown available.</p>';
    }

    function drawerList(title, values) {
      const items = Array.isArray(values) ? values : [];
      return `
        <div class="drawer-section">
          <h4>${escapeHtml(title)}</h4>
          ${items.length ? `<ul class="drawer-list small">${items.map(item => `<li>${escapeHtml(typeof item === "string" ? item : formatJson(item))}</li>`).join("")}</ul>` : '<p class="muted small">None recorded.</p>'}
        </div>
      `;
    }

    function summaryMetric(label, value) {
      return `<span class="stat-chip"><strong>${escapeHtml(value)}</strong>${escapeHtml(label)}</span>`;
    }

    function scoreBar(value) {
      const score = Math.max(0, Math.min(1, Number(value || 0)));
      return `
        <span class="score-bar">
          <span class="muted small">${escapeHtml(scoreLabel(score))}</span>
          <span class="score-bar-track"><span class="score-bar-fill" style="width:${Math.round(score * 100)}%"></span></span>
        </span>
      `;
    }

    function scoreBadge(value) {
      const score = Math.max(0, Math.min(1, Number(value || 0)));
      const klass = score >= 0.72 ? "good" : score >= 0.5 ? "warn" : "";
      return `<span class="score-badge ${klass}">${escapeHtml(scoreLabel(score))}</span>`;
    }

    function scoreLabel(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "n/a";
      }
      return `${Math.round(Number(value) * 100)}`;
    }

    function averageScore(opportunities, key) {
      if (!opportunities.length) return 0;
      return opportunities.reduce((sum, opportunity) => sum + scoreValue(opportunity, key), 0) / opportunities.length;
    }

    function scoreValue(opportunity, key) {
      const scores = opportunity.scores || {};
      const cluster = clusterForOpportunity(opportunity);
      if (key === "authority") return Number(scores.authority_fit ?? cluster.authority_value ?? 0);
      if (key === "geo") return Number(cluster.geo_value ?? scores.geo_value ?? scores.geo ?? 0);
      if (key === "confidence") return Number(opportunity.confidence ?? scores.overall ?? 0);
      return Number(scores[key] ?? opportunity[key] ?? 0);
    }

    function sortValue(opportunity, key) {
      if (key === "cluster") return clusterForOpportunity(opportunity).name || "";
      if (key === "audience") return audienceForOpportunity(opportunity).name || "";
      if (["confidence", "authority", "geo", "novelty", "saturation", "editorial_effort"].includes(key)) return scoreValue(opportunity, key);
      return opportunity[key] || "";
    }

    function clusterForOpportunity(opportunity) {
      return latestClusters.find(cluster => cluster.id === opportunity.cluster_id) || {};
    }

    function audienceForOpportunity(opportunity) {
      return latestAudiences.find(audience => audience.id === opportunity.primary_audience_id) || {};
    }

    function opportunityRelationships(opportunity) {
      const graphRelationships = opportunity.relationships || [];
      const ids = new Set([opportunity.id].concat(opportunity.relationship_ids || []));
      const artifactEdges = latestAuthorityGraph.relationships || [];
      const matches = graphRelationships.concat(artifactEdges.filter(edge => ids.has(edge.parent_id) || ids.has(edge.child_id)));
      if (matches.length) {
        return matches;
      }
      return (opportunity.relationship_ids || []).map(id => ({
        parent_id: opportunity.id,
        child_id: id,
        relationship_type: "semantic_support"
      }));
    }

    function roleChip(opportunity) {
      const role = opportunity.content_role || "";
      if (!role) return "";
      return `<span class="mini-chip">${escapeHtml(labelize(role))}</span>`;
    }

    function typeChips(opportunity) {
      const chips = [];
      if (String(opportunity.opportunity_type || "").includes("question")) chips.push("FAQ");
      if (scoreValue(opportunity, "geo") >= 0.6) chips.push("GEO");
      if (scoreValue(opportunity, "novelty") >= 0.7) chips.push("trend");
      if (opportunity.opportunity_type === "competitor_gap_article" || scoreValue(opportunity, "competitor_gap") >= 0.65) chips.push("competitor gap");
      return chips.map(chip => `<span class="mini-chip">${escapeHtml(chip)}</span>`).join("");
    }

    function labelize(value) {
      return String(value || "").replaceAll("_", " ");
    }

    function defaultOpportunityFilters() {
      return {
        audienceId: "",
        type: "",
        intent: "",
        role: "",
        status: "",
        minAuthority: "",
        minGeo: "",
        minNovelty: ""
      };
    }

    function renderSuggestions(suggestions) {
      const container = document.getElementById("suggestions");
      if (!suggestions.length) {
        container.innerHTML = '<div class="muted">No suggestions returned. Try a more specific website or fewer competitors.</div>';
        return;
      }

      container.innerHTML = suggestions.map((suggestion, index) => `
        <article class="suggestion" data-suggestion-id="${escapeHtml(suggestion.id || "")}" data-suggestion-index="${index}">
          <h3>Suggestion ${index + 1}</h3>
          <div class="muted small">Status: ${escapeHtml(suggestion.status || "suggested")}</div>
          ${suggestion.generated_job_id ? `<div class="muted small">Generated job: ${escapeHtml(suggestion.generated_job_id)}</div>` : ""}
          <label>Title</label>
          <input data-field="title" value="${escapeHtml(suggestion.title)}">
          <label>Target keyword</label>
          <input data-field="target_keyword" value="${escapeHtml(suggestion.target_keyword)}">
          <label>Product name</label>
          <input data-field="product_name" value="${escapeHtml(suggestion.product_name)}">
          <label>Product URL</label>
          <input data-field="product_url" value="${escapeHtml(suggestion.product_url)}">
          <div class="muted small">Confidence: ${escapeHtml(suggestion.confidence || "medium")}</div>
          <p>${escapeHtml(suggestion.reason)}</p>
          <div class="suggestion-actions">
            <button type="button" class="secondary-button" data-suggestion-action="use">Use in form</button>
            <button type="button" class="secondary-button" data-suggestion-action="approve">Approve</button>
            <button type="button" class="secondary-button" data-suggestion-action="reject">Reject</button>
            <button type="button" data-suggestion-action="generate">Generate article</button>
          </div>
        </article>
      `).join("");
    }

    async function loadAnalysisJobs() {
      const list = document.getElementById("analysis-jobs-list");
      try {
        const response = await fetch("/analysis-jobs");
        const jobs = await response.json();
        if (!jobs.length) {
          list.textContent = "No analyses yet. Analyze a website first.";
          return;
        }
        list.innerHTML = jobs.map(job => `
          <div class="analysis-job" data-analysis-job-id="${escapeHtml(job.id)}">
            <div class="job-title">
              <strong>${escapeHtml(job.website_url)}</strong>
              <span class="pill small">${escapeHtml(job.status)}</span>
            </div>
            <div class="muted small">${escapeHtml(job.created_at)}</div>
          </div>
        `).join("");
      } catch (error) {
        list.textContent = "Could not load recent analyses.";
      }
    }

    async function showAnalysisJob(analysisJobId) {
      const response = await fetch(`/analysis-jobs/${analysisJobId}`);
      const detail = await response.json();
      if (!response.ok) {
        throw new Error(detail.detail || "Could not load analysis.");
      }
      latestSuggestions = detail.suggestions || [];
      latestOpportunities = detail.opportunities || [];
      latestClusters = detail.clusters || [];
      latestAudiences = detail.audiences || [];
      latestAuthorityGraph = detail.authority_graph || {};
      document.getElementById("analysis-result").hidden = false;
      renderAnalysisDetail(detail);
    }

    function renderAnalysisDetail(detail) {
      const job = detail.analysis_job || {};
      const pages = detail.pages || [];
      const artifacts = detail.artifacts || [];
      const suggestions = detail.suggestions || [];
      const opportunities = detail.opportunities || [];
      const clusters = detail.clusters || [];
      const audiences = detail.audiences || [];
      const vertical = verticalDetectionFromArtifacts(artifacts);
      const externalResearch = externalResearchFromArtifacts(artifacts);
      const summary = document.getElementById("analysis-summary");
      const artifactHtml = artifacts.length
        ? `<details class="analysis-artifacts"><summary>Analysis artifacts</summary><pre>${escapeHtml(formatJson(artifacts))}</pre></details>`
        : "";
      summary.innerHTML = `
        <strong>${escapeHtml(job.website_url || "Analysis")}</strong>
        <span class="pill small">${escapeHtml(job.status || "unknown")}</span>
        ${vertical ? `<span class="pill small">Vertical: ${escapeHtml(vertical.detected_vertical || "generic")} (${escapeHtml(vertical.detected_vertical_confidence ?? "n/a")})</span>` : ""}
        ${externalResearch ? `<span class="pill small">External research: ${escapeHtml(externalResearch.status || "disabled")}</span>` : ""}
        <div class="muted small">Created: ${escapeHtml(job.created_at || "n/a")}</div>
        <div class="muted small">Pages saved: ${escapeHtml(pages.length)} | Opportunities: ${escapeHtml(opportunities.length)} | Clusters: ${escapeHtml(clusters.length)} | Audiences: ${escapeHtml(audiences.length)} | Legacy suggestions: ${escapeHtml(suggestions.length)}</div>
        ${externalResearch ? `<div class="muted small">Research sources: ${escapeHtml((externalResearch.sources_used || []).join(", ") || "none")} | Queries: ${escapeHtml(researchQueryCount(externalResearch))}</div>` : ""}
        ${job.summary ? `<p>${escapeHtml(job.summary)}</p>` : ""}
        ${job.error_message ? `<p class="key-status missing">Error: ${escapeHtml(job.error_message)}</p>` : ""}
        ${artifactHtml}
      `;
      renderOpportunityExplorer(detail);
      renderSuggestions(latestSuggestions);
    }

    function verticalDetectionFromArtifacts(artifacts) {
      const artifact = (artifacts || []).find(item => item.artifact_type === "vertical_detection");
      const content = artifact?.content_json || {};
      return content.detected_vertical ? content : null;
    }

    function externalResearchFromArtifacts(artifacts) {
      const artifact = (artifacts || []).find(item => item.artifact_type === "external_research_enrichment");
      return artifact?.content_json || null;
    }

    function researchQueryCount(externalResearch) {
      return Object.values(externalResearch?.queries || {}).reduce((total, value) => total + (Array.isArray(value) ? value.length : 0), 0);
    }

    function suggestionPayload(card, status = null) {
      const payload = {};
      card.querySelectorAll("[data-field]").forEach(input => {
        payload[input.dataset.field] = input.value;
      });
      if (status) {
        payload.status = status;
      }
      return payload;
    }

    async function patchSuggestion(suggestionId, payload) {
      const response = await fetch(`/analysis-suggestions/${suggestionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not update suggestion.");
      }
      return data;
    }

    async function patchOpportunity(opportunityId, payload) {
      const response = await fetch(`/opportunities/${opportunityId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not update opportunity.");
      }
      return data;
    }

    function parseCompetitorUrls(value) {
      return value
        .split("\\n")
        .map(url => url.trim())
        .filter(Boolean);
    }

    function renderApiKeyChecks(data) {
      const container = document.getElementById("api-key-checks");
      container.innerHTML = `
        ${data.checks.map(check => `
          <div class="key-row">
            <div>
              <strong>${escapeHtml(check.name)}</strong>
              <div class="muted small">${escapeHtml(check.detail)}</div>
              ${check.masked_value ? `<div class="muted small">Loaded: ${escapeHtml(check.masked_value)}</div>` : ""}
            </div>
            <div class="key-status ${escapeHtml(check.status)}">${escapeHtml(check.status)}</div>
          </div>
        `).join("")}
        <div class="muted small">${escapeHtml(data.note)}</div>
      `;
    }

    async function checkApiKeys() {
      const button = document.getElementById("check-api-keys-button");
      const container = document.getElementById("api-key-checks");
      button.disabled = true;
      button.textContent = "Checking...";
      container.textContent = "Checking loaded configuration...";

      try {
        const response = await fetch("/config/api-keys");
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not check API keys.");
        }
        renderApiKeyChecks(data);
      } catch (error) {
        container.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
      } finally {
        button.disabled = false;
        button.textContent = "Check API keys";
      }
    }

    document.querySelectorAll("[data-sample]").forEach(button => {
      button.addEventListener("click", () => setFormValues(samples[button.dataset.sample]));
    });

    document.getElementById("check-api-keys-button").addEventListener("click", checkApiKeys);

    document.getElementById("jobs-list").addEventListener("click", event => {
      const job = event.target.closest(".job");
      if (job) {
        showJob(job.dataset.jobId);
      }
    });

    document.getElementById("analysis-jobs-list").addEventListener("click", async event => {
      const job = event.target.closest(".analysis-job");
      if (!job) {
        return;
      }
      try {
        await showAnalysisJob(job.dataset.analysisJobId);
      } catch (error) {
        document.getElementById("analysis-result").hidden = false;
        document.getElementById("analysis-summary").textContent = "Could not load analysis.";
        document.getElementById("suggestions").innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
      }
    });

    let latestSuggestions = [];
    let latestOpportunities = [];
    let latestClusters = [];
    let latestAudiences = [];
    let latestAuthorityGraph = {};
    let opportunityWorkbenchState = {
      search: "",
      savedView: "all",
      sortKey: "authority",
      sortDirection: "desc",
      page: 1,
      pageSize: 50,
      density: "compact",
      activeTab: "Opportunities",
      selectedIds: new Set(),
      clusterIds: new Set(),
      activeId: null,
      filters: defaultOpportunityFilters()
    };
    let activeAnalysisController = null;

    document.getElementById("suggestions").addEventListener("click", async event => {
      const button = event.target.closest("[data-suggestion-action]");
      if (!button) {
        return;
      }
      const card = button.closest(".suggestion");
      const suggestion = latestSuggestions[Number(card.dataset.suggestionIndex)];
      if (!suggestion) {
        return;
      }
      const action = button.dataset.suggestionAction;
      const payload = suggestionPayload(card);

      try {
        if (action === "use") {
          setFormValues(payload);
          document.getElementById("title").scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }

        if (!suggestion.id) {
          throw new Error("This suggestion is not saved yet.");
        }

        button.disabled = true;
        if (action === "approve") {
          await patchSuggestion(suggestion.id, { ...payload, status: "approved" });
        } else if (action === "reject") {
          await patchSuggestion(suggestion.id, { ...payload, status: "rejected" });
        } else if (action === "generate") {
          await patchSuggestion(suggestion.id, { ...payload, status: "approved" });
          const response = await fetch(`/analysis-suggestions/${suggestion.id}/generate-article`, {
            method: "POST"
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.detail || "Could not generate article draft.");
          }
          const wordpress = data.article_job.wordpress_post || {};
          document.getElementById("result-card").hidden = false;
          document.getElementById("result-summary").innerHTML =
            `Article job ${escapeHtml(data.article_job.job_id)}. ${generationSummary(data.article_job)}`;
          renderGenerationDetails(data.article_job);
          document.getElementById("result-output").textContent = formatJson(data);
          if (wordpress.link) {
            document.getElementById("result-summary").innerHTML =
              `Article job ${escapeHtml(data.article_job.job_id)}. ${generationSummary(data.article_job)}`;
          }
          await loadJobs();
        }

        await showAnalysisJob(suggestion.analysis_job_id);
        await loadAnalysisJobs();
      } catch (error) {
        document.getElementById("result-card").hidden = false;
        document.getElementById("result-summary").textContent = "Suggestion action failed.";
        document.getElementById("result-output").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    document.getElementById("opportunity-explorer").addEventListener("click", async event => {
      if (event.target.closest("[data-inspector-close]")) {
        closeOpportunityInspector();
        return;
      }
      const button = event.target.closest("[data-opportunity-action]");
      if (!button) {
        const rowCheckbox = event.target.closest(".opportunity-row-select");
        if (rowCheckbox) {
          const row = rowCheckbox.closest(".opportunity-row");
          const id = row?.dataset.opportunityId;
          if (id) {
            if (rowCheckbox.checked) {
              opportunityWorkbenchState.selectedIds.add(id);
            } else {
              opportunityWorkbenchState.selectedIds.delete(id);
            }
            updateBulkSelectionCount();
          }
          return;
        }
        const selectedRow = event.target.closest(".opportunity-row");
        if (selectedRow) {
          const opportunity = latestOpportunities.find(item => item.id === selectedRow.dataset.opportunityId);
          renderOpportunityDetail(opportunity);
          renderOpportunityRows();
        }
        return;
      }
      const row = button.closest(".opportunity-row");
      const opportunity = latestOpportunities.find(item => item.id === row?.dataset.opportunityId);
      if (!opportunity) {
        return;
      }
      const action = button.dataset.opportunityAction;
      const payload = {
        title: opportunity.title,
        target_keyword: opportunity.target_keyword,
        product_name: opportunity.product_name || opportunity.target_keyword,
        product_url: opportunity.product_url
      };

      try {
        if (action === "use") {
          setFormValues(payload);
          document.getElementById("title").scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }

        button.disabled = true;
        if (action === "approve") {
          await patchOpportunity(opportunity.id, { ...payload, status: "approved" });
          opportunity.status = "approved";
        } else if (action === "reject") {
          await patchOpportunity(opportunity.id, { status: "rejected" });
          opportunity.status = "rejected";
        } else if (action === "bookmark") {
          await patchOpportunity(opportunity.id, { status: "bookmarked" });
          opportunity.status = "bookmarked";
        } else if (action === "queue") {
          await patchOpportunity(opportunity.id, { ...payload, status: "planned" });
          opportunity.status = "planned";
        } else if (action === "generate") {
          await patchOpportunity(opportunity.id, { ...payload, status: "approved" });
          const response = await fetch(`/opportunities/${opportunity.id}/generate-article`, {
            method: "POST"
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.detail || "Could not generate article draft.");
          }
          document.getElementById("result-card").hidden = false;
          document.getElementById("result-summary").innerHTML =
            `Article job ${escapeHtml(data.article_job.job_id)}. ${generationSummary(data.article_job)}`;
          renderGenerationDetails(data.article_job);
          document.getElementById("result-output").textContent = formatJson(data);
          await loadJobs();
        }

        renderOpportunityRows();
        renderOpportunityDetail(opportunity);
        await loadAnalysisJobs();
      } catch (error) {
        document.getElementById("result-card").hidden = false;
        document.getElementById("result-summary").textContent = "Opportunity action failed.";
        document.getElementById("result-output").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    document.getElementById("stop-analysis-button").addEventListener("click", async () => {
      const stopButton = document.getElementById("stop-analysis-button");
      const analysisButton = document.getElementById("analysis-button");
      const summary = document.getElementById("analysis-summary");
      const suggestions = document.getElementById("suggestions");

      stopButton.disabled = true;
      stopButton.textContent = "Stopping...";
      if (activeAnalysisController) {
        activeAnalysisController.abort();
      }
      summary.textContent = "Stopping active analysis...";

      try {
        const response = await fetch("/analysis-jobs/cancel-active", { method: "POST" });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not stop analysis.");
        }
        summary.textContent = data.cancelled_count
          ? `Stopped ${data.cancelled_count} active analysis job.`
          : "No active analysis job was running.";
        suggestions.innerHTML = '<pre>Analysis stopped.</pre>';
        await loadAnalysisJobs();
      } catch (error) {
        summary.textContent = "Could not stop analysis.";
        suggestions.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
      } finally {
        activeAnalysisController = null;
        analysisButton.disabled = false;
        analysisButton.textContent = "Analyze Website And Suggest Opportunities";
        stopButton.disabled = true;
        stopButton.textContent = "Stop Analysis";
      }
    });

    document.getElementById("analysis-form").addEventListener("submit", async event => {
      event.preventDefault();
      const button = document.getElementById("analysis-button");
      const stopButton = document.getElementById("stop-analysis-button");
      const result = document.getElementById("analysis-result");
      const summary = document.getElementById("analysis-summary");
      const suggestions = document.getElementById("suggestions");
      const formData = new FormData(event.target);

      button.disabled = true;
      button.textContent = "Analyzing...";
      stopButton.disabled = false;
      result.hidden = false;
      summary.textContent = "Fetching website signals and asking OpenAI for content opportunities.";
      suggestions.innerHTML = '<pre>Analyzing pages. This can take a moment.</pre>';

      const payload = {
        website_url: formData.get("website_url"),
        competitor_urls: parseCompetitorUrls(formData.get("competitor_urls") || ""),
        max_pages_per_site: Number(formData.get("max_pages_per_site") || 3),
        vertical: formData.get("vertical") || "auto"
      };
      activeAnalysisController = new AbortController();

      try {
        const response = await fetch("/analysis-jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: activeAnalysisController.signal
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Website analysis failed.");
        }
        latestSuggestions = data.suggestions || [];
        latestOpportunities = data.opportunities || [];
        latestClusters = data.clusters || [];
        latestAudiences = data.audiences || [];
        latestAuthorityGraph = data.authority_graph || {};
        renderAnalysisDetail(data);
        await loadAnalysisJobs();
      } catch (error) {
        latestSuggestions = [];
        latestOpportunities = [];
        if (error.name === "AbortError") {
          summary.textContent = "Website analysis was stopped.";
          suggestions.innerHTML = '<pre>Analysis stopped.</pre>';
        } else {
          summary.textContent = "Website analysis failed.";
          suggestions.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
        }
      } finally {
        activeAnalysisController = null;
        button.disabled = false;
        button.textContent = "Analyze Website And Suggest Opportunities";
        stopButton.disabled = true;
        stopButton.textContent = "Stop Analysis";
      }
    });

    document.addEventListener("click", async event => {
      const rerunButton = event.target.closest("[data-rerun-action]");
      if (rerunButton) {
        const jobId = rerunButton.dataset.jobId;
        const resultSummary = document.getElementById("result-summary");
        const output = document.getElementById("result-output");
        rerunButton.disabled = true;
        rerunButton.textContent = "Rerunning...";
        resultSummary.textContent = `Rerunning job ${jobId}. This creates a new job and may take a while.`;
        output.textContent = "Generating article from the saved job request.";
        try {
          const response = await fetch(`/jobs/${encodeURIComponent(jobId)}/rerun`, {
            method: "POST"
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.detail || "Rerun failed.");
          }
          const newJob = data.article_job || {};
          resultSummary.innerHTML = `Rerun created new job ${escapeHtml(newJob.job_id || "unknown")}. ${generationSummary(newJob)}`;
          renderGenerationDetails(newJob);
          output.textContent = formatJson(data);
          await loadJobs();
        } catch (error) {
          resultSummary.textContent = "Rerun failed.";
          output.textContent = error.message;
        } finally {
          rerunButton.disabled = false;
          rerunButton.textContent = "Rerun Job";
        }
        return;
      }

      const sanityButton = event.target.closest("[data-sanity-action]");
      if (sanityButton) {
        const jobId = sanityButton.dataset.jobId;
        const resultSummary = document.getElementById("result-summary");
        const output = document.getElementById("result-output");
        sanityButton.disabled = true;
        sanityButton.textContent = "Running sanity check...";
        try {
          const response = await fetch(`/jobs/${encodeURIComponent(jobId)}/run-sanity-check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ apply_rewrite: true })
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.detail || "Sanity check failed.");
          }
          resultSummary.innerHTML = `Sanity check completed for job ${escapeHtml(jobId)}. Status: ${escapeHtml(data.status)}.`;
          output.textContent = formatJson(data);
          await showJob(jobId);
          await loadJobs();
        } catch (error) {
          resultSummary.textContent = "Sanity check failed.";
          output.textContent = error.message;
        } finally {
          sanityButton.disabled = false;
          sanityButton.textContent = "Run Sanity Check";
        }
        return;
      }

      const button = event.target.closest("[data-publish-action]");
      if (!button) {
        return;
      }
      const jobId = button.dataset.jobId;
      const action = button.dataset.publishAction;
      const resultSummary = document.getElementById("result-summary");
      const output = document.getElementById("result-output");
      if (action !== "draft") {
        return;
      }
      button.disabled = true;
      try {
        const response = await fetch(`/jobs/${encodeURIComponent(jobId)}/wordpress-connector/draft`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "WordPress draft creation failed.");
        }
        const wpLink = data.wordpress_edit_url || data.wordpress_public_url || data.wordpress_post?.link || "";
        resultSummary.innerHTML = `WordPress draft created for job ${escapeHtml(jobId)}. ${wpLink ? `<a href="${escapeHtml(wpLink)}" target="_blank" rel="noreferrer">Open in WordPress</a>` : ""}`;
        output.textContent = formatJson(data);
        await showJob(jobId);
        await loadJobs();
        await loadUnattendedStatus();
      } catch (error) {
        resultSummary.textContent = "Publish failed.";
        output.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    document.getElementById("generate-form").addEventListener("submit", async event => {
      event.preventDefault();
      const button = document.getElementById("submit-button");
      const resultCard = document.getElementById("result-card");
      const resultSummary = document.getElementById("result-summary");
      const output = document.getElementById("result-output");

      button.disabled = true;
      button.textContent = "Generating...";
      resultCard.hidden = false;
      resultSummary.textContent = "Working through generation, enrichment, review cleanup, quality checks, and local preview creation.";
      output.textContent = "This can take a moment because external APIs are involved.";

      const formData = new FormData(event.target);
      const payload = Object.fromEntries(formData.entries());
      if (!payload.category_id) {
        delete payload.category_id;
      } else {
        payload.category_id = Number(payload.category_id);
        payload.wordpress_category_id = payload.category_id;
      }
      payload.unattended_mode = payload.unattended_mode === "true";
      payload.wordpress_tags = tagsFromInput(payload.wordpress_tags);
      if (!payload.featured_image_url) {
        delete payload.featured_image_url;
      }
      if (!payload.featured_image_id) {
        delete payload.featured_image_id;
      } else {
        payload.featured_image_id = Number(payload.featured_image_id);
      }
      if (!payload.featured_image_alt) {
        delete payload.featured_image_alt;
      }

      try {
        const response = await fetch("/generate-article", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Generation failed.");
        }
        resultSummary.innerHTML = `Job ${escapeHtml(data.job_id)}. ${generationSummary(data)}`;
        renderGenerationDetails(data);
        output.textContent = formatJson(data);
        await loadJobs();
        await loadUnattendedStatus();
      } catch (error) {
        resultSummary.textContent = "Generation failed.";
        output.textContent = error.message;
      } finally {
        button.disabled = false;
        button.textContent = "Generate Article";
      }
    });

    loadJobs();
    loadWordPressCategories();
    loadWordPressTemplates();
    loadUnattendedStatus();
    loadAnalysisJobs();
    checkApiKeys();
  </script>
</body>
</html>
"""
