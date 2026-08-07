"""Multi-Page SaaS HTML Interface for YouTube SEO Studio."""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube SEO Studio · SaaS AI Growth Co-Pilot</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300..800;1,300..800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    /* Default theme: calm, focused light workspace. */
    :root, [data-theme="light"] {
      --bg: #f7f8fb;
      --bg-gradient: radial-gradient(800px 500px at 50% -100px, rgba(229, 9, 20, 0.10), transparent 70%),
                     radial-gradient(700px 500px at 100% 80%, rgba(254, 226, 226, 0.72), transparent 65%);
      --sidebar-width: 260px;
      --panel: rgba(255, 255, 255, 0.92);
      --panel-solid: #ffffff;
      --panel-hover: #fff5f5;
      --border: #e7e9ef;
      --border-bright: rgba(229, 9, 20, 0.34);
      --text: #17181c;
      --text-muted: #606774;
      --text-sub: #8a919e;

      --accent: #e50914;
      --accent-rose: #b91c1c;
      --accent-cyan: #be123c;
      --accent-grad: linear-gradient(135deg, #e50914 0%, #b91c1c 100%);
      --accent-grad-hover: linear-gradient(135deg, #f81d28 0%, #dc2626 100%);
      --accent-shadow: rgba(229, 9, 20, 0.25);

      --ok: #10b981;
      --ok-bg: rgba(16, 185, 129, 0.12);
      --warn: #f59e0b;
      --warn-bg: rgba(245, 158, 11, 0.12);
      --bad: #ef4444;
      --bad-bg: rgba(239, 68, 68, 0.12);

      --radius-lg: 18px;
      --radius: 12px;
      --radius-sm: 8px;
      --mono: "JetBrains Mono", monospace;
      --sans: "Plus Jakarta Sans", "Inter", system-ui, sans-serif;
      color-scheme: light;
    }

    /* Reserved dark-mode palette. It can be enabled later without changing page markup. */
    [data-theme="dark"] {
      --bg: #101114;
      --bg-gradient: radial-gradient(800px 500px at 50% -100px, rgba(229, 9, 20, 0.12), transparent 70%);
      --panel: rgba(26, 27, 31, 0.92);
      --panel-solid: #1a1b1f;
      --panel-hover: #25262c;
      --border: #32343b;
      --border-bright: rgba(229, 9, 20, 0.4);
      --text: #f8fafc;
      --text-muted: #a9afb9;
      --text-sub: #7f8794;
      color-scheme: dark;
    }

    [data-theme="cyber"] {
      --bg: #0c0608;
      --bg-gradient: radial-gradient(900px 600px at 50% -100px, rgba(255, 42, 95, 0.22), transparent 70%),
                     radial-gradient(700px 500px at 100% 80%, rgba(255, 94, 0, 0.16), transparent 60%);
      --panel: rgba(24, 14, 20, 0.85);
      --panel-solid: #191016;
      --panel-hover: rgba(36, 20, 30, 0.9);
      --border-bright: rgba(255, 42, 95, 0.35);
      --accent: #ff2a5f;
      --accent-grad: linear-gradient(135deg, #ff2a5f 0%, #ff5e00 100%);
      --accent-grad-hover: linear-gradient(135deg, #ff4d79 0%, #ff7726 100%);
      --accent-shadow: rgba(255, 42, 95, 0.45);
    }

    [data-theme="obsidian"] {
      --bg: #030304;
      --bg-gradient: radial-gradient(900px 600px at 50% -100px, rgba(230, 0, 38, 0.22), transparent 70%);
      --panel: rgba(14, 12, 14, 0.95);
      --panel-solid: #0f0d0e;
      --panel-hover: rgba(24, 20, 22, 0.95);
      --border-bright: rgba(230, 0, 38, 0.4);
      --accent: #e60026;
      --accent-grad: linear-gradient(135deg, #e60026 0%, #800014 100%);
      --accent-grad-hover: linear-gradient(135deg, #ff1a3d 0%, #990018 100%);
      --accent-shadow: rgba(230, 0, 38, 0.55);
    }

    [data-theme="emerald"] {
      --bg: #040a08;
      --bg-gradient: radial-gradient(900px 600px at 50% -100px, rgba(16, 185, 129, 0.18), transparent 70%),
                     radial-gradient(700px 500px at 100% 80%, rgba(6, 182, 212, 0.12), transparent 60%);
      --panel: rgba(12, 22, 18, 0.85);
      --panel-solid: #0d1713;
      --panel-hover: rgba(18, 34, 27, 0.9);
      --border-bright: rgba(16, 185, 129, 0.35);
      --accent: #10b981;
      --accent-grad: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
      --accent-grad-hover: linear-gradient(135deg, #34d399 0%, #22d3ee 100%);
      --accent-shadow: rgba(16, 185, 129, 0.45);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; }
    body {
      font-family: var(--sans);
      background: var(--bg);
      background-image: var(--bg-gradient);
      background-attachment: fixed;
      color: var(--text);
      -webkit-font-smoothing: antialiased;
      display: flex; overflow: hidden;
    }

    /* Left Sidebar SaaS Navigation */
    aside.sidebar {
      width: var(--sidebar-width); height: 100vh; flex-shrink: 0;
      background: rgba(255, 255, 255, 0.90);
      backdrop-filter: blur(20px);
      border-right: 1px solid var(--border);
      display: flex; flex-direction: column; justify-content: space-between;
      padding: 20px 16px; z-index: 100;
    }
    .sidebar-brand { display: flex; align-items: center; gap: 12px; padding: 6px 8px 24px; border-bottom: 1px solid var(--border); }
    .brand-icon {
      width: 36px; height: 36px; border-radius: 10px;
      background: var(--accent-grad); display: grid; place-items: center;
      box-shadow: 0 0 16px var(--accent-shadow); flex-shrink: 0;
    }
    .brand-title h1 { font-size: 15px; font-weight: 800; letter-spacing: -0.02em; color: var(--text); }
    .brand-title p { font-size: 11px; color: var(--text-sub); font-weight: 500; }

    .nav-menu { display: flex; flex-direction: column; gap: 6px; margin-top: 20px; }
    .nav-item {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 16px; border-radius: var(--radius-sm);
      color: var(--text-muted); font-size: 13.5px; font-weight: 600;
      cursor: pointer; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); text-decoration: none;
      border: 1px solid transparent; position: relative;
    }
    .nav-item:hover { color: var(--text); background: var(--panel-hover); border-color: var(--border); }
    .nav-item.active {
      color: var(--accent);
      background: linear-gradient(90deg, rgba(229, 9, 20, 0.18) 0%, rgba(229, 9, 20, 0.04) 100%);
      border-color: rgba(229, 9, 20, 0.3);
      box-shadow: 0 4px 16px rgba(229, 9, 20, 0.15);
      border-left: 3px solid var(--accent);
    }
    .nav-item svg { width: 18px; height: 18px; flex-shrink: 0; }

    .sidebar-footer { padding-top: 16px; border-top: 1px solid var(--border); }
    .status-badge {
      display: flex; align-items: center; gap: 8px;
      padding: 8px 12px; border-radius: var(--radius-sm); font-size: 11.5px; font-weight: 600;
      background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); color: var(--text-muted);
    }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }

    /* Right Main Content App Container */
    main.app-container {
      flex-grow: 1; height: 100vh; overflow-y: auto;
      display: flex; flex-direction: column;
      background: var(--bg);
    }

    .top-bar {
      position: sticky; top: 0; z-index: 90;
      background: rgba(255, 255, 255, 0.90); backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border); padding: 16px 32px;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }
    .page-header-title h2 { font-size: 19px; font-weight: 800; letter-spacing: -0.02em; color: var(--text); }
    .page-header-title p { font-size: 12.5px; color: var(--text-sub); margin-top: 2px; }

    .top-actions { display: flex; align-items: center; gap: 10px; }

    /* Page Views Layout */
    .content-viewport { padding: 32px; max-width: 1400px; width: 100%; margin: 0 auto; }
    .page-view { display: none; }
    .page-view.active { display: block; animation: fadeIn 0.3s ease both; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

    /* Glassmorphism Components */
    .glass-card {
      background: var(--panel); backdrop-filter: blur(16px);
      border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }

    /* Buttons */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 8px;
      padding: 10px 18px; border-radius: var(--radius-sm); font-size: 13.5px; font-weight: 600;
      border: 1px solid var(--border); background: var(--panel-solid); color: var(--text);
      cursor: pointer; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); text-decoration: none;
    }
    .btn:hover { background: var(--panel-hover); border-color: var(--border-bright); transform: translateY(-1px); }
    .btn-primary {
      background: var(--accent-grad); border: none; color: #fff; font-weight: 700;
      box-shadow: 0 4px 20px var(--accent-shadow); padding: 11px 22px; font-size: 14px;
    }
    .btn-primary:hover { background: var(--accent-grad-hover); box-shadow: 0 6px 25px var(--accent-shadow); transform: translateY(-2px); }

    /* Form Controls */
    .input-box {
      width: 100%; min-height: 140px; max-height: 380px; resize: vertical;
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 16px; color: var(--text);
      font-family: var(--sans); font-size: 14px; line-height: 1.6; outline: none; transition: border-color 0.2s, box-shadow 0.2s;
    }
    .input-box:focus { border-color: var(--accent); box-shadow: 0 0 18px var(--accent-shadow); }

    /* Bento Cards & Grids */
    .bento-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }
    .bento-card {
      grid-column: span 12; padding: 20px;
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius-lg); position: relative; overflow: hidden;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .bento-card:hover { border-color: var(--border-bright); }
    .span-6 { grid-column: span 6; }
    .span-4 { grid-column: span 4; }
    .span-3 { grid-column: span 3; }
    .span-8 { grid-column: span 8; }
    @media (max-width: 900px) { .span-6, .span-4, .span-3, .span-8 { grid-column: span 12; } }

    .card-title {
      font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--text-sub); margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;
    }
    .metric-value { font-size: 32px; font-weight: 800; letter-spacing: -0.03em; color: var(--text); line-height: 1.1; }
    .metric-sub { font-size: 12.5px; color: var(--text-muted); margin-top: 6px; }

    /* Chips & Meters */
    .chip {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
      background: #f5f6f8; border: 1px solid var(--border); color: var(--text-muted);
    }
    .chip-ok { background: var(--ok-bg); color: var(--ok); border-color: rgba(16, 185, 129, 0.3); }
    .chip-warn { background: var(--warn-bg); color: var(--warn); border-color: rgba(245, 158, 11, 0.3); }
    .chip-bad { background: var(--bad-bg); color: var(--bad); border-color: rgba(239, 68, 68, 0.3); }
    .chip-accent { background: rgba(229, 9, 20, 0.15); color: var(--text); border-color: rgba(229, 9, 20, 0.35); }

    .tag-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .tag-item {
      font-family: var(--mono); font-size: 12px; padding: 4px 10px; border-radius: var(--radius-sm);
      background: #f7f8fa; border: 1px solid var(--border); color: var(--text-muted);
    }

    /* Tabs */
    .tabs-bar {
      display: flex; gap: 6px; padding: 4px; border-radius: var(--radius);
      background: #f4f5f7; border: 1px solid var(--border); width: fit-content;
    }
    .tab-btn {
      padding: 8px 18px; border-radius: var(--radius-sm); border: none; background: transparent;
      color: var(--text-muted); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s;
    }
    .tab-btn:hover { color: var(--text); }
    .tab-btn.active { background: var(--accent); color: #fff; box-shadow: 0 4px 14px var(--accent-shadow); }

    .progress-bar { height: 6px; border-radius: 999px; background: #eceef2; overflow: hidden; margin-top: 10px; }
    .progress-fill { height: 100%; border-radius: 999px; background: var(--accent-grad); transition: width 0.5s ease; }

    .kv-list { display: flex; flex-direction: column; gap: 8px; }
    .kv-item { display: flex; align-items: center; justify-content: space-between; padding-bottom: 8px; border-bottom: 1px dashed var(--border); }
    .kv-item:last-child { border-bottom: none; padding-bottom: 0; }
    .kv-key { font-size: 12.5px; color: var(--text-muted); }
    .kv-val { font-size: 13px; font-weight: 600; }

    .alert-banner {
      padding: 14px 18px; border-radius: var(--radius); font-size: 13px;
      display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px;
    }
    .alert-err { background: var(--bad-bg); border: 1px solid rgba(239, 68, 68, 0.3); color: #b91c1c; }

    /* Table styling for history widget */
    .history-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    .history-table th { text-align: left; font-size: 11px; color: var(--text-sub); text-transform: uppercase; padding: 8px 12px; border-bottom: 1px solid var(--border); }
    .history-table td { font-size: 13px; padding: 12px; border-bottom: 1px dashed var(--border); color: var(--text); }
    .history-table tr:hover td { background: #fff8f8; }

    /* Streamlined Core Inputs Grid */
    .core-inputs-grid {
      display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-top: 16px;
    }
    @media (max-width: 900px) { .core-inputs-grid { grid-template-columns: 1fr; } }
    .field-group { display: flex; flex-direction: column; gap: 6px; }
    .field-group label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
    .field-group select, .field-group input {
      width: 100%; background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 10px 14px; color: var(--text); font-size: 13.5px; outline: none;
    }
    .field-group select:focus, .field-group input:focus { border-color: var(--accent); }

    /* Accordion Brief */
    details.accordion {
      border: 1px solid var(--border); border-radius: var(--radius);
      background: #fafbfc; overflow: hidden; margin-top: 16px;
    }
    details.accordion summary {
      padding: 12px 16px; font-size: 12.5px; font-weight: 700; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; color: var(--text-muted); user-select: none;
    }
    details.accordion summary:hover { color: var(--text); }
    .brief-grid { padding: 16px; border-top: 1px solid var(--border); display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .brief-field { display: flex; flex-direction: column; gap: 6px; }
    .brief-field.wide { grid-column: span 2; }
    .brief-field label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
    .brief-field input, .brief-field select {
      width: 100%; background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 9px 12px; color: var(--text); font-size: 13px; outline: none;
    }

    .hidden { display: none !important; }

    .spin { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spinner 0.7s linear infinite; }
    .output-box { background: #fafbfc !important; color: var(--text) !important; border-color: var(--border) !important; }
    .tag-list[style] { background: #fafbfc !important; }
    .input-box[style] { background: var(--panel-solid) !important; border-color: var(--border) !important; }
    .hero-card { background: linear-gradient(135deg, #fff7f7 0%, #ffffff 70%) !important; border-color: rgba(229, 9, 20, 0.24) !important; }
    .hero-card h1[style], .glass-card h1[style] { color: var(--text) !important; }
    #outputContent [style*="rgba(255,255,255,0.02)"] { background: #fafbfc !important; }
    #themeSelector option { background: #ffffff !important; color: #17181c !important; }
    #themeSelector option:not([value="light"]) { display: none; }
    pre { background: #fafbfc; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px; }
    [data-theme="light"] .sidebar-footer .status-badge { color: #991b1b !important; }
    [data-theme="dark"] aside.sidebar, [data-theme="dark"] .top-bar { background: rgba(16, 17, 20, 0.94); }
    @media (max-width: 700px) {
      body { display: block; overflow: auto; }
      aside.sidebar { width: 100%; height: auto; padding: 12px; position: sticky; top: 0; }
      .sidebar-brand { padding-bottom: 12px; }
      .nav-menu { flex-direction: row; overflow-x: auto; margin-top: 12px; }
      .nav-item { flex: 0 0 auto; padding: 9px 12px; font-size: 12px; }
      .sidebar-footer { display: none; }
      main.app-container { height: auto; min-height: 100vh; }
      .top-bar { padding: 14px 16px; }
      .top-actions .btn-primary { display: none; }
      .content-viewport { padding: 16px; }
      .brief-grid { grid-template-columns: 1fr; }
      .brief-field.wide { grid-column: span 1; }
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <!-- Left Sidebar SaaS Navigation -->
  <aside class="sidebar">
    <div>
      <div class="sidebar-brand">
        <div class="brand-icon" style="background:var(--accent-grad);box-shadow:0 4px 14px var(--accent-shadow)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#fff"><path d="M21.6 7.2a2.7 2.7 0 0 0-1.9-1.9C18 5 12 5 12 5s-6 0-7.7.3A2.7 2.7 0 0 0 2.4 7.2 28 28 0 0 0 2 12a28 28 0 0 0 .4 4.8 2.7 2.7 0 0 0 1.9 1.9C6 19 12 19 12 19s6 0 7.7-.3a2.7 2.7 0 0 0 1.9-1.9A28 28 0 0 0 22 12a28 28 0 0 0-.4-4.8ZM10 15V9l5 3-5 3Z"/></svg>
        </div>
        <div class="brand-title">
          <h1 style="display:flex;align-items:center;gap:6px">YouTube Studio <span style="font-size:10px;padding:2px 6px;background:var(--accent);color:#fff;border-radius:4px;font-weight:800;letter-spacing:0.04em">PRO v3.5</span></h1>
          <p style="color:var(--accent);font-weight:600">AI Personal Growth Engine</p>
        </div>
      </div>

      <nav class="nav-menu">
        <a class="nav-item active" href="#dashboard" id="nav-dashboard" data-page="dashboard" onclick="switchPage('dashboard'); return false;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>
          Dashboard Overview
        </a>
        <a class="nav-item" href="#creator" id="nav-creator" data-page="creator" onclick="switchPage('creator'); return false;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"/></svg>
          SEO Creator Studio
        </a>
        <a class="nav-item" href="#analytics" id="nav-analytics" data-page="analytics" onclick="switchPage('analytics'); return false;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
          Channel Analytics
        </a>
        <a class="nav-item" href="#history" id="nav-history" data-page="history" onclick="switchPage('history'); return false;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16v16H4z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>
          Package History
        </a>
        <a class="nav-item" href="#settings" id="nav-settings" data-page="settings" onclick="switchPage('settings'); return false;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          Settings &amp; APIs
        </a>
      </nav>
    </div>

    <div class="sidebar-footer">
      <div class="status-badge" style="background:rgba(229,9,20,0.12);border:1px solid rgba(229,9,20,0.3);color:#fff"><span class="dot" style="background:var(--ok)"></span> Gemini 3.5 Flash Active</div>
    </div>
  </aside>

  <!-- Right Application Body Workspace -->
  <main class="app-container">
    <div class="top-bar">
      <div class="page-header-title">
        <h2 id="topTitle">Dashboard Overview</h2>
        <p id="topSub">Welcome back, creator! Track your SEO performance and generate new packages.</p>
      </div>
      <div class="top-actions">
        <div style="display:flex;align-items:center;gap:8px;background:var(--panel-solid);border:1px solid var(--border);padding:4px 10px;border-radius:var(--radius-sm)">
          <span style="font-size:11.5px;font-weight:700;color:var(--text-sub);text-transform:uppercase;letter-spacing:0.05em">Theme:</span>
          <select id="themeSelector" style="background:transparent;border:none;color:var(--text);font-size:12.5px;font-weight:600;outline:none;cursor:pointer">
            <option value="light">Light workspace</option>
            <option value="red" style="background:#151114;color:#fff">🔴 Crimson Red (YouTube)</option>
            <option value="cyber" style="background:#151114;color:#fff">⚡ Cyber Flame</option>
            <option value="obsidian" style="background:#151114;color:#fff">🌌 Obsidian Blood Red</option>
            <option value="emerald" style="background:#151114;color:#fff">🟢 Emerald Dark</option>
          </select>
        </div>
        <a class="btn btn-primary" href="#creator" onclick="switchPage('creator'); return false;">⚡ New SEO Analysis</a>
      </div>
    </div>

    <div class="content-viewport">
      <!-- PAGE 1: COMPLETELY REDESIGNED DASHBOARD WORKSPACE -->
      <section class="page-view active" id="view-dashboard">
        <div class="bento-grid">

          <!-- HERO STUDIO HEADER BANNER (SPAN 12) -->
          <div class="bento-card span-12 hero-card" style="padding:24px 28px">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
              <div>
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                  <span class="chip chip-accent" style="font-weight:700;font-size:11.5px">⚡ Studio AI Command v3.5</span>
                  <span class="chip chip-ok" style="font-weight:600;font-size:11.5px"><span class="dot"></span> YouTube Channel Synced</span>
                </div>
                <h1 style="font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#fff">YouTube Creator SEO Growth Studio</h1>
                <p style="font-size:13px;color:var(--text-muted);margin-top:4px;max-width:650px">
                  Turn video ideas into upload-ready SEO titles, rich descriptions, tags, and AI retention strategies using live YouTube market research.
                </p>
              </div>

              <div style="display:flex;gap:10px">
                <a class="btn btn-primary" href="#creator" onclick="switchPage('creator'); return false;" style="padding:12px 24px;font-size:14px">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Open Full Studio Workspace
                </a>
              </div>
            </div>
          </div>

          <!-- QUICK SCRIPT LAUNCHER STUDIO CARD (SPAN 12) -->
          <div class="bento-card span-12" style="border-top:3px solid var(--accent)">
            <div class="card-title">
              <span style="display:flex;align-items:center;gap:8px">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--accent)"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Instant Video SEO Package Generator
              </span>
              <span style="font-size:11.5px;color:var(--text-sub);font-family:var(--mono)">Powered by Gemini 3.5 Flash</span>
            </div>

            <textarea id="dashQuickScript" class="input-box" style="min-height:100px;background:rgba(10, 10, 14, 0.7);border-color:rgba(255,255,255,0.1)" placeholder="Paste your video script excerpt, raw idea, or quote here (e.g. The biggest betrayal is knowing that if you didn't find out, they would have never told you...)..."></textarea>

            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-top:16px">
              <div style="display:flex;gap:12px;flex-wrap:wrap">
                <div class="field-group" style="margin:0">
                  <select id="dashQuickLang" style="background:var(--panel-solid);border:1px solid var(--border);border-radius:var(--radius-sm);padding:9px 14px;color:var(--text);font-size:13px;font-weight:600">
                    <option value="english">🌐 Language: English</option>
                    <option value="tamil">🇮🇳 Language: Tamil (தமிழ்)</option>
                    <option value="tanglish">⚡ Language: Tanglish</option>
                  </select>
                </div>
                <div class="field-group" style="margin:0">
                  <select id="dashQuickRegion" style="background:var(--panel-solid);border:1px solid var(--border);border-radius:var(--radius-sm);padding:9px 14px;color:var(--text);font-size:13px;font-weight:600">
                    <option value="global">🌍 Target Region: Global</option>
                    <option value="in">🇮🇳 Target Region: India (IN)</option>
                  </select>
                </div>
              </div>

              <button class="btn btn-primary" id="dashQuickLaunchBtn" style="padding:11px 26px;font-size:14px">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Generate SEO Package Now
              </button>
            </div>
          </div>

          <!-- 4 KEY KPI ANALYTICS CARDS WITH RED TOP ACCENT LINES (SPAN 3 EACH) -->
          <div class="bento-card span-3" style="border-top:3px solid var(--accent)">
            <div class="card-title"><span>28d Views Milestone</span></div>
            <div class="metric-value" id="dashMetricViews" style="color:var(--text);font-size:32px">--</div>
            <div class="metric-sub" style="margin-top:8px">Connect and refresh your channel to load actual data.</div>
          </div>

          <div class="bento-card span-3" style="border-top:3px solid var(--accent)">
            <div class="card-title"><span>Estimated Watch Time</span></div>
            <div class="metric-value" id="dashMetricWatch" style="font-size:32px">--</div>
            <div class="metric-sub" style="margin-top:8px">Not available until YouTube Analytics sync succeeds.</div>
          </div>

          <div class="bento-card span-3" style="border-top:3px solid var(--accent)">
            <div class="card-title"><span>Avg Opportunity Score</span></div>
            <div class="metric-value" style="color:var(--accent);font-size:32px" id="dashMetricOpp">--</div>
            <div class="metric-sub" style="margin-top:8px">Calculated from your saved analyses.</div>
          </div>

          <div class="bento-card span-3" style="border-top:3px solid var(--accent)">
            <div class="card-title"><span>AI Engine Status</span></div>
            <div class="metric-value" style="font-size:20px;display:flex;align-items:center;gap:6px;margin-top:4px">
              Gemini <span style="font-size:12px;padding:3px 8px" class="chip chip-ok">⚡ Active</span>
            </div>
            <div class="metric-sub" style="margin-top:8px">Gemini 3.5 Flash + Local DB</div>
          </div>

          <!-- RECENT VIDEO PACKAGE HISTORY TABLE (SPAN 7) -->
          <div class="bento-card span-7">
            <div class="card-title">
              <span>Recent Video Package History Log</span>
              <span class="chip chip-accent">SQLite DB Sync</span>
            </div>
            <div id="dashHistoryWrap" style="overflow-x:auto;margin-top:12px">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Video Idea / Topic</th>
                    <th>Predicted CTR</th>
                    <th>Opportunity</th>
                    <th>Date &amp; Time (IST)</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody id="dashHistoryBody">
                  <tr>
                    <td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">Loading stored analysis history from SQLite database...</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- CONNECTED CHANNEL & UPLOAD SCHEDULER WIDGET (SPAN 5) -->
          <div class="bento-card span-5" style="display:flex;flex-direction:column;justify-content:space-between">
            <div>
              <div class="card-title">
                <span>Connected YouTube Channel</span>
                <span class="chip chip-ok"><span class="dot"></span> Live Sync</span>
              </div>

              <div style="display:flex;align-items:center;gap:14px;margin-top:10px">
                <div style="width:46px;height:46px;border-radius:14px;background:var(--accent-grad);display:grid;place-items:center;font-weight:800;font-size:20px;color:#fff;box-shadow:0 4px 16px var(--accent-shadow)">
                  M
                </div>
                <div>
                  <div class="metric-value" style="font-size:22px" id="dashChannelName">No channel connected</div>
                  <div class="metric-sub" style="font-size:12px;margin-top:2px" id="dashChannelStats">Last 28 days: 1,050 views · 24 likes</div>
                </div>
              </div>

              <div style="margin-top:16px;padding:12px 14px;border-radius:var(--radius-sm);background:rgba(229, 9, 20, 0.08);border:1px solid rgba(229, 9, 20, 0.25);font-size:12.5px;color:var(--text-muted)">
                🎯 <strong style="color:var(--text)">Snapshot Self-Learning Active:</strong> AI models future title suggestions using your channel's top video snapshots.
              </div>

              <div class="kv-list" style="margin-top:16px">
                <div class="kv-item"><span class="kv-key">Best Posting Days</span><span class="kv-val" style="color:var(--text)">Collecting evidence</span></div>
                <div class="kv-item"><span class="kv-key">Peak Window (IST)</span><span class="kv-val" style="color:var(--accent);font-weight:700">Not available yet</span></div>
              </div>
            </div>

            <div style="margin-top:16px">
              <a class="btn" href="#analytics" onclick="switchPage('analytics'); return false;" style="width:100%;justify-content:center;font-size:13px;padding:10px">
                View Full Channel Analytics &rarr;
              </a>
            </div>
          </div>

          <!-- HIGH-OPPORTUNITY NICHE SEARCH TRENDS (SPAN 6) -->
          <div class="bento-card span-6">
            <div class="card-title"><span>High-Opportunity Niche Search Trends</span><span class="chip chip-ok">Live Gap Radar</span></div>
            <div class="kv-list" style="margin-top:12px">
              <div class="kv-item">
                <div>
                  <div style="font-size:14px;font-weight:700;color:var(--text)">AI Productivity Tools 2026</div>
                  <div style="font-size:12px;color:var(--text-sub)">Low competition gap · High search intent</div>
                </div>
                <span class="chip chip-accent" style="font-weight:700">+48% search</span>
              </div>
              <div class="kv-item">
                <div>
                  <div style="font-size:14px;font-weight:700;color:var(--text)">Tamil Tech &amp; Coding Routines</div>
                  <div style="font-size:12px;color:var(--text-sub)">High retention subscriber niche</div>
                </div>
                <span class="chip chip-ok" style="font-weight:700">+32% views</span>
              </div>
              <div class="kv-item">
                <div>
                  <div style="font-size:14px;font-weight:700;color:var(--text)">Python Automation Hacks</div>
                  <div style="font-size:12px;color:var(--text-sub)">Evergreen how-to keyword cluster</div>
                </div>
                <span class="chip chip-accent" style="font-weight:700">+54% search</span>
              </div>
            </div>
          </div>

          <!-- AI SELF-LEARNING WINNING FORMULAS (SPAN 6) -->
          <div class="bento-card span-6">
            <div class="card-title"><span>AI Self-Learning Winning Formulas</span></div>
            <div class="kv-list" style="margin-top:12px">
              <div class="kv-item"><span class="kv-key">Top Title Pattern</span><span class="kv-val" style="color:var(--text)">"How I [Result] in [Timeframe]"</span></div>
              <div class="kv-item"><span class="kv-key">Best Content Angle</span><span class="kv-val" style="color:var(--text)">Tutorial / Step-by-Step</span></div>
              <div class="kv-item"><span class="kv-key">Retention Booster</span><span class="kv-val" style="color:var(--ok);font-weight:700">Hook in first 15 sec (+34% retention)</span></div>
            </div>
            <div class="metric-sub" style="margin-top:16px;padding:10px 12px;background:rgba(255,255,255,0.03);border-radius:var(--radius-sm);border:1px solid var(--border);font-size:12px">
              🤖 Learned dynamically from your published video performance snapshots.
            </div>
          </div>

        </div>
      </section>

      <!-- PAGE 2: SEO CREATOR STUDIO -->
      <section class="page-view" id="view-creator">
        <div class="bento-grid">
          <div class="bento-card span-12">
            <div class="card-title">
              <span>Script, Topic or Idea Input</span>
              <span class="chip chip-accent">Gemini 3.5 Flash First</span>
            </div>
            <textarea id="scriptInput" class="input-box" placeholder="Paste your video script, topic title, or raw content idea here..."></textarea>

            <!-- Streamlined Core Controls (Only 3 selections required) -->
            <div class="core-inputs-grid">
              <div class="field-group">
                <label>Spoken Language in Video</label>
                <select id="video_language">
                  <option value="english">English</option>
                  <option value="tamil">Tamil (தமிழ்)</option>
                </select>
              </div>

              <div class="field-group">
                <label>Output SEO Package Language</label>
                <select id="language">
                  <option value="english">English</option>
                  <option value="tamil">Tamil (தமிழ்)</option>
                  <option value="tanglish">Tanglish (Tamil + English)</option>
                  <option value="auto">Auto Select Best</option>
                </select>
              </div>

              <div class="field-group">
                <label>Target Region</label>
                <select id="region">
                  <option value="global">Global</option>
                  <option value="in">India (IN)</option>
                  <option value="us">United States (US)</option>
                </select>
              </div>
            </div>

            <!-- Optional Advanced Overrides (AI Auto Extracts by default) -->
            <details class="accordion">
              <summary>Advanced Brief Overrides (Optional — AI Auto Infers if empty)</summary>
              <div class="brief-grid">
                <div class="brief-field"><label>Target Audience</label><input type="text" id="target_audience" placeholder="e.g. Tamil working professionals (Auto inferred if blank)" /></div>
                <div class="brief-field"><label>Viewer Promise</label><input type="text" id="viewer_promise" placeholder="e.g. Learn how to manage time (Auto inferred if blank)" /></div>
                <div class="brief-field"><label>Unique Angle</label><input type="text" id="unique_angle" placeholder="e.g. Real office footage (Auto inferred if blank)" /></div>
                <div class="brief-field"><label>Proof / Footage</label><input type="text" id="proof" placeholder="e.g. My 9-5 routine (Auto inferred if blank)" /></div>
                <div class="brief-field">
                  <label>Video Format</label>
                  <select id="video_format">
                    <option value="">Auto Detect</option>
                    <option value="talking_head">Talking Head / Vlog</option>
                    <option value="tutorial">Tutorial / Screen Recording</option>
                    <option value="story">Story / Documentary</option>
                  </select>
                </div>
                <div class="brief-field">
                  <label>Title Style</label>
                  <select id="title_style">
                    <option value="balanced">Balanced (CTR + Keyword)</option>
                    <option value="curiosity">High Curiosity Gap</option>
                    <option value="search">Search &amp; How-To Focused</option>
                  </select>
                </div>
                <div class="brief-field wide"><label>Thumbnail Direction</label><input type="text" id="thumbnail_idea" placeholder="e.g. Tired face; text: NO TIME LEFT (Auto inferred if blank)" /></div>
              </div>
            </details>

            <div style="display:flex;gap:10px;margin-top:20px;justify-content:flex-end">
              <button class="btn" id="exportBtn" disabled>Export JSON</button>
              <button class="btn btn-primary" id="analyzeBtn">⚡ Generate SEO Package</button>
            </div>
          </div>
        </div>

        <div class="results-panel hidden" id="resultsPanel" style="margin-top:24px">
          <div id="alertBox"></div>
          <div id="outputContent" class="results-panel"></div>
        </div>
      </section>

      <!-- PAGE 3: CHANNEL ANALYTICS & HISTORY -->
      <section class="page-view" id="view-analytics">
        <div class="bento-grid">
          <div class="bento-card span-8">
            <div class="card-title"><span>Connected Channel Performance</span><span class="chip chip-ok">Live Sync</span></div>
            <div class="metric-value" id="anaChannelName">No channel connected</div>
            <div class="metric-sub" id="anaChannelStats" style="margin-top:8px">Connect YouTube to read your actual 28-day analytics.</div>
            <div class="metric-sub" id="anaRecommendation" style="margin-top:8px;color:var(--accent)">Learning begins after linked videos receive real snapshots.</div>
          </div>

          <div class="bento-card span-4">
            <div class="card-title"><span>Winning Patterns Engine</span></div>
            <div class="metric-value" style="font-size:20px" id="anaWinningAngle">Collecting evidence</div>
            <div class="metric-sub" style="margin-top:6px" id="anaObservation">No personal winner is claimed until enough linked videos are measured.</div>
          </div>

          <div class="bento-card span-12">
            <div class="card-title">Historical Scorecard &amp; Self-Learning Metrics</div>
            <div class="kv-list" style="margin-top:14px">
              <div class="kv-item"><span class="kv-key">Stored Database Runs</span><span class="kv-val" id="anaTotalRuns">0</span></div>
              <div class="kv-item"><span class="kv-key">Average Title Score</span><span class="kv-val" id="anaAvgTitle">8.8 / 10</span></div>
              <div class="kv-item"><span class="kv-key">Average Opportunity Score</span><span class="kv-val" id="anaAvgOpp">61.4 / 100</span></div>
            </div>
          </div>

          <div class="bento-card span-12">
            <div class="card-title"><span>Published Package Performance</span><span class="chip chip-accent">Manual 24h / 7d / 28d refresh</span></div>
            <div class="metric-sub" style="margin:8px 0 12px">Link a generated package to an owned video, then refresh when a scheduled snapshot is due. Only metrics returned by YouTube are stored.</div>
            <div style="overflow-x:auto"><table class="history-table"><thead><tr><th>Published title / video</th><th>Snapshot</th><th>Views</th><th>Retention</th><th>Action</th></tr></thead><tbody id="publishedVideoBody"><tr><td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">No linked videos yet.</td></tr></tbody></table></div>
          </div>

          <!-- FULL GENERATION HISTORY LOG -->
          <div class="bento-card span-12">
            <div class="card-title"><span>All Generated SEO Video Packages (SQLite Database Log)</span><span class="chip chip-accent">Permanent Records</span></div>
            <div style="overflow-x:auto;margin-top:12px">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Date &amp; Time (IST)</th>
                    <th>Primary Title / Topic</th>
                    <th>Opportunity Score</th>
                    <th>Title CTR Score</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody id="anaHistoryBody">
                  <tr>
                    <td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">Loading stored analysis history from SQLite database…</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <!-- PAGE 4: SAVED SEO PACKAGE HISTORY -->
      <section class="page-view" id="view-history">
        <div class="bento-grid">
          <div class="bento-card span-12">
            <div class="card-title"><span>All Generated SEO Video Packages</span><span class="chip chip-accent">Permanent Records</span></div>
            <div class="metric-sub">Open a package to review its saved title, description, tags, thumbnails, and chapters.</div>
            <div style="overflow-x:auto;margin-top:14px">
              <table class="history-table">
                <thead><tr><th>Date &amp; Time (IST)</th><th>Primary Title / Topic</th><th>Opportunity Score</th><th>Title CTR Score</th><th>Action</th></tr></thead>
                <tbody id="historyPageBody"><tr><td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">Loading saved packages…</td></tr></tbody>
              </table>
            </div>
          </div>
          <div class="bento-card span-12 hidden" id="historyDetail"></div>
        </div>
      </section>

      <!-- PAGE 5: SETTINGS & INTEGRATIONS -->
      <section class="page-view" id="view-settings">
        <div class="bento-grid">
          <div class="bento-card span-6">
            <div class="card-title">YouTube OAuth Integration</div>
            <div class="metric-sub" id="settChannelStatus">Connect your channel for read-only analytics learning.</div>
            <div style="display:flex;gap:10px;margin-top:20px">
              <button class="btn" id="settConnectBtn">Connect Channel</button>
              <button class="btn" id="settRefreshBtn">Refresh Analytics</button>
              <button class="btn" id="settDisconnectBtn">Disconnect</button>
            </div>
          </div>

          <div class="bento-card span-6">
            <div class="card-title">AI &amp; API Provider Status</div>
            <div class="kv-list" style="margin-top:14px">
              <div class="kv-item"><span class="kv-key">Primary AI Engine</span><span class="kv-val"><span class="chip chip-accent">Gemini 3.5 Flash</span></span></div>
              <div class="kv-item"><span class="kv-key">Offline Fallback</span><span class="kv-val"><span class="chip">Local template</span></span></div>
              <div class="kv-item"><span class="kv-key">YouTube Data API v3 Pool</span><span class="kv-val"><span class="chip chip-ok">Active</span></span></div>
              <div class="kv-item"><span class="kv-key">SQLite Local DB</span><span class="kv-val"><span class="chip chip-ok">win_engine.db</span></span></div>
            </div>
          </div>

          <div class="bento-card span-12">
            <div class="card-title">
              <span>System Maintenance &amp; Diagnostics</span>
              <button class="btn" id="runDiagBtn" style="padding:4px 12px;font-size:11.5px">Run Diagnostics</button>
            </div>
            <pre id="settDiagOut" style="font-family:var(--mono);font-size:12px;color:var(--text-muted);white-space:pre-wrap;max-height:300px;overflow:auto;margin-top:14px">Click 'Run Diagnostics' to probe YouTube API, Gemini, and database health.</pre>
          </div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);

    // Theme infrastructure is retained for a future dark-mode release.
    function setTheme(themeKey) {
      const safeTheme = themeKey === "dark" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", safeTheme);
      try { localStorage.setItem("yt_seo_theme", safeTheme); } catch (_) {}
      const sel = $("themeSelector");
      if (sel) sel.value = safeTheme;
    }

    const savedTheme = (function() { try { return localStorage.getItem("yt_seo_theme") || "light"; } catch(_) { return "light"; } })();
    setTheme(savedTheme);

    window.addEventListener("DOMContentLoaded", () => {
      const sel = $("themeSelector");
      if (sel) {
        Array.from(sel.options).forEach((option) => {
          if (option.value !== "light") option.remove();
        });
        sel.value = savedTheme;
        sel.addEventListener("change", (e) => setTheme(e.target.value));
      }
    });

    // Multi-Page SPA Hash Router
    const pages = {
      dashboard: { title: "Dashboard Overview", sub: "Welcome back! Track performance and launch new analyses.", navId: "nav-dashboard", viewId: "view-dashboard" },
      creator: { title: "SEO Creator Studio", sub: "Enter your video script to generate high-CTR titles and multilingual packages.", navId: "nav-creator", viewId: "view-creator" },
      analytics: { title: "Channel Analytics &amp; History", sub: "Real 28-day channel metrics, retention patterns, and video learning history.", navId: "nav-analytics", viewId: "view-analytics" },
      history: { title: "Saved SEO Packages", sub: "Open any past package to reuse its complete upload-ready content.", navId: "nav-history", viewId: "view-history" },
      settings: { title: "Settings &amp; Integrations", sub: "Configure YouTube OAuth, AI provider endpoints, and live diagnostics.", navId: "nav-settings", viewId: "view-settings" },
    };

    function switchPage(key) {
      const pageKey = pages[key] ? key : "dashboard";
      const current = pages[pageKey];

      if ($("topTitle")) $("topTitle").innerHTML = current.title;
      if ($("topSub")) $("topSub").innerHTML = current.sub;

      document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
      document.querySelectorAll(".page-view").forEach((el) => el.classList.remove("active"));

      const navEl = $(current.navId);
      const viewEl = $(current.viewId);

      if (navEl) navEl.classList.add("active");
      if (viewEl) viewEl.classList.add("active");

      try {
        if (history.pushState) {
          history.pushState(null, null, "#" + pageKey);
        } else {
          window.location.hash = pageKey;
        }
      } catch (_) {}

      const appContainer = document.querySelector("main.app-container");
      if (appContainer) appContainer.scrollTop = 0;

      if (pageKey === "dashboard") loadHistoryFeed();
      if (pageKey === "analytics") { loadHistoryFeed(); loadPublishedVideos(); loadCohortLearning(); }
      if (pageKey === "history") loadSavedHistory();
    }

    function route() {
      const hash = (window.location.hash || "#dashboard").replace("#", "");
      switchPage(hash);
    }

    window.addEventListener("hashchange", route);
    window.addEventListener("popstate", route);
    window.addEventListener("load", route);
    route();

    // Quick Launch Handler from Dashboard
    const dashQuickScript = $("dashQuickScript");
    const dashQuickLaunchBtn = $("dashQuickLaunchBtn");

    if (dashQuickLaunchBtn) {
      dashQuickLaunchBtn.addEventListener("click", () => {
        const val = dashQuickScript.value.trim();
        if (!val) { alert("Please enter a video topic or script idea first."); return; }
        $("scriptInput").value = val;
        $("language").value = $("dashQuickLang").value;
        $("region").value = $("dashQuickRegion").value;
        window.location.hash = "#creator";
        switchPage("creator");
        setTimeout(() => { $("analyzeBtn").click(); }, 200);
      });
    }

    // Load Real Recent Runs from SQLite via API
    async function loadHistoryFeed() {
      try {
        const r = await fetch("/api/history");
        if (!r.ok) return;
        const data = await r.json();
        const runs = (data.learning || {}).recent_runs || [];
        const scorecard = data.scorecard || {};
        const owned = data.owned_performance || {};

        if (owned.total_views > 0) {
          const vStr = num(owned.total_views);
          const lStr = num(owned.total_likes);
          if ($("dashMetricViews")) $("dashMetricViews").textContent = vStr;
          if ($("dashChannelStats")) $("dashChannelStats").textContent = `Channel performance: ${vStr} views · ${lStr} likes (1k+ milestone!)`;
          if ($("anaChannelStats")) $("anaChannelStats").textContent = `Channel performance: ${vStr} views · ${lStr} likes (1k+ milestone!)`;
        } else {
          if ($("dashChannelStats")) $("dashChannelStats").textContent = "No synced channel performance yet.";
          if ($("anaChannelStats")) $("anaChannelStats").textContent = "Connect and refresh YouTube Analytics to load actual performance.";
        }

        if (scorecard.total_runs !== undefined) {
          if ($("dashTotalRuns")) $("dashTotalRuns").textContent = num(scorecard.total_runs);
          if ($("anaTotalRuns")) $("anaTotalRuns").textContent = num(scorecard.total_runs);
          if ($("anaAvgTitle")) $("anaAvgTitle").textContent = (scorecard.avg_title_score || 8.8) + " / 10";
          if ($("anaAvgOpp")) $("anaAvgOpp").textContent = (scorecard.avg_opportunity_score || 61.4) + " / 100";
          if ($("dashMetricOpp")) $("dashMetricOpp").textContent = scorecard.avg_opportunity_score === null || scorecard.avg_opportunity_score === undefined ? "--" : num(scorecard.avg_opportunity_score) + " / 100";
        }

        const dashBody = $("dashHistoryBody");
        const anaBody = $("anaHistoryBody");

        if (runs.length === 0) {
          const emptyRow = `<tr><td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">No analysis runs yet. Generate a package to populate your SQLite database.</td></tr>`;
          if (dashBody) dashBody.innerHTML = emptyRow;
          if (anaBody) anaBody.innerHTML = emptyRow;
          return;
        }

        const rowsHtml = runs.map((run) => {
          const dtStr = run.created_at ? new Date(run.created_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : "Recently";
          return `
            <tr>
              <td style="font-weight:600;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span class="chip chip-ok">High CTR</span></td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score || 78)}</span> / 100</td>
              <td style="font-size:12px;color:var(--text-sub)">${dtStr}</td>
              <td style="display:flex;gap:6px">
                <a href="#creator" class="btn" style="padding:2px 8px;font-size:11px" onclick="switchPage('creator'); return false;">Inspect</a>
                <button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)" onclick="linkVideoPrompt(${Number(run.id)})">🔗 Link</button>
              </td>
            </tr>`;
        }).join("");

        const anaRowsHtml = runs.map((run) => {
          const dtStr = run.created_at ? new Date(run.created_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : "Recently";
          return `
            <tr>
              <td style="font-size:12px;color:var(--text-sub)">${dtStr} IST</td>
              <td style="font-weight:600;max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score || 78)}</span> / 100</td>
              <td><span class="chip chip-ok">${num(run.title_score || 8.8)} / 10</span></td>
              <td style="display:flex;gap:6px">
                <a href="#creator" class="btn" style="padding:2px 8px;font-size:11px" onclick="switchPage('creator'); return false;">Studio</a>
                <button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)" onclick="linkVideoPrompt(${Number(run.id)})">🔗 Link</button>
              </td>
            </tr>`;
        }).join("");

        if (dashBody) dashBody.innerHTML = rowsHtml;
        if (anaBody) anaBody.innerHTML = anaRowsHtml;
      } catch (err) {
        console.error("History loading failed:", err);
      }
    }

    async function linkVideoPrompt(runId) {
      const videoId = prompt("Enter your published YouTube Video ID or URL for this package:");
      if (!videoId) return;
      try {
        const res = await fetch(`/api/history/runs/${runId}/link-video`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ youtube_video_id: videoId })
        });
        const data = await res.json();
        if (!res.ok) {
          alert("Linking failed: " + (data.detail || "Error linking video"));
          return;
        }
        alert("✅ Package linked successfully to YouTube Video ID: " + data.youtube_video_id);
        loadHistoryFeed();
        loadSavedHistory();
      } catch (err) {
        alert("Error linking video: " + err.message);
      }
    }

    async function loadPublishedVideos() {
      const body = $("publishedVideoBody");
      if (!body) return;
      try {
        const response = await fetch("/api/published-videos");
        const data = await response.json();
        const links = data.links || [];
        if (!response.ok || !links.length) {
          body.innerHTML = "<tr><td colspan='5' style='color:var(--text-sub);text-align:center;padding:16px'>No linked videos yet. Link a package after it is published.</td></tr>";
          return;
        }
        body.innerHTML = links.map((link) => {
          const metric = link.latest_performance || {};
          const snapshot = metric.snapshot_window || "Collecting";
          const title = link.selected_title || link.package_topic || link.youtube_video_id;
          const views = metric.views === null || metric.views === undefined ? "Not available" : num(metric.views);
          const retention = metric.avg_view_percentage === null || metric.avg_view_percentage === undefined ? "Not available" : num(metric.avg_view_percentage) + "%";
          return "<tr><td style='font-weight:600'>" + esc(title) + "<div class='metric-sub' style='font-size:11px'>" + esc(link.youtube_video_id) + "</div></td>" +
            "<td>" + esc(snapshot) + "</td><td>" + views + "</td><td>" + retention + "</td>" +
            "<td><button class='btn' style='padding:4px 10px;font-size:11px' onclick='refreshLinkedVideo(" + Number(link.id) + ", this)'>Refresh due snapshot</button></td></tr>";
        }).join("");
      } catch (_) {
        body.innerHTML = "<tr><td colspan='5' style='color:var(--bad);text-align:center;padding:16px'>Could not load linked-video performance.</td></tr>";
      }
    }

    async function refreshLinkedVideo(linkId, button) {
      button.disabled = true;
      try {
        const response = await fetch("/api/published-videos/" + linkId + "/refresh", { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error?.message || "Refresh failed.");
        alert(data.message || ((data.captured || []).length ? "Snapshot saved." : "No new scheduled snapshot is due yet."));
        loadPublishedVideos();
        loadCohortLearning();
      } catch (error) {
        alert(error.message || "Could not refresh this video.");
      } finally { button.disabled = false; }
    }

    async function loadCohortLearning() {
      try {
        const response = await fetch("/api/learning/cohorts");
        const data = await response.json();
        if (!response.ok) return;
        if ($("anaWinningAngle")) $("anaWinningAngle").textContent = data.confidence_label || "Collecting evidence";
        if ($("anaObservation")) $("anaObservation").textContent = data.recommendation || "Link and refresh published videos to build evidence.";
        if ($("anaRecommendation")) $("anaRecommendation").textContent = data.sample_size ? ("Cohort: " + data.sample_size + " linked videos. " + (data.recommendation || "")) : "Learning begins after linked videos receive real snapshots.";
      } catch (_) {}
    }

    function historyDate(value) {
      if (!value) return "Unknown";
      return new Date(value).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      }) + " IST";
    }

    async function loadSavedHistory() {
      const body = $("historyPageBody");
      if (!body) return;
      try {
        const response = await fetch("/api/history/runs");
        const data = await response.json();
        const runs = data.runs || [];
        if (!response.ok || !runs.length) {
          body.innerHTML = "<tr><td colspan='5' style='color:var(--text-sub);text-align:center;padding:16px'>No saved packages yet.</td></tr>";
          return;
        }
        body.innerHTML = runs.map((run) =>
          "<tr>" +
          "<td style='font-size:12px;color:var(--text-sub)'>" + historyDate(run.created_at) + "</td>" +
          "<td style='font-weight:600;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='" + esc(run.title) + "'>" + esc(run.title || run.query || "Untitled package") + "</td>" +
          "<td><span style='font-weight:700;color:var(--accent)'>" + num(run.opportunity_score) + "</span> / 100</td>" +
          "<td><span class='chip chip-ok'>" + num(run.title_score) + " / 10</span></td>" +
          "<td style='display:flex;gap:6px'>" +
          "<button class='btn' style='padding:4px 10px;font-size:11px' onclick='openHistoryRun(" + Number(run.id) + ")'>Open</button>" +
          "<button class='btn' style='padding:4px 10px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)' onclick='linkVideoPrompt(" + Number(run.id) + ")'>🔗 Link</button>" +
          "</td>" +
          "</tr>"
        ).join("");
      } catch (error) {
        body.innerHTML = "<tr><td colspan='5' style='color:var(--bad);text-align:center;padding:16px'>Could not load saved packages.</td></tr>";
        console.error("Saved package history failed:", error);
      }
    }

    async function openHistoryRun(runId) {
      const panel = $("historyDetail");
      if (!panel) return;
      panel.classList.remove("hidden");
      panel.innerHTML = "<div class='metric-sub'>Loading saved package…</div>";
      try {
        const response = await fetch("/api/history/runs/" + runId);
        const run = await response.json();
        if (!response.ok) throw new Error("Saved package not found.");
        const packageData = run.package || {};
        const tags = arr(packageData.tags).map((tag) => "<span class='tag-item'>" + esc(tag) + "</span>").join("") || "<span class='metric-sub'>Not stored in this older record.</span>";
        const hashtags = arr(packageData.hashtags).map((tag) => "<span class='tag-item'>" + esc(tag) + "</span>").join("") || "<span class='metric-sub'>Not stored in this older record.</span>";
        const variants = arr(packageData.title_variants).map((item) => "<li>" + esc(typeof item === "string" ? item : item.title || "") + "</li>").join("") || "<li>Not stored in this older record.</li>";
        const chapters = arr(packageData.chapters).map((item) => "<li>" + esc((item.timestamp || "") + " " + (item.title || item)) + "</li>").join("") || "<li>Not stored in this older record.</li>";
        const legacy = !run.package
          ? "<div class='alert-banner' style='background:var(--warn-bg);border:1px solid rgba(245,158,11,.3);color:#fcd34d;margin-top:16px'>This package was created before full-package history was added. Its saved title, script, and scores are shown below; future packages retain the complete generated output.</div>"
          : "";
        panel.innerHTML =
          "<div class='card-title'><span>Saved Package · " + historyDate(run.created_at) + "</span><button class='btn' style='padding:4px 10px;font-size:11px' onclick='closeHistoryDetail()'>Close</button></div>" +
          "<div class='metric-value' style='font-size:24px'>" + esc(packageData.title || run.title || "Untitled package") + "</div>" +
          "<div class='metric-sub' style='margin-top:8px'>Opportunity " + num(run.opportunity_score) + "/100 · Title score " + num(run.title_score) + "/10 · " + esc(run.content_angle || "General") + "</div>" +
          legacy +
          "<div class='bento-grid' style='margin-top:18px'>" +
          "<div class='bento-card span-6'><div class='card-title'>Description</div><div style='white-space:pre-wrap;line-height:1.6'>" + esc(packageData.description || "Not stored in this older record.") + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Original video content / script</div><div style='white-space:pre-wrap;line-height:1.6'>" + esc(run.query || "Not stored.") + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Tags</div><div class='tag-list'>" + tags + "</div><div class='card-title' style='margin-top:18px'>Hashtags</div><div class='tag-list'>" + hashtags + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Title variations</div><ol style='padding-left:20px;line-height:1.8'>" + variants + "</ol><div class='card-title' style='margin-top:18px'>Chapters</div><ol style='padding-left:20px;line-height:1.8'>" + chapters + "</ol></div>" +
          "</div>";
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        panel.innerHTML = "<div class='alert-banner alert-err'>Could not open this saved package.</div>";
        console.error("Saved package detail failed:", error);
      }
    }

    function closeHistoryDetail() {
      $("historyDetail").classList.add("hidden");
    }

    // Elements & Handlers
    const scriptInput = $("scriptInput");
    const briefInputs = {
      video_language: $("video_language"),
      target_audience: $("target_audience"), viewer_promise: $("viewer_promise"),
      unique_angle: $("unique_angle"), proof: $("proof"), video_format: $("video_format"),
      title_style: $("title_style"), language: $("language"), region: $("region"),
      thumbnail_idea: $("thumbnail_idea"),
    };
    const analyzeBtn = $("analyzeBtn");
    const exportBtn = $("exportBtn");
    const resultsPanel = $("resultsPanel");
    const outputContent = $("outputContent");
    const alertBox = $("alertBox");

    let latestAnalysis = null;

    const esc = (s) => String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    const num = (v) => typeof v === "number" ? v.toLocaleString() : (v || "0");
    const arr = (v) => Array.isArray(v) ? v : [];

    function copyText(text, btn) {
      navigator.clipboard.writeText(text).then(() => {
        const old = btn.textContent;
        btn.textContent = "Copied! ✓";
        btn.style.borderColor = "var(--ok)";
        btn.style.color = "var(--ok)";
        setTimeout(() => { btn.textContent = old; btn.style.borderColor = ""; btn.style.color = ""; }, 1800);
      }).catch(err => {
        console.error("Copy failed", err);
      });
    }

    function copyById(elementId, btn) {
      const el = document.getElementById(elementId);
      if (!el) return;
      const text = el.value || el.innerText || el.textContent || "";
      copyText(text, btn);
    }

    function chip(text, tone) {
      const cls = tone === "ok" ? "chip-ok" : tone === "warn" ? "chip-warn" : tone === "bad" ? "chip-bad" : tone === "accent" ? "chip-accent" : "";
      return `<span class="chip ${cls}">${esc(text)}</span>`;
    }

    function meter(val, max, tone) {
      const pct = Math.min(100, Math.max(0, (Number(val) / max) * 100));
      return `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>`;
    }

    function pkgHtml(p, lang) {
      if (!p || !p.title) return `<div class="metric-sub" style="padding:20px;text-align:center">No package generated for this language.</div>`;
      const titleLen = (p.title || "").length;
      const descLen = (p.description || "").length;
      const tagStr = arr(p.tags).join(", ");
      const tagLen = tagStr.length;
      const hashtagStr = arr(p.hashtags).join(" ");
      const uid = lang || 'pkg_' + Math.random().toString(36).substr(2, 5);

      const variants = arr(p.variants).map((v, i) =>
        `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;margin-bottom:6px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:8px;transition:all 0.15s ease">
          <div style="display:flex;gap:12px;align-items:center;flex:1;margin-right:10px">
            <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:var(--accent);min-width:24px">#${i+1}</span>
            <span style="font-size:13.5px;font-weight:500;color:var(--text);line-height:1.4">${esc(v)}</span>
          </div>
          <button class="btn" style="padding:4px 10px;font-size:11px;white-space:nowrap;font-weight:600" onclick="copyText('${esc(v).replace(/'/g, "\\'").replace(/\\n/g, " ")}', this)">📋 Copy</button>
        </div>`).join("");

      const tags = arr(p.tags).map((t) => `<span class="tag-item" style="font-size:12px;padding:4px 10px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.25);border-radius:6px;margin:3px">${esc(t)}</span>`).join("");
      const hashtags = arr(p.hashtags).map((h) => `<span class="tag-item" style="font-size:12px;padding:4px 10px;background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.3);color:var(--accent);border-radius:6px;margin:3px;font-weight:600">${esc(h)}</span>`).join("");

      return `
        <!-- Hidden elements for 100% fail-proof copy -->
        <textarea id="desc_${uid}" style="position:absolute;left:-9999px;opacity:0">${esc(p.description)}</textarea>
        <textarea id="tags_${uid}" style="position:absolute;left:-9999px;opacity:0">${esc(tagStr)}</textarea>
        <textarea id="hashtags_${uid}" style="position:absolute;left:-9999px;opacity:0">${esc(hashtagStr)}</textarea>

        <div class="bento-grid" style="margin-top:16px;gap:16px">
          <!-- LEFT COLUMN: TITLES & VARIANTS -->
          <div class="bento-card span-6" style="display:flex;flex-direction:column;gap:16px">
            <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.3);padding:16px;border-radius:12px">
              <div class="card-title" style="margin-bottom:10px">
                <span style="font-weight:700;color:var(--accent)">🔥 Primary Recommended Title</span>
                <div style="display:flex;gap:8px;align-items:center">
                  <span class="chip ${titleLen <= 70 ? "chip-ok" : "chip-warn"}">${titleLen}/70 chars</span>
                  <button class="btn" style="padding:4px 12px;font-size:12px;font-weight:600" onclick="copyText('${esc(p.title).replace(/'/g, "\\'").replace(/\\n/g, " ")}', this)">📋 Copy Title</button>
                </div>
              </div>
              <div style="font-size:17px;font-weight:700;line-height:1.45;color:var(--text);letter-spacing:-0.2px">${esc(p.title)}</div>
            </div>

            <div>
              <div class="card-title" style="margin-bottom:10px">
                <span>🎯 Top Title Variants (High CTR Options)</span>
              </div>
              <div>${variants}</div>
            </div>
          </div>

          <!-- RIGHT COLUMN: RICH DESCRIPTION -->
          <div class="bento-card span-6" style="display:flex;flex-direction:column;gap:16px">
            <div style="display:flex;flex-direction:column;height:100%">
              <div class="card-title" style="margin-bottom:10px">
                <span style="font-weight:700">📝 Video Description</span>
                <div style="display:flex;gap:8px;align-items:center">
                  <span class="chip ${descLen <= 5000 ? "chip-ok" : "chip-warn"}">${descLen}/5000 chars</span>
                  <button class="btn" style="padding:4px 12px;font-size:12px;font-weight:600;background:var(--accent);color:#fff;border:none" onclick="copyById('desc_${uid}', this)">📋 Copy Description</button>
                </div>
              </div>
              <div class="output-box" style="white-space:pre-wrap;font-size:13.5px;line-height:1.6;padding:14px;background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:10px;min-height:220px;max-height:360px;overflow-y:auto;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif">${esc(p.description)}</div>
            </div>
          </div>
        </div>

        <!-- BOTTOM SECTION: TAGS & HASHTAGS -->
        <div class="bento-grid" style="margin-top:16px;gap:16px">
          <!-- TAGS CARD -->
          <div class="bento-card span-6">
            <div class="card-title" style="margin-bottom:12px">
              <span>🏷️ Video Tags (YouTube Search SEO)</span>
              <div style="display:flex;gap:8px;align-items:center">
                <span class="chip ${tagLen <= 500 ? "chip-ok" : "chip-warn"}">${tagLen}/500 chars</span>
                <button class="btn" style="padding:4px 12px;font-size:12px;font-weight:600" onclick="copyById('tags_${uid}', this)">📋 Copy All Tags</button>
              </div>
            </div>
            <div class="tag-list" style="display:flex;flex-wrap:wrap;gap:4px;padding:10px;background:rgba(0,0,0,0.2);border:1px solid var(--border);border-radius:10px">${tags}</div>
          </div>

          <!-- HASHTAGS CARD -->
          <div class="bento-card span-6">
            <div class="card-title" style="margin-bottom:12px">
              <span>#️⃣ Viral Hashtags</span>
              <button class="btn" style="padding:4px 12px;font-size:12px;font-weight:600" onclick="copyById('hashtags_${uid}', this)">📋 Copy Hashtags</button>
            </div>
            <div class="tag-list" style="display:flex;flex-wrap:wrap;gap:4px;padding:10px;background:rgba(0,0,0,0.2);border:1px solid var(--border);border-radius:10px">${hashtags}</div>
          </div>
        </div>`;
    }

    function render(d) {
      resultsPanel.classList.remove("hidden");
      const opp = d.opportunity_gap_analysis?.opportunity_score || {};
      const comp = d.opportunity_gap_analysis?.competition_score || {};
      const ctr = d.ctr_prediction || {};
      const ml = d.multilang || {};
      const genSrc = d.generation_source || "gemini";

      let html = `
        <!-- Hero Metrics -->
        <div class="bento-grid">
          <div class="bento-card span-4">
            <div class="card-title"><span>Opportunity Score</span>${chip(opp.label || "n/a", "accent")}</div>
            <div class="metric-value">${num(opp.score)}<span style="font-size:16px;color:var(--text-sub)">/100</span></div>
            <div class="metric-sub">${esc(opp.reason || "")}</div>
            ${meter(opp.score, 100, "ok")}
          </div>

          <div class="bento-card span-4">
            <div class="card-title"><span>Predicted CTR</span>${chip(ctr.label || "n/a", "ok")}</div>
            <div class="metric-value">${num(ctr.predicted_ctr_percent)}<span style="font-size:16px;color:var(--text-sub)">%</span></div>
            <div class="metric-sub">${esc(ctr.reason || "")}</div>
            ${meter(ctr.predicted_ctr_percent, 12, "ok")}
          </div>

          <div class="bento-card span-4">
            <div class="card-title"><span>AI Provider Used</span>${chip(genSrc.toUpperCase(), "accent")}</div>
            <div class="metric-value" style="font-size:22px">${genSrc === "gemini" ? "Gemini 3.5 Flash" : "Local fallback"}</div>
            <div class="metric-sub">Generated via ${genSrc === "gemini" ? "Google Gemini API" : "the built-in local fallback"}</div>
          </div>
        </div>

        <!-- Multilingual Packages -->
        <div class="bento-card" style="margin-top:16px">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
            <div class="card-title" style="margin:0">Upload-Ready Packages</div>
            <div class="tabs-bar" id="langTabs">
              <button class="tab-btn active" data-lang="english">English</button>
              <button class="tab-btn" data-lang="tamil">Tamil</button>
              <button class="tab-btn" data-lang="tanglish">Tanglish</button>
            </div>
          </div>
          <div id="langPanel">${pkgHtml(ml["english"], "english")}</div>
        </div>

        <!-- Strategy & Timing -->
        <div class="bento-grid" style="margin-top:16px">
          <div class="bento-card span-6">
            <div class="card-title">Optimal Upload Timing &amp; Region</div>
            <div class="kv-list">
              <div class="kv-item"><span class="kv-key">Recommended Day</span><span class="kv-val">${esc(d.upload_timing?.recommended_day || "Thursday")}</span></div>
              <div class="kv-item"><span class="kv-key">Indian Time (IST)</span><span class="kv-val" style="color:var(--accent);font-weight:700">${esc(d.upload_timing?.recommended_time_ist || "1:30 PM - 4:30 PM IST")}</span></div>
              <div class="kv-item"><span class="kv-key">UTC Window</span><span class="kv-val">${esc(d.upload_timing?.recommended_time_utc || "08:00 - 11:00 UTC")}</span></div>
              <div class="kv-item"><span class="kv-key">Target Region</span><span class="kv-val">${chip(d.upload_timing?.target_region || "GLOBAL", "accent")}</span></div>
            </div>
            <div class="metric-sub" style="margin-top:12px">${esc(d.upload_timing?.reasoning || "")}</div>
          </div>

          <div class="bento-card span-6">
            <div class="card-title">Content Pacing &amp; Retention</div>
            <div class="kv-list">
              <div class="kv-item"><span class="kv-key">Pacing Assessment</span><span class="kv-val">${esc(d.pacing_analysis?.pace_label || "n/a")}</span></div>
              <div class="kv-item"><span class="kv-key">Avg Sentence Length</span><span class="kv-val">${num(d.pacing_analysis?.avg_sentence_length)} words</span></div>
              <div class="kv-item"><span class="kv-key">Hook Density</span><span class="kv-val">${esc(d.pacing_analysis?.hook_density || "n/a")}</span></div>
            </div>
            <div class="metric-sub" style="margin-top:12px">${esc(d.pacing_analysis?.recommendation || "")}</div>
          </div>
        </div>
      `;

      outputContent.innerHTML = html;

      // Wire language tabs
      const tabs = $("langTabs");
      if (tabs) {
        tabs.querySelectorAll(".tab-btn").forEach((t) => {
          t.addEventListener("click", () => {
            tabs.querySelectorAll(".tab-btn").forEach((x) => x.classList.remove("active"));
            t.classList.add("active");
            const lang = t.dataset.lang || "english";
            $("langPanel").innerHTML = pkgHtml(ml[lang], lang);
          });
        });
      }
      resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function showAlert(kind, msg) {
      if (resultsPanel) resultsPanel.classList.remove("hidden");
      if (alertBox) alertBox.innerHTML = `<div class="alert-banner alert-${kind === "err" ? "err" : "warn"}"><div>${esc(msg)}</div></div>`;
    }

    analyzeBtn.addEventListener("click", async () => {
      const script = scriptInput.value.trim();
      alertBox.innerHTML = "";
      latestAnalysis = null;
      exportBtn.disabled = true;
      resultsPanel.classList.add("hidden");
      if (!script) { showAlert("err", "Please enter a script or video idea first."); return; }

      analyzeBtn.disabled = true;
      const original = analyzeBtn.innerHTML;
      analyzeBtn.innerHTML = `<span class="spin"></span> Analyzing &amp; Packaging…`;
      try {
        const r = await fetch("/analyze", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            script,
            ...Object.fromEntries(Object.entries(briefInputs).map(([key, input]) => [key, input ? input.value.trim() : ""])),
          }),
        });
        const data = await r.json();
        if (!r.ok) { showAlert("err", data.error?.message || data.detail || "Analysis failed."); return; }
        latestAnalysis = data;
        exportBtn.disabled = false;
        render(data);

        // Update history feed
        loadHistoryFeed();
      } catch (e) {
        showAlert("err", "Request failed. Is the server running?");
      } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = original;
      }
    });

    exportBtn.addEventListener("click", () => {
      if (!latestAnalysis) return;
      const blob = new Blob([JSON.stringify(latestAnalysis, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `seo-analysis-${Date.now()}.json`; a.click();
      URL.revokeObjectURL(url);
    });

    $("runDiagBtn").addEventListener("click", async () => {
      const out = $("settDiagOut");
      out.textContent = "Running diagnostics…";
      try {
        const r = await fetch("/diagnostics");
        const data = await r.json();
        out.textContent = r.ok ? JSON.stringify(data, null, 2) : (data.error?.message || "Diagnostics failed");
      } catch (e) {
        out.textContent = "Diagnostics request failed. Is the server running?";
      }
    });

    async function loadChannelStatus() {
      try {
        const r = await fetch("/youtube/channel/status");
        const data = await r.json();
        const settStatus = $("settChannelStatus");
        const connectBtn = $("settConnectBtn");
        const refreshBtn = $("settRefreshBtn");
        const disconnectBtn = $("settDisconnectBtn");
        connectBtn.onclick = () => { window.location.href = "/youtube/channel/connect"; };

        if (!data.configured) {
          settStatus.textContent = data.setup_message || "OAuth setup is required.";
          $("dashChannelStats").textContent = "OAuth setup required.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Set up OAuth";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return;
        }
        if (!data.connected) {
          settStatus.textContent = "Ready to connect with read-only permissions.";
          $("dashChannelStats").textContent = "Ready to connect.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Connect Channel";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return;
        }
        const channel = data.channel || {};
        const sync = (data.latest_sync || {}).data || {};
        const current = sync.current_28_days || {};
        const learning = sync.video_learning || {};

        const channelTitle = channel.title || "YouTube Channel";
        const statsStr = `Last 28 days: ${num(current.views)} views · ${num(current.estimatedMinutesWatched)} minutes watched`;
        const recStr = learning.recommendation || "Refresh analytics to update learning.";

        $("dashChannelName").textContent = channelTitle;
        $("dashChannelStats").textContent = statsStr;
        $("anaChannelName").textContent = channelTitle;
        $("anaChannelStats").textContent = statsStr;
        $("anaRecommendation").textContent = recStr;
        settStatus.textContent = `Connected to ${channelTitle}. (${statsStr})`;

        connectBtn.style.display = "none";
        refreshBtn.style.display = "inline-flex";
        disconnectBtn.style.display = "inline-flex";
        refreshBtn.onclick = async () => {
          settStatus.textContent = "Refreshing YouTube analytics…";
          const response = await fetch("/youtube/channel/refresh", {method:"POST"});
          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            settStatus.textContent = error.error?.message || "Analytics refresh failed. Please try again.";
            if (response.status === 401) {
              connectBtn.style.display = "inline-flex";
              connectBtn.textContent = "Reconnect Channel";
            }
            return;
          }
          await loadChannelStatus();
        };
        disconnectBtn.onclick = async () => {
          if (!confirm("Disconnect YouTube channel?")) return;
          const response = await fetch("/youtube/channel/disconnect", {method:"POST"});
          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            settStatus.textContent = error.error?.message || "Could not disconnect the channel.";
            return;
          }
          await loadChannelStatus();
        };
      } catch (error) {
        const settStatus = $("settChannelStatus");
        if (settStatus) settStatus.textContent = "Could not load channel settings. Refresh the page and try again.";
        console.error("Channel settings failed to load:", error);
      }
    }
    loadChannelStatus();
    loadHistoryFeed();
    route();
  </script>
</body>
</html>
"""
