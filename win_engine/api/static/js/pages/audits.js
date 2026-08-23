import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedLinkId = null;
const date = (value) => (value ? new Date(value).toLocaleString() : "UNAVAILABLE");
const stateLabel = (value) => String(value || "unavailable").replaceAll("_", " ").toUpperCase();

function auditCards(items) {
  if (!items.length) {
    return `
      <div class="empty-state-card" style="margin:8px 0">
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5"/></svg>
        </div>
        <h4>No Linked Published Videos</h4>
        <p>No linked published videos match these filters. Use the Link button on a History package row after publishing on YouTube.</p>
      </div>`;
  }
  return items.map((item) => `
    <button type="button" class="ideas-card ${Number(item.id) === Number(selectedLinkId) ? "selected" : ""}" data-audit-link="${Number(item.id)}">
      <div class="ideas-card-head">
        <strong>${esc(item.package_topic || item.youtube_video_id)}</strong>
        ${chip(stateLabel(item.audit_state), item.audit_state === "actionable_observation" ? "ok" : item.audit_state === "not_run" ? "warn" : "accent")}
      </div>
      <div class="ideas-card-meta" style="font-size:11px;color:var(--text-sub);margin:4px 0">
        Published: ${esc(date(item.published_at))} &bull; Evidence: <strong>${esc(stateLabel(item.evidence_state))}</strong>
      </div>
      <p style="font-size:12px;color:var(--text-muted);margin:4px 0">Idea: ${esc(item.idea?.topic || "UNAVAILABLE")} &bull; Attribution: <strong>${esc(stateLabel(item.selection_state))}</strong></p>
    </button>`).join("");
}

export async function loadAudits() {
  const params = new URLSearchParams();
  if ($("auditStateFilter")?.value) params.set("audit_state", $("auditStateFilter").value);
  if ($("auditEvidenceFilter")?.value) params.set("evidence_state", $("auditEvidenceFilter").value);
  try {
    const data = await apiRequest(`/api/audits${params.size ? `?${params}` : ""}`, { cache: "no-store" });
    $("auditList").innerHTML = auditCards(arr(data.candidates));
    $("auditStatus").textContent = `${num(data.total)} linked video(s). Audit snapshots are immutable.`;
  } catch (error) {
    $("auditStatus").textContent = formatApiError(error, "Published audits are unavailable.");
  }
}

function fieldRows(comparisons) {
  return arr(comparisons).map((item) => `
    <tr>
      <td><strong>${esc(item.field)}</strong></td>
      <td>${esc(item.generated || (Array.isArray(item.generated) ? item.generated.join(", ") : "UNAVAILABLE"))}</td>
      <td><span class="chip chip-accent" style="font-size:11px">${esc(Array.isArray(item.selected) ? item.selected.join(", ") : item.selected || "UNKNOWN")}</span></td>
      <td>${esc(Array.isArray(item.published) ? item.published.join(", ") : item.published || "UNAVAILABLE")}</td>
      <td>${chip(stateLabel(item.selected_to_published), item.selected_to_published === "match" ? "ok" : "warn")}</td>
    </tr>`).join("");
}

