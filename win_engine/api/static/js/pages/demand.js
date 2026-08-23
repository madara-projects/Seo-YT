import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedId = null;

const date = (v) => (v ? new Date(v).toLocaleString() : "Not available");

function classificationChip(classification) {
  const isWarn = classification === "insufficient_evidence" || classification === "unavailable";
  return chip(String(classification || "unavailable").replaceAll("_", " ").toUpperCase(), isWarn ? "warn" : "accent");
}

function renderList(data) {
  const root = $("demandList");
  if (!root) return;
  const rows = arr(data.research);
  if (!rows.length) {
    root.innerHTML = `
      <div class="empty-state-card" style="margin:8px 0">
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 20h18M5 17l4-5 4 3 6-9"/></svg>
        </div>
        <h4>No Demand Snapshots Yet</h4>
        <p>No demand research snapshots exist yet. Enter a topic above to investigate observed market signals without fake search volume.</p>
      </div>`;
    return;
  }
  root.innerHTML = rows.map((x) => `
    <button type="button" class="ideas-card ${Number(x.id) === Number(selectedId) ? "selected" : ""}" data-demand-id="${Number(x.id)}">
      <div class="ideas-card-head">
        <strong>${esc(x.topic)}</strong>
        ${classificationChip(x.classification)}
      </div>
      <div class="ideas-card-meta" style="display:flex;gap:6px;flex-wrap:wrap;margin:4px 0">
        <span class="chip" style="font-size:10.5px">${esc(x.language || "any language")}</span>
        <span class="chip" style="font-size:10.5px">${esc(x.format || "any format")}</span>
      </div>
      <p style="font-size:12px;color:var(--text-muted);margin:4px 0">Immutable evidence snapshot. Observational market guidance only; not guaranteed search volume.</p>
      <div class="ideas-card-meta" style="font-size:10.5px;color:var(--text-sub)">
        Captured: ${esc(date(x.captured_at))}
      </div>
    </button>`).join("");
}

function render(item) {
  const root = $("demandDetail");
  if (!root) return;
  selectedId = item.id;
  const e = item.evidence || {};
  const personal = e.personal_evidence || {};
  const signals = arr(e.signals);
  const watchlist = arr(e.watchlist_evidence);
  const reasons = arr(e.reasons);
  const limitations = arr(e.limitations);

  root.innerHTML = `
    <div class="card-title"><span>Topic Demand Intelligence</span>${classificationChip(item.classification)}</div>
    <h2 class="ideas-detail-title">${esc(item.topic)}</h2>
    <p class="metric-sub">Snapshot captured on ${esc(date(item.captured_at))}. Internal evidence classification only.</p>

    <div class="demand-pipeline-flow">
      <div class="demand-pipeline-step"><span>1. Topic Query</span><strong>${esc(item.topic)}</strong></div>
      <div class="demand-pipeline-arrow">&rarr;</div>
      <div class="demand-pipeline-step"><span>2. Public Signals</span><strong>${signals.length} observed</strong></div>
      <div class="demand-pipeline-arrow">&rarr;</div>
      <div class="demand-pipeline-step"><span>3. Classification</span><strong>${esc(item.classification)}</strong></div>
    </div>

    <div class="creator-card-heading">Classification reasoning ${chip("Local heuristic", "warn")}</div>
    <div class="intel-evidence">
      ${reasons.length ? reasons.map((r) => `<div><span>${esc(r)}</span></div>`).join("") : "<div><span>No classification reason is available.</span></div>"}
    </div>

    <div class="creator-card-heading">Observed public signals &amp; provenance ${chip("YouTube Data API", "cyan")}</div>
    <div class="intel-evidence">
      ${signals.length ? signals.map((s) => `
        <div>
          <strong>${esc(s.name)} / Source: ${esc(s.source)}</strong>
          <span>Observed mentions/volume: ${num(s.observed)}. ${esc(s.limitation || "")}</span>
        </div>`).join("") : "<div><span>No keyword or entity signals were observed in public data.</span></div>"}
    </div>

    <div class="ideas-evidence-summary">
      <div class="creator-card-heading">Watchlist &amp; outlier evidence ${chip("Public observation", "accent")}</div>
      <p>${watchlist.length} matching saved video(s); ${watchlist.filter((x) => x.outlier_status === "possible_outlier").length} possible outlier observation(s).</p>
      ${watchlist.length ? `<div class="ideas-card-meta" style="margin-top:4px">Outliers indicate observed engagement velocity, not viral prediction.</div>` : ""}
    </div>

    <div class="ideas-evidence-summary">
      <div class="creator-card-heading">Personal channel evidence ${chip(personal.source || "unavailable", personal.learning_allowed ? "ok" : "warn")}</div>
      <p>${personal.learning_allowed ? "Eligible mature creator history is available for this topic." : "Not enough mature comparable personal evidence exists on this channel yet."}</p>
      <div class="ideas-card-meta">Sample size: ${num(personal.sample_size || 0)} video(s) / Window: ${esc(personal.snapshot_window || "24h")}</div>
    </div>

    <div class="creator-card-heading">Limitations &amp; truth boundaries</div>
    <div class="intel-evidence">
      ${limitations.length ? limitations.map((x) => `<div><span>${esc(x)}</span></div>`).join("") : "<div><span>Public observations and keyword signals do not guarantee viewer search volume or future algorithmic reach.</span></div>"}
    </div>

    <div id="demandActionStatus" class="metric-sub" aria-live="polite"></div>
    <div class="creator-inline-actions" style="margin-top:16px">
      <button type="button" class="btn btn-primary" data-demand-action="generate" style="padding:9px 18px">Generate package through Creator engine</button>
    </div>`;
}

