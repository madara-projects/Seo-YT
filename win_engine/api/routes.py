from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.core.config import get_settings
from win_engine.core.schemas import AnalyzeRequest, AnalyzeResponse
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService
from win_engine.llm import gemini_client
from win_engine.integrations.youtube_channel import YouTubeChannelService

router = APIRouter()

_APP_START = time.time()

_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube SEO Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg: #09090b;
      --bg-soft: #0c0c0f;
      --panel: #111114;
      --panel-2: #161619;
      --border: #1f1f23;
      --border-soft: #27272a;
      --text: #fafafa;
      --muted: #a1a1aa;
      --muted-2: #71717a;
      --accent: #f43f5e;
      --accent-soft: rgba(244, 63, 94, 0.14);
      --ok: #34d399;
      --ok-soft: rgba(52, 211, 153, 0.12);
      --warn: #fbbf24;
      --warn-soft: rgba(251, 191, 36, 0.12);
      --bad: #f87171;
      --bad-soft: rgba(248, 113, 113, 0.12);
      --radius: 14px;
      --radius-sm: 10px;
      --shadow: 0 1px 0 rgba(255,255,255,0.02), 0 8px 30px rgba(0,0,0,0.45);
      --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      --sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
      color-scheme: dark;
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: var(--sans);
      background: var(--bg);
      background-image:
        radial-gradient(60rem 60rem at 85% -10%, rgba(244,63,94,0.07), transparent 60%),
        radial-gradient(50rem 50rem at -10% 0%, rgba(99,102,241,0.06), transparent 55%);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
      letter-spacing: -0.011em;
    }

    .wrap { max-width: 1140px; margin: 0 auto; padding: 0 20px 80px; }

    /* ---------- Top nav ---------- */
    nav {
      position: sticky; top: 0; z-index: 40;
      backdrop-filter: saturate(160%) blur(12px);
      background: rgba(9,9,11,0.72);
      border-bottom: 1px solid var(--border);
    }
    .nav-inner {
      max-width: 1140px; margin: 0 auto; padding: 14px 20px;
      display: flex; align-items: center; gap: 16px; justify-content: space-between;
    }
    .brand { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .logo {
      width: 34px; height: 34px; border-radius: 9px; flex: none;
      display: grid; place-items: center;
      background: linear-gradient(150deg, var(--accent), #b91c4d);
      box-shadow: 0 6px 18px rgba(244,63,94,0.35);
    }
    .logo svg { width: 18px; height: 18px; }
    .brand-text b { font-size: 14.5px; font-weight: 700; letter-spacing: -0.02em; display: block; line-height: 1.1; }
    .brand-text span { font-size: 11px; color: var(--muted-2); }
    .status-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .status {
      display: inline-flex; align-items: center; gap: 7px;
      font-size: 11px; font-weight: 500; color: var(--muted);
      padding: 6px 10px; border: 1px solid var(--border-soft);
      border-radius: 999px; background: var(--panel);
    }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted-2); flex: none; box-shadow: 0 0 0 0 rgba(0,0,0,0); transition: .25s; }
    .dot-ok { background: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); }
    .dot-warn { background: var(--warn); box-shadow: 0 0 0 3px var(--warn-soft); }
    .dot-bad { background: var(--bad); box-shadow: 0 0 0 3px var(--bad-soft); }
    .dot-accent { background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }

    /* ---------- Hero ---------- */
    header.hero { padding: 46px 0 26px; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
      color: var(--accent); padding: 5px 11px; border-radius: 999px;
      border: 1px solid var(--accent-soft); background: var(--accent-soft); margin-bottom: 18px;
    }
    h1.title { margin: 0 0 10px; font-size: 38px; line-height: 1.04; font-weight: 800; letter-spacing: -0.03em; }
    h1.title .grad { background: linear-gradient(120deg,#fff 30%, #a1a1aa); -webkit-background-clip: text; background-clip: text; color: transparent; }
    .lede { margin: 0; max-width: 56ch; color: var(--muted); font-size: 15px; line-height: 1.5; }

    /* ---------- Cards ---------- */
    .card {
      background: linear-gradient(180deg, var(--panel) 0%, var(--bg-soft) 100%);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .card-pad { padding: 20px; }

    /* ---------- Editor / input ---------- */
    .editor-frame {
      border: 1px solid var(--border-soft);
      border-radius: var(--radius);
      background: var(--panel);
      overflow: hidden;
      transition: border-color .2s, box-shadow .2s;
    }
    .editor-frame:focus-within { border-color: rgba(244,63,94,0.55); box-shadow: 0 0 0 4px var(--accent-soft); }
    .editor-top {
      display: flex; align-items: center; gap: 8px;
      padding: 11px 14px; border-bottom: 1px solid var(--border);
      background: var(--panel-2);
    }
    .tl { width: 11px; height: 11px; border-radius: 50%; }
    .tl.r { background: #ff5f57; } .tl.y { background: #febc2e; } .tl.g { background: #28c840; }
    .editor-name { margin-left: 8px; font-size: 12px; color: var(--muted-2); font-family: var(--mono); }
    textarea#script {
      width: 100%; min-height: 168px; resize: vertical; border: none; outline: none;
      background: transparent; color: var(--text);
      padding: 16px; font-size: 15px; line-height: 1.6; font-family: var(--sans);
    }
    textarea#script::placeholder { color: #52525b; }
    .brief-panel { padding: 16px; border-top: 1px solid var(--border); background: var(--bg-soft); }
    .brief-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 13px; flex-wrap: wrap; }
    .brief-head p { margin: 0; font-size: 12px; color: var(--muted-2); }
    .brief-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .brief-field { display: flex; flex-direction: column; gap: 6px; }
    .brief-field.wide { grid-column: span 2; }
    .brief-field label { font-size: 11px; font-weight: 600; color: var(--muted); }
    .brief-field input, .brief-field select {
      width: 100%; border: 1px solid var(--border-soft); outline: none; border-radius: 8px;
      background: var(--panel); color: var(--text); padding: 10px 11px; font: inherit; font-size: 13px;
    }
    .brief-field input:focus, .brief-field select:focus { border-color: rgba(244,63,94,0.65); }
    .brief-field input::placeholder { color: #52525b; }
    .editor-foot {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 12px 14px; border-top: 1px solid var(--border); background: var(--panel-2); flex-wrap: wrap;
    }
    .hint { font-size: 12px; color: var(--muted-2); }
    .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }
    .btn {
      display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
      font-family: var(--sans); font-size: 13.5px; font-weight: 600;
      padding: 9px 15px; border-radius: 10px; border: 1px solid var(--border-soft);
      background: var(--panel); color: var(--text); transition: .16s ease;
    }
    .btn:hover { background: var(--panel-2); transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn:disabled { opacity: .5; cursor: not-allowed; transform: none; }
    .btn-primary {
      background: linear-gradient(180deg, #fb4d68, var(--accent));
      border-color: transparent; color: #fff;
      box-shadow: 0 6px 18px rgba(244,63,94,0.32);
    }
    .btn-primary:hover { box-shadow: 0 8px 24px rgba(244,63,94,0.45); }
    .btn .spin { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.4); border-top-color:#fff; border-radius: 50%; animation: spin .7s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ---------- Sections ---------- */
    .results { margin-top: 30px; display: grid; gap: 22px; }
    .results.hidden { display: none; }
    .sec-head { display: flex; align-items: center; gap: 10px; margin: 6px 2px 14px; }
    .sec-head h2 { margin: 0; font-size: 13px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
    .sec-head .rule { flex: 1; height: 1px; background: linear-gradient(90deg, var(--border-soft), transparent); }
    .label { font-size: 10.5px; font-weight: 600; letter-spacing: .13em; text-transform: uppercase; color: var(--muted-2); }
    .metric { font-size: 30px; font-weight: 800; letter-spacing: -0.03em; line-height: 1.05; margin: 8px 0 2px; }
    .metric.sm { font-size: 20px; }
    .sub { font-size: 12.5px; color: var(--muted-2); line-height: 1.45; }

    /* ---------- Bento ---------- */
    .bento { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .tile { grid-column: span 4; background: linear-gradient(180deg, var(--panel), var(--bg-soft)); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; transition: .18s; position: relative; overflow: hidden; }
    .tile:hover { border-color: var(--border-soft); transform: translateY(-2px); }
    .tile-6 { grid-column: span 6; } .tile-8 { grid-column: span 8; } .tile-12 { grid-column: span 12; }
    .tile-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .glow { position: absolute; inset: 0; background: radial-gradient(20rem 12rem at 80% -20%, var(--accent-soft), transparent 70%); pointer-events: none; opacity: .8; }

    /* ---------- Chips / badges ---------- */
    .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border-soft); color: var(--muted); background: var(--panel-2); }
    .chip-ok { color: var(--ok); border-color: var(--ok-soft); background: var(--ok-soft); }
    .chip-warn { color: var(--warn); border-color: var(--warn-soft); background: var(--warn-soft); }
    .chip-bad { color: var(--bad); border-color: var(--bad-soft); background: var(--bad-soft); }
    .chip-accent { color: var(--accent); border-color: var(--accent-soft); background: var(--accent-soft); }
    .chips { display: flex; flex-wrap: wrap; gap: 7px; }
    .trend { display: inline-flex; align-items: center; gap: 3px; font-size: 11.5px; font-weight: 700; padding: 3px 9px; border-radius: 999px; font-family: var(--mono); }
    .trend-ok { color: var(--ok); background: var(--ok-soft); }
    .trend-bad { color: var(--bad); background: var(--bad-soft); }
    .trend-muted { color: var(--muted-2); background: var(--panel-2); }

    /* ---------- Meters ---------- */
    .meter { height: 8px; border-radius: 999px; background: #1c1c20; overflow: hidden; margin-top: 8px; }
    .meter-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), #fb7185); transition: width .6s cubic-bezier(.2,.7,.2,1); }
    .meter-fill.ok { background: linear-gradient(90deg, #059669, var(--ok)); }
    .meter-fill.warn { background: linear-gradient(90deg, #d97706, var(--warn)); }
    .meter-fill.bad { background: linear-gradient(90deg, #dc2626, var(--bad)); }

    /* ---------- Tabs ---------- */
    .tabs { display: inline-flex; gap: 4px; padding: 4px; border-radius: 12px; background: var(--panel-2); border: 1px solid var(--border); }
    .tab { border: none; background: transparent; color: var(--muted); font-family: var(--sans); font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 9px; cursor: pointer; transition: .16s; }
    .tab:hover { color: var(--text); }
    .tab.active { background: var(--accent); color: #fff; box-shadow: 0 4px 12px rgba(244,63,94,0.3); }

    /* ---------- Key-value ---------- */
    .kv { display: flex; flex-direction: column; gap: 10px; }
    .kv-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding-bottom: 10px; border-bottom: 1px dashed var(--border); }
    .kv-row:last-child { border-bottom: none; padding-bottom: 0; }
    .kv-k { font-size: 12.5px; color: var(--muted); }
    .kv-v { font-size: 13px; font-weight: 600; text-align: right; }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }

    /* ---------- Code block (copyable) ---------- */
    .codebox { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; font-size: 13.5px; line-height: 1.55; }
    .pkg-title { font-size: 17px; font-weight: 700; letter-spacing: -0.02em; }
    .pkg-desc { color: var(--muted); font-size: 13.5px; line-height: 1.6; white-space: pre-wrap; }
    .taglist { display: flex; flex-wrap: wrap; gap: 6px; }
    .tag { font-size: 12px; padding: 4px 9px; border-radius: 7px; background: var(--panel-2); border: 1px solid var(--border-soft); color: var(--muted); font-family: var(--mono); }
    .variant { display: flex; gap: 10px; align-items: baseline; padding: 9px 0; border-bottom: 1px dashed var(--border); }
    .variant:last-child { border-bottom: none; }
    .variant-n { font-size: 11px; color: var(--muted-2); font-family: var(--mono); flex: none; width: 18px; }

    /* ---------- Feed ---------- */
    .feed { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
    .feed-card { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 16px; background: var(--panel); transition: .16s; }
    .feed-card:hover { border-color: var(--border-soft); transform: translateY(-2px); }
    .feed-card h4 { margin: 0 0 8px; font-size: 14.5px; font-weight: 700; line-height: 1.3; }
    .feed-meta { font-size: 12px; color: var(--muted-2); margin: 3px 0; }
    .feed-reason { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border); font-size: 12.5px; color: var(--muted); line-height: 1.45; }

    ul.clean { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
    ul.clean li { font-size: 13px; color: var(--muted); padding-left: 18px; position: relative; line-height: 1.45; }
    ul.clean li::before { content: ""; position: absolute; left: 2px; top: 8px; width: 5px; height: 5px; border-radius: 50%; background: var(--accent); }

    .banner { border-radius: var(--radius); padding: 14px 16px; font-size: 13px; display: flex; gap: 11px; align-items: flex-start; }
    .banner-warn { background: var(--warn-soft); border: 1px solid var(--warn-soft); color: #fcd34d; }
    .banner-err { background: var(--bad-soft); border: 1px solid var(--bad-soft); color: #fca5a5; }
    .banner svg { flex: none; margin-top: 1px; }

    pre#diagOut { white-space: pre-wrap; font-family: var(--mono); font-size: 12.5px; color: var(--muted); margin: 0; max-height: 380px; overflow: auto; }

    .fade { animation: fade .45s cubic-bezier(.2,.7,.2,1) both; }
    @keyframes fade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

    @media (max-width: 860px) {
      .tile, .tile-6, .tile-8 { grid-column: span 12 !important; }
      .grid-3 { grid-template-columns: 1fr; }
      h1.title { font-size: 30px; }
    }
    @media (max-width: 560px) {
      .grid-2 { grid-template-columns: 1fr; }
      .brief-grid { grid-template-columns: 1fr; }
      .brief-field.wide { grid-column: span 1; }
      .nav-inner { flex-direction: column; align-items: flex-start; }
    }
  </style>
</head>
<body>
  <nav>
    <div class="nav-inner">
      <div class="brand">
        <div class="logo">
          <svg viewBox="0 0 24 24" fill="#fff"><path d="M21.6 7.2a2.7 2.7 0 0 0-1.9-1.9C18 5 12 5 12 5s-6 0-7.7.3A2.7 2.7 0 0 0 2.4 7.2 28 28 0 0 0 2 12a28 28 0 0 0 .4 4.8 2.7 2.7 0 0 0 1.9 1.9C6 19 12 19 12 19s6 0 7.7-.3a2.7 2.7 0 0 0 1.9-1.9A28 28 0 0 0 22 12a28 28 0 0 0-.4-4.8ZM10 15V9l5 3-5 3Z"/></svg>
        </div>
        <div class="brand-text">
          <b>YouTube SEO Analyzer</b>
          <span>Local creator engine</span>
        </div>
      </div>
      <div class="status-group" id="statusGroup">
        <span class="status" id="st-health"><span class="dot" id="dot-health"></span> Health</span>
        <span class="status" id="st-ready"><span class="dot" id="dot-ready"></span> Ready</span>
        <span class="status" id="st-engine"><span class="dot" id="dot-engine"></span> Engine</span>
      </div>
    </div>
  </nav>

  <div class="wrap">
    <header class="hero">
      <span class="eyebrow"><span class="dot dot-accent"></span> AI SEO Packaging</span>
      <h1 class="title"><span class="grad">Turn a script into an upload-ready package.</span></h1>
      <p class="lede">Paste your video script or idea. Get titles, descriptions, tags and hashtags in English, Tamil &amp; Tanglish — plus competitor-aware strategy and risk analysis.</p>
    </header>

    <div class="editor-frame">
      <div class="editor-top">
        <span class="tl r"></span><span class="tl y"></span><span class="tl g"></span>
        <span class="editor-name">script.md</span>
      </div>
       <textarea id="script" placeholder="e.g. My video is about my daily office life vlog and personal experiences..."></textarea>
      <div class="brief-panel">
        <div class="brief-head">
          <span class="label">Creator brief</span>
          <p>Add these details for titles that match the real video. All fields are optional, but more detail gives better output.</p>
        </div>
        <div class="brief-grid">
          <div class="brief-field">
            <label for="targetAudience">Who is this video for?</label>
            <input id="targetAudience" placeholder="e.g. Tamil working professionals aged 20–30" />
          </div>
          <div class="brief-field">
            <label for="viewerPromise">What will the viewer get?</label>
            <input id="viewerPromise" placeholder="e.g. Feel understood and learn how I manage my time" />
          </div>
          <div class="brief-field">
            <label for="uniqueAngle">What makes this video different?</label>
            <input id="uniqueAngle" placeholder="e.g. Real office footage, not a perfect productivity routine" />
          </div>
          <div class="brief-field">
            <label for="proof">Your proof, footage, or experience</label>
            <input id="proof" placeholder="e.g. My commute, workday, and evening creator routine" />
          </div>
          <div class="brief-field">
            <label for="videoFormat">Video format</label>
            <select id="videoFormat">
              <option value="">Choose a format</option><option>Vlog</option><option>Tutorial</option><option>Short</option><option>Review</option><option>Story</option><option>Challenge</option>
            </select>
          </div>
          <div class="brief-field">
            <label for="titleStyle">Preferred title style</label>
            <select id="titleStyle"><option value="balanced">Balanced</option><option value="searchable">Searchable</option><option value="curiosity-led">Curiosity-led</option></select>
          </div>
          <div class="brief-field">
            <label for="language">Output language</label>
            <select id="language"><option value="english">English</option><option value="tamil">Tamil</option><option value="tanglish">Tanglish</option></select>
          </div>
          <div class="brief-field">
            <label for="region">Target region</label>
            <select id="region"><option value="global">Global</option><option value="india">India</option><option value="tamil nadu">Tamil Nadu</option><option value="sri lanka">Sri Lanka</option><option value="gulf">Gulf</option></select>
          </div>
          <div class="brief-field wide">
            <label for="thumbnailIdea">Optional thumbnail idea</label>
            <input id="thumbnailIdea" placeholder="e.g. Tired face in an office elevator; text: NO TIME LEFT" />
          </div>
        </div>
      </div>
      <div class="editor-foot">
        <span class="hint" id="charHint">0 characters</span>
        <div class="btn-group">
          <button class="btn" id="channelBtn">Connect YouTube Channel</button>
          <button class="btn" id="diagBtn">Run Diagnostics</button>
          <button class="btn" id="exportBtn" disabled>Export</button>
          <button class="btn btn-primary" id="analyzeBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5L20 7"/></svg>
            Analyze
          </button>
        </div>
      </div>
    </div>

    <div id="alert" style="margin-top:16px; display:none;"></div>
    <div id="channelPanel" class="card card-pad" style="margin-top:16px; display:none;"></div>

    <div class="results hidden" id="results"></div>

    <div id="diagWrap" style="margin-top:22px; display:none;">
      <div class="sec-head"><h2>Diagnostics</h2><span class="rule"></span></div>
      <div class="card card-pad"><pre id="diagOut"></pre></div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    const analyzeBtn = $("analyzeBtn");
    const diagBtn = $("diagBtn");
    const channelBtn = $("channelBtn");
    const channelPanel = $("channelPanel");
    const exportBtn = $("exportBtn");
    const scriptInput = $("script");
    const briefInputs = {
      target_audience: $("targetAudience"), viewer_promise: $("viewerPromise"),
      unique_angle: $("uniqueAngle"), proof: $("proof"), video_format: $("videoFormat"),
      title_style: $("titleStyle"), thumbnail_idea: $("thumbnailIdea"),
      language: $("language"), region: $("region"),
    };
    const results = $("results");
    const alertBox = $("alert");
    const charHint = $("charHint");
    let latestAnalysis = null;

    /* ---------- helpers ---------- */
    const esc = (s) => String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    const num = (v) => (v === 0 || v ? v : "n/a");
    const arr = (v) => Array.isArray(v) ? v : [];

    const TONES = {
      risk: { HIGH: "bad", MEDIUM: "warn", LOW: "ok" },
      strength: { HIGH: "ok", STRONG: "ok", MEDIUM: "warn", LOW: "bad", WEAK: "bad" },
      comp: { UNDERSERVED: "ok", COMPETITIVE: "warn", SATURATED: "bad", STRONG: "ok", WORKABLE: "warn", WEAK: "bad" },
      ctr: { VERY_HIGH: "ok", HIGH: "ok", MEDIUM: "warn", LOW: "bad", VERY_LOW: "bad" },
      verdict: { GREEN: "ok", YELLOW: "warn", RED: "bad" },
    };
    const tone = (v, kind) => (TONES[kind] || {})[String(v || "").toUpperCase()] || "muted";
    const chip = (txt, t) => `<span class="chip chip-${t || "muted"}">${esc(txt)}</span>`;
    const dotChip = (txt, t) => `<span class="chip chip-${t}"><span class="dot dot-${t}"></span>${esc(txt)}</span>`;
    const trend = (n) => {
      const x = Number(n);
      if (isNaN(x)) return "";
      const t = x > 0 ? "ok" : x < 0 ? "bad" : "muted";
      const a = x > 0 ? "▲" : x < 0 ? "▼" : "•";
      return `<span class="trend trend-${t}">${a} ${x > 0 ? "+" : ""}${x}</span>`;
    };
    const meter = (val, max, t) => {
      const pct = Math.max(0, Math.min(100, (Number(val || 0) / (max || 10)) * 100));
      return `<div class="meter"><div class="meter-fill ${t || ""}" style="width:${pct}%"></div></div>`;
    };
    const sec = (title, body) => `<section class="fade"><div class="sec-head"><h2>${title}</h2><span class="rule"></span></div>${body}</section>`;

    /* ---------- status indicators ---------- */
    async function probe(path, dotId, stId) {
      try {
        const r = await fetch(path);
        const ok = r.ok;
        let label = ok ? "ok" : "warn";
        if (path === "/ready") {
          const d = await r.json().catch(() => ({}));
          label = d.status === "ready" ? "ok" : "warn";
        }
        $(dotId).className = "dot dot-" + (ok ? (label) : "bad");
      } catch (e) {
        $(dotId).className = "dot dot-bad";
      }
    }
    probe("/health", "dot-health");
    probe("/ready", "dot-ready");
    probe("/meta", "dot-engine");

    scriptInput.addEventListener("input", () => {
      charHint.textContent = `${scriptInput.value.trim().length} characters`;
    });

    /* ---------- render: metrics bento ---------- */
    function renderMetrics(d) {
      const ctr = d.ctr_prediction || {};
      const gap = d.opportunity_gap_analysis || {};
      const opp = gap.opportunity_score || {};
      const comp = gap.competition || {};
      const verdict = gap.viability_verdict || {};
      const uniq = Number(gap.ai_uniqueness_score || 0);
      const hist = d.historical_comparison || {};
      const perf = d.performance_sync || {};

      return sec("Insight Overview", `
        <div class="bento">
          <div class="tile tile-6">
            <div class="glow"></div>
            <span class="label">Recommended Title</span>
            <div class="metric sm" style="margin-top:10px">${esc(d.title || "n/a")}</div>
            <div class="chips" style="margin-top:12px">
              ${chip("Intent · " + (d.intent || "n/a"), "accent")}
              ${chip("Angle · " + (d.content_angle || "n/a"), "muted")}
            </div>
          </div>
          <div class="tile tile-6">
            <div class="tile-row">
              <span class="label">CTR Prediction</span>
              ${dotChip(ctr.label || "n/a", tone(ctr.label, "ctr"))}
            </div>
            <div class="metric">${num(ctr.score)}<span style="font-size:14px;color:var(--muted-2);font-weight:600">${ctr.predicted_ctr_percent ? "%" : ""}</span></div>
            <div class="sub">${esc(ctr.expected_band || ctr.reason || "")}</div>
          </div>

          <div class="tile">
            <div class="tile-row"><span class="label">Opportunity</span>${dotChip(opp.label || "n/a", tone(opp.label, "comp"))}</div>
            <div class="metric">${num(opp.score)}</div>
            ${meter(opp.score, 100, tone(opp.label, "comp"))}
          </div>
          <div class="tile">
            <div class="tile-row"><span class="label">Competition</span>${dotChip(comp.label || "n/a", tone(comp.label, "comp"))}</div>
            <div class="metric">${num(comp.score)}</div>
            <div class="sub" style="margin-top:8px">${esc(comp.reason || "")}</div>
          </div>
          <div class="tile">
            <div class="tile-row"><span class="label">Title Uniqueness</span>${chip(Math.round(uniq * 100) + "%", uniq >= 0.6 ? "ok" : uniq >= 0.35 ? "warn" : "bad")}</div>
            <div class="metric">${(uniq * 100).toFixed(0)}<span style="font-size:14px;color:var(--muted-2)">%</span></div>
            ${meter(uniq * 100, 100, uniq >= 0.6 ? "ok" : uniq >= 0.35 ? "warn" : "bad")}
          </div>

          <div class="tile tile-8">
            <div class="tile-row">
              <span class="label">Viability Verdict</span>
              ${dotChip((verdict.status || "n/a").toUpperCase(), tone(verdict.status, "verdict"))}
            </div>
            <div class="sub" style="margin-top:10px;font-size:13.5px;color:var(--muted)">${esc(verdict.summary || gap.idea_kill_switch?.reason || "")}</div>
          </div>
          <div class="tile">
            <span class="label">Vs. Your Average</span>
            <div class="kv" style="margin-top:12px">
              <div class="kv-row"><span class="kv-k">Title score</span><span class="kv-v">${trend(hist.title_score_vs_average)}</span></div>
              <div class="kv-row"><span class="kv-k">Opportunity</span><span class="kv-v">${trend(hist.opportunity_score_vs_average)}</span></div>
            </div>
          </div>
        </div>`);
    }

    /* ---------- render: multilang packages ---------- */
    function pkgHtml(p) {
      if (!p || !p.title) return `<div class="sub">No package generated.</div>`;
      const variants = arr(p.variants).map((v, i) =>
        `<div class="variant"><span class="variant-n">${i + 1}</span><span>${esc(v)}</span></div>`).join("");
      const tags = arr(p.tags).map((t) => `<span class="tag">${esc(t)}</span>`).join("");
      const hashtags = arr(p.hashtags).map((h) => `<span class="tag">${esc(h)}</span>`).join("");
      return `
        <div class="grid-2" style="align-items:start">
          <div>
            <span class="label">Primary Title</span>
            <div class="pkg-title" style="margin:8px 0 16px">${esc(p.title)}</div>
            <span class="label">Variants</span>
            <div style="margin-top:8px">${variants}</div>
          </div>
          <div>
            <span class="label">Description</span>
            <div class="codebox pkg-desc" style="margin:8px 0 16px">${esc(p.description)}</div>
            <span class="label">Tags</span>
            <div class="taglist" style="margin:8px 0 14px">${tags}</div>
            <span class="label">Hashtags</span>
            <div class="taglist" style="margin-top:8px">${hashtags}</div>
          </div>
        </div>`;
    }
    function renderLangs(d) {
      const ml = d.multilang || {};
      const langs = [["english", "English"], ["tamil", "Tamil"], ["tanglish", "Tanglish"]].filter(([k]) => ml[k]);
      if (!langs.length) return "";
      const tabs = langs.map(([k, lbl], i) =>
        `<button class="tab ${i === 0 ? "active" : ""}" data-lang="${k}">${lbl}</button>`).join("");
      return sec("Upload-Ready Packages", `
        <div class="card card-pad">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px">
            <div class="tabs" id="langTabs">${tabs}</div>
            <span class="sub">One script → three languages</span>
          </div>
          <div id="langPanel">${pkgHtml(ml[langs[0][0]])}</div>
        </div>`);
    }
    function wireLangTabs(d) {
      const ml = d.multilang || {};
      const tabsEl = $("langTabs");
      if (!tabsEl) return;
      tabsEl.querySelectorAll(".tab").forEach((t) => {
        t.addEventListener("click", () => {
          tabsEl.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
          t.classList.add("active");
          const panel = $("langPanel");
          panel.classList.remove("fade"); void panel.offsetWidth; panel.classList.add("fade");
          panel.innerHTML = pkgHtml(ml[t.dataset.lang]);
        });
      });
    }

    /* ---------- render: content audit ---------- */
    function riskRow(label, value, kind) {
      const t = tone(value, kind);
      return `<div class="kv-row"><span class="kv-k">${label}</span>${dotChip(value || "n/a", t)}</div>`;
    }
    function renderAudit(d) {
      const a = d.content_audit || {};
      const hook = a.hook_audit || {};
      const sim = a.first_30_second_simulator || {};
      const pat = a.pattern_interrupts || {};
      const ret = a.retention_risk || {};
      const align = a.alignment || {};
      const notes = arr(ret.notes).map((n) => `<li>${esc(n)}</li>`).join("");
      return sec("Content Audit", `
        <div class="grid-2">
          <div class="card card-pad">
            <span class="label">Risk Signals</span>
            <div class="kv" style="margin-top:14px">
              ${riskRow("Hook strength", hook.hook_strength, "strength")}
              ${riskRow("First 30s dropoff", sim.predicted_dropoff_risk, "risk")}
              ${riskRow("Engagement", sim.engagement_strength, "strength")}
              ${riskRow("Pattern interrupts", pat.assessment, "strength")}
              ${riskRow("Retention risk", ret.level, "risk")}
              ${riskRow("Package match", align.package_match, "strength")}
            </div>
          </div>
          <div class="card card-pad">
            <span class="label">Notes &amp; Fixes</span>
            <ul class="clean" style="margin-top:14px">${notes || "<li>Opening structure looks solid.</li>"}</ul>
            <div class="chips" style="margin-top:16px">
              ${chip("Keyword in opening: " + (hook.keyword_in_opening ? "yes" : "no"), hook.keyword_in_opening ? "ok" : "warn")}
              ${chip("Stakes present: " + (hook.stakes_present ? "yes" : "no"), hook.stakes_present ? "ok" : "warn")}
            </div>
          </div>
        </div>`);
    }

    /* ---------- render: title optimization ---------- */
    function renderTitleOpt(d) {
      const sv = arr((d.title_optimization || {}).scored_variants);
      if (!sv.length) return "";
      const rows = sv.map((v) => `
        <div class="card card-pad" style="padding:14px 16px">
          <div class="tile-row" style="align-items:flex-start">
            <span style="font-weight:600;font-size:14px;max-width:78%">${esc(v.title || "n/a")}</span>
            <span class="chip chip-${Number(v.score) >= 8 ? "ok" : Number(v.score) >= 6 ? "warn" : "bad"}">${num(v.score)}</span>
          </div>
          <div class="sub" style="margin-top:8px">Est. CTR ${esc(v.estimated_ctr || "n/a")} · ${num(v.character_count)} chars</div>
          ${meter(v.score, 10, Number(v.score) >= 8 ? "ok" : Number(v.score) >= 6 ? "warn" : "bad")}
        </div>`).join("");
      return sec("Title Optimization", `<div class="grid-3">${rows}</div>`);
    }

    /* ---------- render: opportunity gap ---------- */
    function renderGap(d) {
      const gap = d.opportunity_gap_analysis || {};
      const diff = gap.differentiation || {};
      const gaps = arr(gap.keyword_gaps).map((g) => `
        <div class="kv-row">
          <span class="kv-k">${esc(g.keyword || "n/a")}</span>
          <span class="kv-v">${chip(g.gap_strength || "n/a", g.gap_strength === "high" ? "ok" : "warn")}</span>
        </div>`).join("");
      const emphasize = arr(diff.emphasize).map((e) => chip(e, "accent")).join("");
      const avoid = arr(diff.avoid_patterns).map((e) => `<li>${esc(e)}</li>`).join("");
      return sec("Opportunity Gap", `
        <div class="grid-2">
          <div class="card card-pad">
            <span class="label">Keyword Gaps</span>
            <div class="kv" style="margin-top:14px">${gaps || "<div class='sub'>No clear keyword gaps detected.</div>"}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Differentiation</span>
            <div class="sub" style="margin:12px 0;color:var(--muted);font-size:13.5px">${esc(diff.recommendation || "")}</div>
            ${emphasize ? `<span class="label">Emphasize</span><div class="chips" style="margin:8px 0 14px">${emphasize}</div>` : ""}
            ${avoid ? `<span class="label">Avoid</span><ul class="clean" style="margin-top:8px">${avoid}</ul>` : ""}
          </div>
        </div>`);
    }

    /* ---------- render: advanced strategy ---------- */
    function renderStrategy(d) {
      const ch = d.channel_intelligence || {};
      const cg = d.content_graph_strategy || {};
      const exp = d.session_expansion || {};
      const series = arr(cg.series_plan).map((s) => `<li>${esc(s)}</li>`).join("");
      const support = arr(cg.supporting_topics).map((s) => chip(s, "muted")).join("");
      const chapters = arr(d.chapters).map((c) => `<span class="tag">${esc(c.timestamp)} ${esc(c.title)}</span>`).join("");
      return sec("Advanced Strategy", `
        <div class="grid-2">
          <div class="card card-pad">
            <span class="label">Channel Intelligence</span>
            <div class="kv" style="margin-top:14px">
              <div class="kv-row"><span class="kv-k">Dominant size</span><span class="kv-v">${esc(ch.dominant_channel_size || "n/a")}</span></div>
              <div class="kv-row"><span class="kv-k">Video length</span><span class="kv-v">${esc(ch.dominant_video_length || "n/a")}</span></div>
              <div class="kv-row"><span class="kv-k">Packaging</span><span class="kv-v">${esc(ch.dominant_packaging_style || "n/a")}</span></div>
            </div>
            <div class="sub" style="margin-top:12px">${esc(ch.summary || "")}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Content Graph · Hub</span>
            <div class="pkg-title" style="margin:8px 0 12px">${esc(cg.hub_topic || "n/a")}</div>
            ${support ? `<div class="chips" style="margin-bottom:14px">${support}</div>` : ""}
            <span class="label">Series Plan</span>
            <ul class="clean" style="margin-top:8px">${series || "<li>n/a</li>"}</ul>
          </div>
          <div class="card card-pad tile-12" style="grid-column:1/-1">
            <span class="label">Expansion</span>
            <div class="kv" style="margin-top:14px">
              <div class="kv-row"><span class="kv-k">Next video hook</span><span class="kv-v" style="max-width:70%">${esc(exp.next_video_hook || "n/a")}</span></div>
              <div class="kv-row"><span class="kv-k">Pinned comment</span><span class="kv-v" style="max-width:70%">${esc(exp.pinned_comment_funnel || "n/a")}</span></div>
              <div class="kv-row"><span class="kv-k">Playlist</span><span class="kv-v">${esc(exp.playlist_positioning || "n/a")}</span></div>
            </div>
            ${chapters ? `<div style="margin-top:14px"><span class="label">Chapters</span><div class="taglist" style="margin-top:8px">${chapters}</div></div>` : ""}
          </div>
        </div>`);
    }

    /* ---------- render: pacing / language / thumbnail ---------- */
    function renderSignals(d) {
      const p = d.pacing_analysis || {};
      const l = d.language_strategy || {};
      const t = d.thumbnail_strategy || {};
      const ti = d.thumbnail_intelligence || {};
      return sec("Pacing · Language · Thumbnail", `
        <div class="grid-3">
          <div class="card card-pad">
            <span class="label">Pacing</span>
            <div class="metric sm" style="text-transform:capitalize">${esc(p.pace_label || "n/a")}</div>
            <div class="kv" style="margin-top:12px">
              <div class="kv-row"><span class="kv-k">Avg sentence</span><span class="kv-v">${num(p.avg_sentence_length)}</span></div>
              <div class="kv-row"><span class="kv-k">Hook density</span><span class="kv-v">${esc(p.hook_density || "n/a")}</span></div>
            </div>
            <div class="sub" style="margin-top:12px">${esc(p.recommendation || "")}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Language</span>
            <div class="metric sm" style="text-transform:capitalize">${esc(l.primary_language || "n/a")}</div>
            <div class="chips" style="margin-top:12px">${chip(l.multi_language_ready ? "Multi-language ready" : "Single language", l.multi_language_ready ? "ok" : "muted")}</div>
            <div class="sub" style="margin-top:12px">${esc(l.recommendation || "")}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Thumbnail</span>
            <div class="metric sm" style="text-transform:capitalize">${esc((t.style || "n/a").replace(/_/g, " "))}</div>
            <div class="chips" style="margin-top:12px">${chip("Strength: " + (t.competitive_strength || "n/a"), t.competitive_strength === "strong" ? "ok" : "warn")}</div>
            <div class="sub" style="margin-top:12px">${esc(t.recommendation || ti.recommendation || "")}</div>
          </div>
        </div>`);
    }

    /* ---------- render: keywords / entities / timing ---------- */
    function renderGrids(d) {
      const kw = arr(d.keyword_signals).map((k) => `
        <div class="kv-row"><span class="kv-k">${esc(k.keyword || "n/a")}</span>
        <span class="kv-v">${chip("×" + num(k.mentions), "muted")} ${chip(k.strength || "n/a", k.strength === "high" ? "ok" : k.strength === "medium" ? "warn" : "muted")}</span></div>`).join("");
      const ent = arr(d.entity_signals).map((e) => `
        <div class="kv-row"><span class="kv-k">${esc(e.entity || "n/a")}</span>
        <span class="kv-v">${chip(e.type || "n/a", "muted")} ${chip("×" + num(e.mentions), "muted")}</span></div>`).join("");
      const tim = d.upload_timing || {};
      const hours = arr(tim.top_hours).map((h) => `<span class="tag">${esc(h)}:00</span>`).join("");
      const days = arr(tim.top_weekdays).map((w) => `<span class="tag">${esc(w)}</span>`).join("");
      return sec("Signals", `
        <div class="grid-3">
          <div class="card card-pad">
            <span class="label">Keyword Signals</span>
            <div class="kv" style="margin-top:14px">${kw || "<div class='sub'>None yet.</div>"}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Entity Signals</span>
            <div class="kv" style="margin-top:14px">${ent || "<div class='sub'>None yet.</div>"}</div>
          </div>
          <div class="card card-pad">
            <span class="label">Optimal Upload Timing</span>
            <div style="margin-top:14px"><span class="sub">Top hours (UTC)</span><div class="taglist" style="margin:8px 0 14px">${hours || "<span class='sub'>n/a</span>"}</div></div>
            <div><span class="sub">Top weekdays</span><div class="taglist" style="margin-top:8px">${days || "<span class='sub'>n/a</span>"}</div></div>
          </div>
        </div>`);
    }

    /* ---------- render: research feeds ---------- */
    function feedCard(item, opp) {
      const reasons = arr(item.opportunity_reasons).join(" ");
      const meta = opp
        ? `Outlier ${num(item.outlier_score)} · Views/day ${num(item.views_per_day)} · V/sub ${num(item.views_per_subscriber)}`
        : `${esc(item.channel_title || "Unknown")} · ${num(item.view_count)} views · ${num(item.subscriber_count)} subs`;
      return `<div class="feed-card">
        <h4>${esc(item.title || "Untitled")}</h4>
        <div class="feed-meta">${esc(meta)}</div>
        ${item.small_channel_outlier ? `<div class="chips" style="margin-top:8px">${chip("Small-channel outlier", "ok")}</div>` : ""}
        ${reasons ? `<div class="feed-reason">${esc(reasons)}</div>` : ""}
      </div>`;
    }
    function renderResearch(d) {
      const opp = arr(d.top_opportunities);
      const yt = arr(d.youtube_results);
      const queries = arr(d.research_queries);
      const decision = d.research_decision || {};
      if (!opp.length && !yt.length && !queries.length && !decision.recommended_angle) return "";
      let out = "";
      if (decision.recommended_angle) {
        const repeated = arr(decision.repeated_title_patterns).map((item) => `${item.pattern} (${item.count})`).join(", ");
        out += `<div class="card card-pad" style="margin-bottom:18px"><span class="label">Recommended angle</span><div class="metric sm" style="margin-top:8px">${esc(decision.recommended_angle)}</div><div class="sub" style="margin-top:10px">${esc(decision.reason || "")}</div><div class="kv" style="margin-top:14px"><div class="kv-row"><span class="kv-k">Competitor pattern</span><span class="kv-v">${esc(decision.dominant_competitor_pattern || "n/a")}</span></div><div class="kv-row"><span class="kv-k">Patterns to avoid</span><span class="kv-v">${esc(arr(decision.avoid).join(" "))}</span></div>${repeated ? `<div class="kv-row"><span class="kv-k">Repeated patterns</span><span class="kv-v">${esc(repeated)}</span></div>` : ""}</div></div>`;
      }
      if (queries.length) out += `<div style="margin:0 0 18px 2px"><span class="label">Research searches</span><div class="taglist" style="margin-top:10px">${queries.map((item) => chip(`${item.type}: ${item.query}`, "")).join("")}</div></div>`;
      if (opp.length) out += `<div style="margin-bottom:18px"><span class="label" style="margin-left:2px">Top Opportunities</span><div class="feed" style="margin-top:10px">${opp.map((i) => feedCard(i, true)).join("")}</div></div>`;
      if (yt.length) out += `<div><span class="label" style="margin-left:2px">Competitor Results</span><div class="feed" style="margin-top:10px">${yt.map((i) => feedCard(i, false)).join("")}</div></div>`;
      return sec("Competitor Research", out);
    }

    function renderPackages(d) {
      const packages = arr(d.title_thumbnail_packages);
      if (!packages.length) return "";
      return sec("Title + Thumbnail Packages", `<div class="feed">${packages.map((item) => `<div class="feed-card"><div class="tile-row"><h4>${esc(item.package || "Option")} · ${esc(item.title)}</h4>${chip(item.approach || "balanced", "ok")}</div><div class="feed-reason" style="margin-top:10px"><b>Thumbnail text:</b> ${esc(item.thumbnail_text || "")}</div><div class="feed-reason"><b>Visual:</b> ${esc(item.thumbnail_visual || "")}</div><div class="feed-reason"><b>Why viewers may click:</b> ${esc(item.why_click || "")}</div><div class="feed-reason"><b>Best for:</b> ${esc(item.best_for || "")}&nbsp; · &nbsp;<b>Misleading risk:</b> ${esc(item.misleading_risk || "low")}</div></div>`).join("")}</div>`);
    }

    /* ---------- render: workflow + feedback ---------- */
    function renderWorkflow(d) {
      const w = d.automation_workflow || {};
      const list = (a) => arr(a).map((x) => `<li>${esc(x)}</li>`).join("");
      const sc = d.internal_scorecard || {};
      const wp = d.winning_patterns || {};
      const ab = d.ab_test_pack || {};
      return sec("Workflow & Learning", `
        <div class="grid-3" style="margin-bottom:14px">
          <div class="card card-pad"><span class="label">Pre-Publish</span><ul class="clean" style="margin-top:12px">${list(w.pre_publish_checklist) || "<li>n/a</li>"}</ul></div>
          <div class="card card-pad"><span class="label">Publish</span><ul class="clean" style="margin-top:12px">${list(w.publish_workflow) || "<li>n/a</li>"}</ul></div>
          <div class="card card-pad"><span class="label">Next Actions</span><ul class="clean" style="margin-top:12px">${list(w.next_actions) || "<li>n/a</li>"}</ul></div>
        </div>
        <div class="grid-3">
          <div class="tile"><span class="label">Total Analyses</span><div class="metric">${num(sc.total_runs)}</div><div class="sub">Stored locally for learning</div></div>
          <div class="tile"><span class="label">Best Angle</span><div class="metric sm">${esc(wp.best_angle_so_far || "n/a")}</div><div class="sub" style="margin-top:6px">${esc(wp.observation || "")}</div></div>
          <div class="tile"><span class="label">A/B Test Pack</span><div class="sub" style="margin-top:10px"><b style="color:var(--text)">A:</b> ${esc(ab.variation_a || "n/a")}</div><div class="sub" style="margin-top:6px"><b style="color:var(--text)">B:</b> ${esc(ab.variation_b || "n/a")}</div></div>
        </div>`);
    }

    function renderWarnings(d) {
      const w = arr(d.research_warnings);
      if (!w.length) return "";
      return `<div class="banner banner-warn fade" style="margin-bottom:4px">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
        <div>${w.map((x) => esc(x)).join("<br>")}</div></div>`;
    }

    function renderBrief(d) {
      const b = d.creator_brief || {};
      if (!b.status) return "";
      const statusTone = b.status === "ready" ? "ok" : "warn";
      const rows = [
        ["Audience", b.target_audience], ["Viewer promise", b.viewer_promise],
        ["Unique angle", b.unique_angle], ["Proof", b.proof],
        ["Format", b.video_format], ["Title style", b.title_style],
      ].filter(([, value]) => value && value !== "unspecified");
      return sec("Creator Brief", `<div class="card card-pad">
        <div class="tile-row"><div><span class="label">Brief readiness</span><div class="metric sm">${esc(b.status === "ready" ? "Ready to package" : "Needs more detail")}</div></div>${chip((b.completeness || 0) + "% complete", statusTone)}</div>
        <div class="sub" style="margin-top:8px">${esc(b.recommendation || "")}</div>
        <div class="sub" style="margin-top:8px">Writing source: <b style="color:var(--text)">${esc(d.generation_source || "local fallback")}</b></div>
        <div class="kv" style="margin-top:16px">${rows.map(([label, value]) => `<div class="kv-row"><span class="kv-k">${esc(label)}</span><span class="kv-v">${esc(value)}</span></div>`).join("") || "<div class='sub'>Add audience, promise, angle, and proof above for more specific packaging.</div>"}</div>
      </div>`);
    }

    /* ---------- main ---------- */
    function render(d) {
      results.classList.remove("hidden");
      results.innerHTML =
        renderWarnings(d) +
        renderBrief(d) +
        renderMetrics(d) +
        renderLangs(d) +
        renderAudit(d) +
        renderTitleOpt(d) +
        renderPackages(d) +
        renderGap(d) +
        renderStrategy(d) +
        renderSignals(d) +
        renderGrids(d) +
        renderResearch(d) +
        renderWorkflow(d);
      wireLangTabs(d);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function showAlert(kind, msg) {
      alertBox.style.display = "block";
      alertBox.innerHTML = `<div class="banner banner-${kind === "err" ? "err" : "warn"} fade">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4m0 4h.01"/></svg>
        <div>${esc(msg)}</div></div>`;
    }
    const clearAlert = () => { alertBox.style.display = "none"; alertBox.innerHTML = ""; };

    analyzeBtn.addEventListener("click", async () => {
      const script = scriptInput.value.trim();
      clearAlert();
      latestAnalysis = null;
      exportBtn.disabled = true;
      results.classList.add("hidden");
      if (!script) { showAlert("err", "Please enter a script or idea first."); return; }

      analyzeBtn.disabled = true;
      const original = analyzeBtn.innerHTML;
      analyzeBtn.innerHTML = `<span class="spin"></span> Analyzing…`;
      try {
        const r = await fetch("/analyze", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            script,
            ...Object.fromEntries(Object.entries(briefInputs).map(([key, input]) => [key, input.value.trim()])),
          }),
        });
        const data = await r.json();
        if (!r.ok) { showAlert("err", data.error?.message || data.detail || "Analysis failed."); return; }
        latestAnalysis = data;
        exportBtn.disabled = false;
        render(data);
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

    diagBtn.addEventListener("click", async () => {
      const wrap = $("diagWrap"), out = $("diagOut");
      wrap.style.display = "block";
      out.textContent = "Running diagnostics…";
      wrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
      try {
        const r = await fetch("/diagnostics");
        const data = await r.json();
        out.textContent = r.ok ? JSON.stringify(data, null, 2) : (data.error?.message || "Diagnostics failed");
      } catch (e) {
        out.textContent = "Diagnostics request failed. Is the server running?";
      }
    });
    channelBtn.addEventListener("click", () => { window.location.href = "/youtube/channel/connect"; });
    async function loadChannelStatus() {
      try {
        const r = await fetch("/youtube/channel/status");
        const data = await r.json();
        channelPanel.style.display = "block";
        if (!data.configured) {
          channelPanel.innerHTML = `<span class="label">YouTube Channel</span><div class="sub" style="margin-top:8px">${esc(data.setup_message || "OAuth setup is required.")}</div>`;
          channelBtn.textContent = "Set up YouTube OAuth";
          return;
        }
        if (!data.connected) {
          channelPanel.innerHTML = `<span class="label">YouTube Channel</span><div class="sub" style="margin-top:8px">Ready to connect with read-only permissions.</div>`;
          channelBtn.textContent = "Connect YouTube Channel";
          return;
        }
        const channel = data.channel || {};
        const sync = (data.latest_sync || {}).data || {};
        const current = sync.current_28_days || {};
        const learning = sync.video_learning || {};
        channelPanel.innerHTML = `<div class="tile-row"><div><span class="label">Connected channel</span><div class="metric sm">${esc(channel.title || "YouTube channel")}</div><div class="sub" style="margin-top:6px">Last 28 days: ${num(current.views)} views · ${num(current.estimatedMinutesWatched)} minutes watched</div><div class="sub" style="margin-top:6px">${esc(learning.recommendation || "Refresh analytics to begin video learning.")}</div></div><div class="btn-group"><button class="btn" id="channelRefresh">Refresh analytics</button><button class="btn" id="channelDisconnect">Disconnect</button></div></div>`;
        $("channelRefresh").addEventListener("click", async () => { await fetch("/youtube/channel/refresh", {method:"POST"}); await loadChannelStatus(); });
        $("channelDisconnect").addEventListener("click", async () => { if (confirm("Disconnect this YouTube channel from the local tool?")) { await fetch("/youtube/channel/disconnect", {method:"POST"}); await loadChannelStatus(); } });
        channelBtn.style.display = "none";
      } catch (_) { /* connection controls are optional; the editor remains usable */ }
    }
    loadChannelStatus();
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def dashboard():
    return _DASHBOARD_HTML


@router.get("/health")
def health_check():
    settings = get_settings()
    history = HistoryStore(settings.database_path).system_status()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "uptime_seconds": int(time.time() - _APP_START),
        "database_ok": history["database_ok"],
    }


@router.get("/ready")
def readiness_check(request: Request):
    settings = get_settings()
    _require_admin(request, settings)
    history = HistoryStore(settings.database_path).system_status()
    youtube_keys_present = bool(settings.youtube_api_key_pool)
    ready = history["database_ok"] and youtube_keys_present

    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": history,
            "youtube_api_keys_present": youtube_keys_present,
        },
    }


@router.get("/meta")
def metadata():
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "docker_optional": True,
        "public_diagnostics_enabled": settings.public_diagnostics_enabled,
        "capabilities": [
            "youtube research",
            "seo generation",
            "outlier scoring",
            "feedback loop",
            "advanced strategy layer",
        ],
    }


@router.get("/diagnostics")
def diagnostics(request: Request):
    settings = get_settings()
    if not settings.public_diagnostics_enabled:
        _require_admin(request, settings)
    research = ResearchService(settings)

    return {**research.diagnostics(), "gemini": gemini_client.diagnostics()}


@router.get("/youtube/channel/status")
def youtube_channel_status():
    return YouTubeChannelService(get_settings()).status()


@router.get("/youtube/channel/connect")
def connect_youtube_channel():
    service = YouTubeChannelService(get_settings())
    try:
        return RedirectResponse(service.authorization_url())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/oauth/youtube/callback")
def youtube_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(url=f"/?youtube=error&reason={error}")
    try:
        YouTubeChannelService(get_settings()).complete_authorization(code=code, state=state)
    except ValueError as exc:
        return RedirectResponse(url="/?youtube=error")
    return RedirectResponse(url="/?youtube=connected")


@router.post("/youtube/channel/refresh")
def refresh_youtube_channel():
    try:
        return YouTubeChannelService(get_settings()).refresh()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/youtube/channel/disconnect")
def disconnect_youtube_channel():
    YouTubeChannelService(get_settings()).disconnect()
    return {"disconnected": True}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_script(payload: AnalyzeRequest):
    settings = get_settings()
    creator_brief = build_creator_brief(
        script=payload.script,
        target_audience=payload.target_audience,
        viewer_promise=payload.viewer_promise,
        unique_angle=payload.unique_angle,
        proof=payload.proof,
        video_format=payload.video_format,
        title_style=payload.title_style,
        thumbnail_idea=payload.thumbnail_idea,
    )
    research = ResearchService(settings)
    research_data = research.gather(
        payload.script,
        region=payload.region,
        primary_language=payload.language,
        creator_brief=creator_brief,
    )

    context = {
        "language": payload.language,
        "region": payload.region,
        "audience_type": payload.audience_type,
        "creator_brief": creator_brief,
    }
    return generate_seo_suggestions(payload.script, research_data, context=context)


def _require_admin(request: Request, settings) -> None:
    if settings.app_environment == "development":
        return

    expected = settings.admin_api_token
    if not expected:
        raise HTTPException(status_code=403, detail="This endpoint is disabled until an admin token is configured.")

    provided = request.headers.get("X-Admin-Token", "").strip()
    if provided != expected:
        raise HTTPException(status_code=403, detail="Admin token required for this endpoint.")
