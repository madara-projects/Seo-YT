from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse

from win_engine.core.config import get_settings
from win_engine.core.schemas import AnalyzeRequest, AnalyzeResponse
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService

router = APIRouter()

_APP_START = time.time()

_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube SEO Analyzer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f2ea;
      --ink: #1f1b16;
      --accent: #0f766e;
      --card: #fffdf8;
      --border: #e3d9c9;
      --warn: #b42318;
    }
    body {
      margin: 0;
      font-family: "Georgia", "Times New Roman", serif;
      background: radial-gradient(circle at 10% 10%, #fff7e6, #f6f2ea 55%);
      color: var(--ink);
    }
    .wrap {
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 20px 60px;
    }
    header {
      padding: 16px 0 12px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 30px;
      letter-spacing: 0.2px;
    }
    p {
      margin: 0 0 16px;
      line-height: 1.4;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
    }
    label {
      font-weight: 600;
      display: block;
      margin-bottom: 8px;
    }
    textarea {
      width: 100%;
      min-height: 160px;
      border-radius: 10px;
      border: 1px solid var(--border);
      padding: 12px;
      font-size: 15px;
      resize: vertical;
      background: #fff;
    }
    button {
      margin-top: 12px;
      background: var(--accent);
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 15px;
    }
    button.secondary {
      background: #5a4c3e;
    }
    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    button:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }
    .result {
      margin-top: 18px;
      padding: 16px;
      border-radius: 10px;
      background: #f1fbf9;
      border: 1px solid #c6eee9;
      white-space: pre-wrap;
    }
    .result.error {
      background: #fdecea;
      border-color: #f5c2c7;
      color: var(--warn);
    }
    .section {
      margin-top: 18px;
      padding: 14px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #ffffff;
    }
    .section h3 {
      margin: 0 0 8px;
    }
    .meta {
      font-size: 13px;
      color: #5a4c3e;
    }
    .list {
      margin: 0;
      padding-left: 18px;
    }
    .feed {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
      margin-top: 10px;
    }
    .feed-card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      background: linear-gradient(180deg, #fffdfa 0%, #f7f2ea 100%);
      box-shadow: 0 8px 20px rgba(31, 27, 22, 0.06);
    }
    .feed-card h4 {
      margin: 0 0 8px;
      font-size: 18px;
      line-height: 1.25;
    }
    .feed-meta {
      font-size: 13px;
      color: #5a4c3e;
      margin: 4px 0;
    }
    .feed-reason {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px dashed var(--border);
      font-size: 13px;
      color: #473c30;
      line-height: 1.4;
    }
    .row {
      margin: 6px 0;
    }
    .hero {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .stat-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      background: linear-gradient(180deg, #fffdf8 0%, #fbf6ef 100%);
    }
    .stat-card .label {
      font-size: 12px;
      color: #6a5a49;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }
    .stat-card .value {
      font-size: 24px;
      font-weight: 700;
      line-height: 1.1;
    }
    .stat-card .sub {
      margin-top: 6px;
      font-size: 13px;
      color: #5a4c3e;
    }
    .pill {
      display: inline-block;
      padding: 5px 10px;
      border-radius: 999px;
      background: #e6f5f3;
      color: #0f766e;
      font-size: 12px;
      font-weight: 700;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    .pill.warn {
      background: #fdecea;
      color: var(--warn);
    }
    .score-row {
      margin: 10px 0;
    }
    .score-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 13px;
      margin-bottom: 4px;
    }
    .score-bar {
      height: 10px;
      border-radius: 999px;
      background: #ece2d2;
      overflow: hidden;
    }
    .score-fill {
      height: 100%;
      background: linear-gradient(90deg, #0f766e 0%, #53b8aa 100%);
      border-radius: 999px;
    }
    .score-fill.warn {
      background: linear-gradient(90deg, #b42318 0%, #e67e73 100%);
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-top: 10px;
    }
    .mini-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      background: #fffdfa;
    }
    .mini-card h4 {
      margin: 0 0 8px;
      font-size: 16px;
    }
    .muted {
      color: #6a5a49;
      font-size: 13px;
    }
    .export-note {
      margin-top: 10px;
      font-size: 13px;
      color: #5a4c3e;
    }
    @media (max-width: 640px) {
      .wrap {
        padding: 20px 14px 40px;
      }
      h1 {
        font-size: 26px;
      }
      .card {
        padding: 16px;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>YouTube SEO Analyzer</h1>
      <p class="meta">Paste your script, click Analyze, and see SEO suggestions plus YouTube research.</p>
      <p class="meta">Phase 8 has started with release-readiness basics. See `/health`, `/ready`, and `/meta` for service status.</p>
    </header>
    <div class="card">
      <label for="script">Your video script or content</label>
      <textarea id="script" placeholder="Paste your content here..."></textarea>
      <div class="actions">
        <button id="analyzeBtn">Analyze</button>
        <button id="diagBtn" class="secondary">Run Diagnostics</button>
        <button id="exportBtn" class="secondary" disabled>Export Result</button>
      </div>
      <div class="export-note">The dashboard now shows score cards, comparisons, and a one-click export of the latest analysis.</div>

      <div id="summary" class="section" style="display:none;"></div>
      <div id="system" class="section" style="display:none;"></div>
      <div id="titles" class="section" style="display:none;"></div>
      <div id="audit" class="section" style="display:none;"></div>
      <div id="gap" class="section" style="display:none;"></div>
      <div id="strategy" class="section" style="display:none;"></div>
      <div id="expansion" class="section" style="display:none;"></div>
      <div id="feedback" class="section" style="display:none;"></div>
      <div id="pacing" class="section" style="display:none;"></div>
      <div id="keywords" class="section" style="display:none;"></div>
      <div id="entities" class="section" style="display:none;"></div>
      <div id="timing" class="section" style="display:none;"></div>
      <div id="thumbnails" class="section" style="display:none;"></div>
      <div id="opportunities" class="section" style="display:none;"></div>
      <div id="youtube" class="section" style="display:none;"></div>
      <div id="workflow" class="section" style="display:none;"></div>
      <div id="errors" class="result" style="display:none;"></div>
      <div id="diagnostics" class="result" style="display:none;"></div>
    </div>
  </div>

  <script>
    const btn = document.getElementById("analyzeBtn");
    const diagBtn = document.getElementById("diagBtn");
    const summary = document.getElementById("summary");
    const system = document.getElementById("system");
    const titles = document.getElementById("titles");
    const audit = document.getElementById("audit");
    const gap = document.getElementById("gap");
    const strategy = document.getElementById("strategy");
    const expansion = document.getElementById("expansion");
    const feedback = document.getElementById("feedback");
    const pacing = document.getElementById("pacing");
    const keywords = document.getElementById("keywords");
    const entities = document.getElementById("entities");
    const timing = document.getElementById("timing");
    const thumbnails = document.getElementById("thumbnails");
    const opportunities = document.getElementById("opportunities");
    const youtube = document.getElementById("youtube");
    const workflow = document.getElementById("workflow");
    const errors = document.getElementById("errors");
    const diagnostics = document.getElementById("diagnostics");
    const scriptInput = document.getElementById("script");
    const exportBtn = document.getElementById("exportBtn");
    let latestAnalysis = null;

    function renderList(items, formatter) {
      if (!items || items.length === 0) {
        return "<p class='meta'>No results yet. Check your API keys.</p>";
      }
      const rows = items.map(formatter).join("");
      return `<ul class='list'>${rows}</ul>`;
    }

    function renderFeed(items, formatter) {
      if (!items || items.length === 0) {
        return "<p class='meta'>No results yet. Check your API keys.</p>";
      }
      return `<div class='feed'>${items.map(formatter).join("")}</div>`;
    }

    function clampPercent(value, maxValue = 10) {
      const numeric = Number(value || 0);
      return Math.max(0, Math.min(100, (numeric / maxValue) * 100));
    }

    function renderScore(label, value, maxValue = 10, warn = false) {
      const percent = clampPercent(value, maxValue);
      return `
        <div class="score-row">
          <div class="score-head">
            <span>${label}</span>
            <strong>${value ?? "n/a"}</strong>
          </div>
          <div class="score-bar">
            <div class="score-fill ${warn ? "warn" : ""}" style="width:${percent}%;"></div>
          </div>
        </div>
      `;
    }

    function downloadAnalysis(data) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      link.href = url;
      link.download = `youtube-win-engine-${stamp}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }

    btn.addEventListener("click", async () => {
      const script = scriptInput.value.trim();
      latestAnalysis = null;
      exportBtn.disabled = true;
      summary.style.display = "none";
      system.style.display = "none";
      titles.style.display = "none";
      audit.style.display = "none";
      gap.style.display = "none";
      strategy.style.display = "none";
      expansion.style.display = "none";
      feedback.style.display = "none";
      pacing.style.display = "none";
      keywords.style.display = "none";
      entities.style.display = "none";
      timing.style.display = "none";
      thumbnails.style.display = "none";
      opportunities.style.display = "none";
      youtube.style.display = "none";
      workflow.style.display = "none";
      errors.style.display = "none";
      diagnostics.style.display = "none";

      if (!script) {
        errors.style.display = "block";
        errors.classList.add("error");
        errors.textContent = "Please enter a script.";
        return;
      }

      btn.disabled = true;
      errors.style.display = "block";
      errors.classList.remove("error");
      errors.textContent = "Analyzing...";

      try {
        const response = await fetch("/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ script })
        });

        const data = await response.json();
        if (!response.ok) {
          errors.classList.add("error");
          errors.textContent = data.error?.message || data.detail || data.error || "Error";
          return;
        }

        errors.style.display = "none";
        latestAnalysis = data;
        exportBtn.disabled = false;

        summary.style.display = "block";
        summary.innerHTML = `
          <h3>SEO Suggestions</h3>
          <div class='row'><span class='pill'>Intent: ${data.intent}</span><span class='pill'>Angle: ${data.content_angle}</span></div>
          <div class='hero'>
            <div class='stat-card'>
              <div class='label'>Primary Title</div>
              <div class='value' style='font-size:18px;'>${data.title}</div>
              <div class='sub'>Best current packaging recommendation</div>
            </div>
            <div class='stat-card'>
              <div class='label'>CTR Prediction</div>
              <div class='value'>${data.ctr_prediction?.label || "n/a"}</div>
              <div class='sub'>Score: ${data.ctr_prediction?.score ?? "n/a"}</div>
            </div>
            <div class='stat-card'>
              <div class='label'>Opportunity Score</div>
              <div class='value'>${data.opportunity_gap_analysis?.opportunity_score?.label || "n/a"}</div>
              <div class='sub'>${data.opportunity_gap_analysis?.opportunity_score?.score ?? "n/a"}</div>
            </div>
            <div class='stat-card'>
              <div class='label'>Competition</div>
              <div class='value'>${data.opportunity_gap_analysis?.competition?.label || "n/a"}</div>
              <div class='sub'>${data.opportunity_gap_analysis?.competition?.score ?? "n/a"}</div>
            </div>
          </div>
          <div class='row'><strong>Description:</strong> ${data.description}</div>
          <div class='row'><strong>Hashtags:</strong> ${data.hashtags.join(" ")}</div>
          <div class='cards'>
            ${(Array.isArray(data.title_variants) ? data.title_variants : []).map(item => `<div class='mini-card'><h4>${item}</h4><div class='muted'>Alternate title option for testing.</div></div>`).join("")}
          </div>
        `;

        system.style.display = "block";
        system.innerHTML = `
          <h3>System Signals</h3>
          <div class='hero'>
            <div class='stat-card'>
              <div class='label'>Cache Policy</div>
              <div class='value'>${data.cache_policy || "n/a"}</div>
              <div class='sub'>Trending and evergreen queries are cached differently.</div>
            </div>
            <div class='stat-card'>
              <div class='label'>Warnings</div>
              <div class='value' style='font-size:18px;'>${data.research_warnings && data.research_warnings.length ? data.research_warnings.length : 0}</div>
              <div class='sub'>${data.research_warnings && data.research_warnings.length ? data.research_warnings.join(" ") : "None"}</div>
            </div>
          </div>
        `;

        titles.style.display = "block";
        titles.innerHTML = `
          <h3>Title Optimization</h3>
          ${renderList(data.title_optimization?.scored_variants || [], item => `
            <li class='row'>
              <strong>${item.title || "n/a"}</strong><br/>
              <span class='meta'>Score: ${item.score ?? "n/a"} | Length: ${item.length ?? "n/a"} | Mobile hook ok: ${item.mobile_hook_ok ? "yes" : "no"}</span><br/>
              <span class='meta'>Power: ${item.power_score ?? "n/a"} | Curiosity: ${item.curiosity_score ?? "n/a"} | Topic: ${item.topic_score ?? "n/a"}</span>
            </li>
          `)}
        `;

        audit.style.display = "block";
        audit.innerHTML = `
          <h3>Content Audit</h3>
          <div class='row'><strong>Package match:</strong> ${data.content_audit?.alignment?.package_match || "n/a"} (${data.content_audit?.alignment?.title_script_alignment ?? "n/a"})</div>
          <div class='row'><strong>Hook strength:</strong> ${data.content_audit?.hook_audit?.hook_strength || "n/a"}</div>
          <div class='row'><strong>Keyword in opening:</strong> ${data.content_audit?.hook_audit?.keyword_in_opening ? "yes" : "no"}</div>
          <div class='row'><strong>Stakes present:</strong> ${data.content_audit?.hook_audit?.stakes_present ? "yes" : "no"}</div>
          <div class='row'><strong>First 30s dropoff risk:</strong> ${data.content_audit?.first_30_second_simulator?.predicted_dropoff_risk || "n/a"}</div>
          <div class='row'><strong>Engagement strength:</strong> ${data.content_audit?.first_30_second_simulator?.engagement_strength || "n/a"}</div>
          <div class='row'><strong>Pattern interrupts:</strong> ${data.content_audit?.pattern_interrupts?.assessment || "n/a"} (${data.content_audit?.pattern_interrupts?.count ?? "n/a"})</div>
          <div class='row'><strong>Retention risk:</strong> ${data.content_audit?.retention_risk?.level || "n/a"}</div>
          <div class='row'><strong>Notes:</strong> ${Array.isArray(data.content_audit?.retention_risk?.notes) ? data.content_audit.retention_risk.notes.join(" ") : "n/a"}</div>
        `;

        gap.style.display = "block";
        gap.innerHTML = `
          <h3>Opportunity Gap Analysis</h3>
          <div class='row'><strong>Opportunity score:</strong> ${data.opportunity_gap_analysis?.opportunity_score?.label || "n/a"} (${data.opportunity_gap_analysis?.opportunity_score?.score ?? "n/a"})</div>
          <div class='row'><strong>Competition:</strong> ${data.opportunity_gap_analysis?.competition?.label || "n/a"} (${data.opportunity_gap_analysis?.competition?.score ?? "n/a"})</div>
          <div class='row'><strong>Competition reason:</strong> ${data.opportunity_gap_analysis?.competition?.reason || "n/a"}</div>
          <div class='row'><strong>Proceed:</strong> ${data.opportunity_gap_analysis?.idea_kill_switch?.proceed ? "yes" : "no"}</div>
          <div class='row'><strong>Kill switch reason:</strong> ${data.opportunity_gap_analysis?.idea_kill_switch?.reason || "n/a"}</div>
          <div class='row'><strong>Entity focus:</strong> ${Array.isArray(data.opportunity_gap_analysis?.entity_focus) ? data.opportunity_gap_analysis.entity_focus.join(", ") : "n/a"}</div>
          <div class='row'><strong>Differentiation recommendation:</strong> ${data.opportunity_gap_analysis?.differentiation?.recommendation || "n/a"}</div>
          <div class='row'><strong>Emphasize:</strong> ${Array.isArray(data.opportunity_gap_analysis?.differentiation?.emphasize) ? data.opportunity_gap_analysis.differentiation.emphasize.join(", ") : "n/a"}</div>
          <div class='row'><strong>Avoid patterns:</strong> ${Array.isArray(data.opportunity_gap_analysis?.differentiation?.avoid_patterns) && data.opportunity_gap_analysis.differentiation.avoid_patterns.length ? data.opportunity_gap_analysis.differentiation.avoid_patterns.join(" ") : "None"}</div>
          ${renderList(data.opportunity_gap_analysis?.keyword_gaps || [], item => `
            <li class='row'>
              <strong>${item.keyword || "n/a"}</strong><br/>
              <span class='meta'>Gap strength: ${item.gap_strength || "n/a"} | ${item.reason || ""}</span>
            </li>
          `)}
        `;

        strategy.style.display = "block";
        strategy.innerHTML = `
          <h3>Advanced Strategy Layer</h3>
          <div class='cards'>
            <div class='mini-card'>
              <h4>Channel Intelligence</h4>
              <div class='row'><strong>Dominant channel size:</strong> ${data.channel_intelligence?.dominant_channel_size || "n/a"}</div>
              <div class='row'><strong>Dominant video length:</strong> ${data.channel_intelligence?.dominant_video_length || "n/a"}</div>
              <div class='row'><strong>Packaging style:</strong> ${data.channel_intelligence?.dominant_packaging_style || "n/a"}</div>
              <div class='muted'>${data.channel_intelligence?.summary || "n/a"}</div>
            </div>
            <div class='mini-card'>
              <h4>Content Graph Strategy</h4>
              <div class='row'><strong>Hub topic:</strong> ${data.content_graph_strategy?.hub_topic || "n/a"}</div>
              <div class='row'><strong>Supporting topics:</strong> ${Array.isArray(data.content_graph_strategy?.supporting_topics) ? data.content_graph_strategy.supporting_topics.join(", ") : "n/a"}</div>
              <div class='row'><strong>Bridge strategy:</strong> ${data.content_graph_strategy?.bridge_strategy || "n/a"}</div>
            </div>
          </div>
          <div class='row'><strong>Series plan:</strong> ${Array.isArray(data.content_graph_strategy?.series_plan) ? data.content_graph_strategy.series_plan.join(" | ") : "n/a"}</div>
        `;

        expansion.style.display = "block";
        expansion.innerHTML = `
          <h3>Expansion Engine</h3>
          <div class='row'><strong>Chapters:</strong> ${Array.isArray(data.chapters) ? data.chapters.map(item => `${item.timestamp} ${item.title}`).join(" | ") : "n/a"}</div>
          <div class='row'><strong>Next video hook:</strong> ${data.session_expansion?.next_video_hook || "n/a"}</div>
          <div class='row'><strong>Pinned comment funnel:</strong> ${data.session_expansion?.pinned_comment_funnel || "n/a"}</div>
          <div class='row'><strong>Playlist positioning:</strong> ${data.session_expansion?.playlist_positioning || "n/a"}</div>
          <div class='row'><strong>Binge bridge:</strong> ${data.binge_bridge || "n/a"}</div>
        `;

        feedback.style.display = "block";
        feedback.innerHTML = `
          <h3>Feedback Loop</h3>
          <div class='hero'>
            <div class='stat-card'>
              <div class='label'>Total Analyses</div>
              <div class='value'>${data.internal_scorecard?.total_runs ?? "n/a"}</div>
              <div class='sub'>Stored for local learning and comparison</div>
            </div>
            <div class='stat-card'>
              <div class='label'>Best Angle So Far</div>
              <div class='value' style='font-size:18px;'>${data.winning_patterns?.best_angle_so_far || "n/a"}</div>
              <div class='sub'>${data.winning_patterns?.observation || "n/a"}</div>
            </div>
            <div class='stat-card'>
              <div class='label'>Dominant Opportunity</div>
              <div class='value' style='font-size:18px;'>${data.internal_scorecard?.dominant_opportunity_label || "n/a"}</div>
              <div class='sub'>Retention risk: ${data.internal_scorecard?.dominant_retention_risk || "n/a"}</div>
            </div>
          </div>
          ${renderScore("Current CTR Score", data.ctr_prediction?.score ?? 0, 10)}
          ${renderScore("Current Title Score", data.performance_sync?.current_title_score ?? 0, 10)}
          ${renderScore("Historical Title Average", data.performance_sync?.historical_title_score_avg ?? 0, 10)}
          <div class='cards'>
            <div class='mini-card'>
              <h4>Historical Comparison</h4>
              <div class='muted'>${data.historical_comparison?.summary || "n/a"}</div>
              <div class='row'><strong>Title vs avg:</strong> ${data.historical_comparison?.title_score_vs_average ?? "n/a"}</div>
              <div class='row'><strong>Opportunity vs avg:</strong> ${data.historical_comparison?.opportunity_score_vs_average ?? "n/a"}</div>
            </div>
            <div class='mini-card'>
              <h4>Performance Sync</h4>
              <div class='row'><strong>Top competitor views:</strong> ${data.performance_sync?.top_competitor_views ?? "n/a"}</div>
              <div class='row'><strong>Average outlier score:</strong> ${data.performance_sync?.average_outlier_score ?? "n/a"}</div>
              <div class='row'><strong>Snapshot count:</strong> ${data.performance_sync?.snapshot_count ?? "n/a"}</div>
              <div class='row'><strong>Title vs history:</strong> ${data.performance_sync?.title_score_vs_history ?? "n/a"}</div>
            </div>
            <div class='mini-card'>
              <h4>Score Trend</h4>
              <div class='muted'>${data.internal_scorecard?.score_trend || "n/a"}</div>
              <div class='row'><strong>Recent avg title:</strong> ${data.internal_scorecard?.recent_title_score_avg ?? "n/a"}</div>
              <div class='row'><strong>Recent avg opportunity:</strong> ${data.internal_scorecard?.recent_opportunity_score_avg ?? "n/a"}</div>
            </div>
          </div>
          <div class='row'><strong>A/B test pack:</strong> A: ${data.ab_test_pack?.variation_a || "n/a"} | B: ${data.ab_test_pack?.variation_b || "n/a"}</div>
        `;

        pacing.style.display = "block";
        pacing.innerHTML = `
          <h3>Script Pacing & Reach</h3>
          <div class='cards'>
            <div class='mini-card'>
              <h4>Pacing Analysis</h4>
              <div class='row'><strong>Pace:</strong> ${data.pacing_analysis?.pace_label || "n/a"}</div>
              <div class='row'><strong>Avg sentence length:</strong> ${data.pacing_analysis?.avg_sentence_length ?? "n/a"}</div>
              <div class='row'><strong>Hook density:</strong> ${data.pacing_analysis?.hook_density || "n/a"}</div>
              <div class='row'><strong>Pattern interrupts:</strong> ${data.pacing_analysis?.pattern_interrupts ?? "n/a"}</div>
              <div class='muted'>${data.pacing_analysis?.recommendation || "n/a"}</div>
            </div>
            <div class='mini-card'>
              <h4>Language Strategy</h4>
              <div class='row'><strong>Primary language:</strong> ${data.language_strategy?.primary_language || "n/a"}</div>
              <div class='row'><strong>Multi-language ready:</strong> ${data.language_strategy?.multi_language_ready ? "yes" : "no"}</div>
              <div class='muted'>${data.language_strategy?.recommendation || "n/a"}</div>
            </div>
            <div class='mini-card'>
              <h4>Predictive CTR Model</h4>
              <div class='row'><strong>Label:</strong> ${data.ctr_prediction?.label || "n/a"}</div>
              <div class='row'><strong>Confidence:</strong> ${data.ctr_prediction?.confidence || "n/a"}</div>
              <div class='row'><strong>Expected band:</strong> ${data.ctr_prediction?.expected_band || "n/a"}</div>
              <div class='muted'>${data.ctr_prediction?.reason || "n/a"}</div>
            </div>
          </div>
        `;

        keywords.style.display = "block";
        keywords.innerHTML = `
          <h3>Keyword Signals</h3>
          ${renderList(data.keyword_signals, item => `
            <li class='row'>
              <strong>${item.keyword || "n/a"}</strong><br/>
              <span class='meta'>Mentions: ${item.mentions || 0} | Strength: ${item.strength || "n/a"}</span>
            </li>
          `)}
        `;

        entities.style.display = "block";
        entities.innerHTML = `
          <h3>Entity Signals</h3>
          ${renderList(data.entity_signals, item => `
            <li class='row'>
              <strong>${item.entity || "n/a"}</strong><br/>
              <span class='meta'>Mentions: ${item.mentions || 0} | Type: ${item.type || "n/a"}</span>
            </li>
          `)}
        `;

        timing.style.display = "block";
        timing.innerHTML = `
          <h3>Upload Timing Insights</h3>
          <div class='row'><strong>Top hours:</strong> ${Array.isArray(data.upload_timing?.top_hours) ? data.upload_timing.top_hours.join(", ") : "n/a"}</div>
          <div class='row'><strong>Top weekdays:</strong> ${Array.isArray(data.upload_timing?.top_weekdays) ? data.upload_timing.top_weekdays.join(", ") : "n/a"}</div>
          <div class='row'><strong>Recommendation:</strong> ${data.upload_timing?.recommendation || "n/a"}</div>
        `;

        thumbnails.style.display = "block";
        thumbnails.innerHTML = `
          <h3>Thumbnail Intelligence</h3>
          <div class='row'><strong>High-quality thumbs:</strong> ${data.thumbnail_intelligence?.quality_counts?.high || 0}</div>
          <div class='row'><strong>Max-res thumbs:</strong> ${data.thumbnail_intelligence?.quality_counts?.maxres || 0}</div>
          <div class='row'><strong>Low-res count:</strong> ${data.thumbnail_intelligence?.low_resolution_count || 0}</div>
          <div class='row'><strong>Recommendation:</strong> ${data.thumbnail_intelligence?.recommendation || "n/a"}</div>
          <div class='row'><strong>Classified style:</strong> ${data.thumbnail_strategy?.style || "n/a"}</div>
          <div class='row'><strong>Competitive strength:</strong> ${data.thumbnail_strategy?.competitive_strength || "n/a"}</div>
          <div class='row'><strong>Thumbnail strategy:</strong> ${data.thumbnail_strategy?.recommendation || "n/a"}</div>
        `;

        opportunities.style.display = "block";
        opportunities.innerHTML = `
          <h3>Top Opportunities</h3>
          ${renderFeed(data.top_opportunities, item => `
            <div class='feed-card'>
              <h4>${item.title || "Untitled"}</h4>
              <div class='feed-meta'>Outlier score: ${item.outlier_score || "n/a"} | Views/day: ${item.views_per_day || "n/a"}</div>
              <div class='feed-meta'>Views/subscriber: ${item.views_per_subscriber || "n/a"} | Small-channel outlier: ${item.small_channel_outlier ? "yes" : "no"}</div>
              <div class='feed-meta'>Velocity 24h: ${item.velocity_24h ?? "n/a"} | Velocity 48h: ${item.velocity_48h ?? "n/a"} | Velocity 7d: ${item.velocity_7d ?? "n/a"}</div>
              <div class='feed-reason'><strong>Why it matters:</strong> ${Array.isArray(item.opportunity_reasons) ? item.opportunity_reasons.join(" ") : "No explanation yet."}</div>
            </div>
          `)}
        `;

        youtube.style.display = "block";
        youtube.innerHTML = `
          <h3>YouTube Results</h3>
          ${renderFeed(data.youtube_results, item => `
            <div class='feed-card'>
              <h4>${item.title || "Untitled"}</h4>
              <div class='feed-meta'>${item.channel_title || "Unknown channel"}</div>
              <div class='feed-meta'>Views: ${item.view_count || "n/a"}, Likes: ${item.like_count || "n/a"}, Subscribers: ${item.subscriber_count || "n/a"}</div>
              <div class='feed-meta'>Outlier score: ${item.outlier_score || "n/a"} | Engagement density: ${item.engagement_density || "n/a"} | Retention proxy: ${item.retention_proxy || "n/a"}</div>
              <div class='feed-meta'>Duration: ${item.duration || "n/a"} | Velocity 24h: ${item.velocity_24h ?? "n/a"} | History points: ${item.history_points ?? 0}</div>
              <div class='feed-reason'><strong>Why it matters:</strong> ${Array.isArray(item.opportunity_reasons) ? item.opportunity_reasons.join(" ") : "No explanation yet."}</div>
            </div>
          `)}
        `;

        workflow.style.display = "block";
        workflow.innerHTML = `
          <h3>Automation Workflow</h3>
          <div class='cards'>
            <div class='mini-card'>
              <h4>Pre-publish Checklist</h4>
              ${renderList(data.automation_workflow?.pre_publish_checklist || [], item => `<li class='row'>${item}</li>`)}
            </div>
            <div class='mini-card'>
              <h4>Publish Workflow</h4>
              ${renderList(data.automation_workflow?.publish_workflow || [], item => `<li class='row'>${item}</li>`)}
            </div>
            <div class='mini-card'>
              <h4>Next Actions</h4>
              ${renderList(data.automation_workflow?.next_actions || [], item => `<li class='row'>${item}</li>`)}
            </div>
          </div>
        `;
      } catch (err) {
        errors.style.display = "block";
        errors.classList.add("error");
        errors.textContent = "Request failed. Is the server running?";
      } finally {
        btn.disabled = false;
      }
    });

    exportBtn.addEventListener("click", () => {
      if (!latestAnalysis) {
        return;
      }
      downloadAnalysis(latestAnalysis);
    });

    diagBtn.addEventListener("click", async () => {
      diagnostics.style.display = "block";
      diagnostics.classList.remove("error");
      diagnostics.textContent = "Running diagnostics...";
      try {
        const response = await fetch("/diagnostics");
        const data = await response.json();
        if (!response.ok) {
          diagnostics.classList.add("error");
          diagnostics.textContent = data.error?.message || data.detail || data.error || "Diagnostics failed";
          return;
        }
        diagnostics.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        diagnostics.classList.add("error");
        diagnostics.textContent = "Diagnostics request failed. Is the server running?";
      }
    });
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

    return research.diagnostics()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_script(payload: AnalyzeRequest):
    settings = get_settings()
    research = ResearchService(settings)
    research_data = research.gather(payload.script, region=payload.region, primary_language=payload.language)

    context = {
        "language": payload.language,
        "region": payload.region,
        "audience_type": payload.audience_type,
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