function renderAudit(audit, versions) {
  if (!audit) {
    $("auditDetail").innerHTML = `
      <div class="card-title"><span>Audit not run</span>${chip("HISTORICAL SNAPSHOT")}</div>
      <p class="metric-sub">Create the first immutable audit snapshot from saved generation intent, explicit creator selection, owned YouTube metadata, and mature evidence windows.</p>
      <div style="margin-top:16px"><button type="button" class="btn btn-primary" data-audit-action="refresh">Run audit now</button></div>
      <div id="auditActionStatus" class="metric-sub" aria-live="polite"></div>`;
    return;
  }
  const before = audit.before_publication || {};
  const observed = audit.observed_performance || {};

  $("auditDetail").innerHTML = `
    <div class="card-title">
      <span>PUBLISHED VIDEO AUDIT</span>
      ${chip(stateLabel(audit.summary?.state), audit.summary?.state === "actionable_observation" ? "ok" : "warn")}
    </div>
    <h2 class="ideas-detail-title">${esc(audit.published_reality?.title || audit.intent?.generated_package?.title || audit.video?.youtube_video_id)}</h2>
    <p class="metric-sub">Snapshot captured on ${esc(date(audit.captured_at))} &bull; ${esc(audit.summary?.message || "Audit completed")}</p>

    <!-- 4-Tier Lifecycle Pipeline -->
    <div class="demand-pipeline-flow" style="margin:16px 0">
      <div class="demand-pipeline-step"><span>1. GENERATED</span><strong>${esc(audit.intent?.generated_package?.title ? "Available" : "UNAVAILABLE")}</strong></div>
      <div class="demand-pipeline-arrow">&rarr;</div>
      <div class="demand-pipeline-step"><span>2. SELECTED</span><strong>${esc(stateLabel(audit.intent?.selection_state || "UNKNOWN"))}</strong></div>
      <div class="demand-pipeline-arrow">&rarr;</div>
      <div class="demand-pipeline-step"><span>3. PUBLISHED</span><strong>Live Reality</strong></div>
      <div class="demand-pipeline-arrow">&rarr;</div>
      <div class="demand-pipeline-step"><span>4. OBSERVED</span><strong>${num(observed.latest_observation?.views || 0)} views</strong></div>
    </div>

    <div class="creator-inline-actions ideas-actions" style="margin:12px 0">
      <button type="button" class="btn" data-audit-action="refresh">Refresh as new audit version</button>
    </div>
    <div id="auditActionStatus" class="metric-sub" aria-live="polite"></div>

    <h3 class="creator-section-heading">Intent vs Actual Comparison Matrix</h3>
    <div class="phase8-table-wrap">
      <table class="history-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Generated</th>
            <th>Selected</th>
            <th>Published</th>
            <th>Selection &rarr; Published</th>
          </tr>
        </thead>
        <tbody>${fieldRows(audit.comparisons)}</tbody>
      </table>
    </div>

    <h3 class="creator-section-heading">Before Publication Intelligence</h3>
    <div class="ideas-facts">
      <div><span>Generation quality</span><strong>${esc(stateLabel(before.generation_quality?.status))}</strong></div>
      <div><span>Retention risk</span><strong>${esc(stateLabel(before.retention_assistant?.risk_level || before.retention_assistant?.status))}</strong></div>
      <div><span>Demand</span><strong>${esc(stateLabel(before.demand_research?.classification))}</strong></div>
      <div><span>Watchlist context</span><strong>${Array.isArray(before.watchlist_context) ? num(before.watchlist_context.length) : "UNAVAILABLE"}</strong></div>
      <div><span>Personal evidence</span><strong>${esc(stateLabel(before.personal_evidence?.status))}</strong></div>
      <div><span>Idea topic</span><strong>${esc(before.idea?.topic || "UNAVAILABLE")}</strong></div>
    </div>

    <h3 class="creator-section-heading">Published Reality and Observed Performance</h3>
    <div class="ideas-facts">
      <div><span>Format / language</span><strong>${esc(audit.video?.format || "UNAVAILABLE")} / ${esc(audit.video?.language || "UNAVAILABLE")}</strong></div>
      <div><span>Metadata captured</span><strong>${esc(date(audit.published_reality?.captured_at))}</strong></div>
      <div><span>Measured Views</span><strong>${num(observed.latest_observation?.views)}</strong></div>
      <div><span>Average Viewed %</span><strong>${observed.latest_observation?.avg_view_percentage == null ? "UNAVAILABLE" : `${num(observed.latest_observation.avg_view_percentage)}%`}</strong></div>
      <div><span>Evidence maturity</span><strong>${esc(stateLabel(observed.maturity))}</strong></div>
      <div><span>Causality disclaimer</span><strong>NOT ESTABLISHED</strong></div>
    </div>

    <h3 class="creator-section-heading">Audit Findings &amp; Observations</h3>
    <div class="intel-evidence">
      ${arr(audit.findings).map((item) => `
        <div>
          <strong>${esc(stateLabel(item.severity))} / ${esc(item.code)}</strong>
          <span>${esc(item.explanation)} ${esc(item.recommended_interpretation || "")}</span>
          <small>Evidence: ${esc(item.evidence_state || "")} &bull; ${esc(item.evidence || "")}</small>
        </div>`).join("") || '<div><span>UNAVAILABLE</span></div>'}
    </div>

    <h3 class="creator-section-heading">Learning Candidates</h3>
    <div class="intel-evidence">
      ${arr(audit.learning_candidates).map((item) => `
        <div>
          <strong>${esc(item.variable)}: ${esc(item.value)}</strong>
          <span>${esc(stateLabel(item.evidence_state))} / Sample size: ${num(item.sample_size)}</span>
          <small>${esc(item.interpretation)}</small>
        </div>`).join("") || '<div><span>INSUFFICIENT EVIDENCE</span></div>'}
    </div>

    <h3 class="creator-section-heading">Evidence and Methodological Limitations</h3>
    <p class="metric-sub">${num(audit.evidence?.snapshot_count)} snapshots / ${num(audit.evidence?.mature_window_count)} mature windows / ${num(versions?.length)} immutable audit version(s).</p>
    <ul class="phase8-limitations">
      ${arr(audit.limitations).map((item) => `<li>${esc(item)}</li>`).join("")}
    </ul>`;
}

async function openAudit(linkId) {
  selectedLinkId = linkId;
  const root = $("auditDetail");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading published audit snapshot...</div>`;
  try {
    const data = await apiRequest(`/api/audits/${linkId}`, { cache: "no-store" });
    renderAudit(data.audit, data.versions);
  } catch (error) {
    if (root) root.textContent = formatApiError(error, "Audit detail is unavailable.");
  }
}

async function refreshAudit(button) {
  if (!selectedLinkId || button.disabled) return;
  button.disabled = true;
  try {
    const data = await apiRequest(`/api/audits/${selectedLinkId}/refresh`, { method: "POST" });
    renderAudit(data.audit, data.versions);
    await loadAudits();
  } catch (error) {
    const status = $("auditActionStatus");
    if (status) status.textContent = formatApiError(error, "Audit could not be refreshed.");
  } finally {
    button.disabled = false;
  }
}

export function mountAuditsPage() {
  if (!$("auditList")) return;
  $("auditRefreshList").onclick = loadAudits;
  $("auditStateFilter").onchange = loadAudits;
  $("auditEvidenceFilter").onchange = loadAudits;
  $("auditList").onclick = (event) => {
    const card = event.target.closest("[data-audit-link]");
    if (card) openAudit(Number(card.dataset.auditLink));
  };
  $("auditDetail").onclick = (event) => {
    const button = event.target.closest('[data-audit-action="refresh"]');
    if (button) refreshAudit(button);
  };
}