export async function loadDemand() {
  const root = $("demandList");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading demand research history...</div>`;
  try {
    const d = await apiRequest("/api/demand/research?limit=50&offset=0", { cache: "no-store" });
    renderList(d);
  } catch (e) {
    if ($("demandStatus")) $("demandStatus").textContent = formatApiError(e, "Demand history unavailable.");
  }
}

async function open(id) {
  const root = $("demandDetail");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading demand evidence snapshot...</div>`;
  try {
    const d = await apiRequest(`/api/demand/research/${id}`, { cache: "no-store" });
    render(d.research);
  } catch (e) {
    if (root) root.textContent = formatApiError(e, "Demand evidence unavailable.");
  }
}

export function mountDemandPage() {
  if (!$("demandForm")) return;
  $("demandForm").onsubmit = async (e) => {
    e.preventDefault();
    const b = $("demandResearchBtn");
    if (b.disabled) return;
    b.disabled = true;
    $("demandStatus").textContent = "Researching approved public observations...";
    try {
      const d = await apiRequest("/api/demand/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: $("demandTopic").value,
          language: $("demandLanguage").value,
          format: $("demandFormat").value,
          region: $("demandRegion").value,
          audience_context: $("demandAudience").value,
        }),
      });
      render(d.research);
      await loadDemand();
      $("demandStatus").textContent = "Dated evidence snapshot saved.";
    } catch (x) {
      $("demandStatus").textContent = formatApiError(x, "Research failed.");
    } finally {
      b.disabled = false;
    }
  };

  $("demandRefreshBtn").onclick = loadDemand;

  $("demandList").onclick = (e) => {
    const c = e.target.closest("[data-demand-id]");
    if (c) open(Number(c.dataset.demandId));
  };

  $("demandDetail").onclick = async (e) => {
    const b = e.target.closest("[data-demand-action]");
    if (!b || b.disabled || !selectedId) return;
    b.disabled = true;
    try {
      const d = await apiRequest(`/api/demand/research/${selectedId}/generate`, { method: "POST" });
      $("demandActionStatus").textContent = `Package saved in History run ${d.analysis?.history_run_id ?? "available"}. Publishing remains manual.`;
    } catch (x) {
      $("demandActionStatus").textContent = formatApiError(x, "Generation failed.");
    } finally {
      b.disabled = false;
    }
  };
}
