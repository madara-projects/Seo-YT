import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedLinkId = null;
const date = (value) => value ? new Date(value).toLocaleString() : "UNAVAILABLE";
const stateLabel = (value) => String(value || "unavailable").replaceAll("_", " ").toUpperCase();

function auditCards(items) {
  if (!items.length) return '<div class="creator-empty-state">No linked published videos match these filters.</div>';
  return items.map((item) => `<button class="ideas-card" data-audit-link="${Number(item.id)}">
    <div class="ideas-card-head"><strong>${esc(item.package_topic || item.youtube_video_id)}</strong>${chip(stateLabel(item.audit_state), item.audit_state === "actionable_observation" ? "ok" : "")}</div>
    <div class="ideas-card-meta">Published ${esc(date(item.published_at))} / Evidence: ${esc(stateLabel(item.evidence_state))}</div>
    <p>Idea: ${esc(item.idea?.topic || "UNAVAILABLE")} / Selection: ${esc(stateLabel(item.selection_state))}</p>
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
  return arr(comparisons).map((item) => `<tr><td>${esc(item.field)}</td><td>${esc(item.generated || (Array.isArray(item.generated) ? item.generated.join(", ") : "UNAVAILABLE"))}</td><td>${esc(Array.isArray(item.selected) ? item.selected.join(", ") : item.selected || "UNKNOWN")}</td><td>${esc(Array.isArray(item.published) ? item.published.join(", ") : item.published || "UNAVAILABLE")}</td><td>${esc(stateLabel(item.selected_to_published))}</td></tr>`).join("");
}

function renderAudit(audit, versions) {
  if (!audit) {
    $("auditDetail").innerHTML = `<div class="card-title"><span>Audit not run</span>${chip("HISTORICAL SNAPSHOT")}</div><p class="metric-sub">Create the first immutable audit from saved intent, selection, owned metadata, and current evidence.</p><button class="btn btn-primary" data-audit-action="refresh">Run audit</button><div id="auditActionStatus" class="metric-sub"></div>`;
    return;
  }
  const before = audit.before_publication || {};
  const observed = audit.observed_performance || {};
  $("auditDetail").innerHTML = `<div class="card-title"><span>PUBLISHED VIDEO AUDIT</span>${chip(stateLabel(audit.summary?.state), audit.summary?.state === "actionable_observation" ? "ok" : "warn")}</div>
    <h2 class="ideas-detail-title">${esc(audit.published_reality?.title || audit.intent?.generated_package?.title || audit.video?.youtube_video_id)}</h2>
    <p class="metric-sub">Captured ${esc(date(audit.captured_at))} / ${esc(audit.summary?.message)}</p>
    <div class="creator-inline-actions ideas-actions"><button class="btn" data-audit-action="refresh">Refresh as new audit version</button></div><div id="auditActionStatus" class="metric-sub"></div>
    <h3 class="creator-section-heading">Intent vs actual</h3><div class="phase8-table-wrap"><table class="history-table"><thead><tr><th>Field</th><th>Generated</th><th>Selected</th><th>Published</th><th>Selection → published</th></tr></thead><tbody>${fieldRows(audit.comparisons)}</tbody></table></div>
    <h3 class="creator-section-heading">Before publication</h3><div class="ideas-facts"><div><span>Generation quality</span><strong>${esc(stateLabel(before.generation_quality?.status))}</strong></div><div><span>Retention risk</span><strong>${esc(stateLabel(before.retention_assistant?.risk_level || before.retention_assistant?.status))}</strong></div><div><span>Demand</span><strong>${esc(stateLabel(before.demand_research?.classification))}</strong></div><div><span>Watchlist context</span><strong>${Array.isArray(before.watchlist_context) ? num(before.watchlist_context.length) : "UNAVAILABLE"}</strong></div><div><span>Personal evidence</span><strong>${esc(stateLabel(before.personal_evidence?.status))}</strong></div><div><span>Idea</span><strong>${esc(before.idea?.topic || "UNAVAILABLE")}</strong></div></div>
    <h3 class="creator-section-heading">Published reality and observed performance</h3><div class="ideas-facts"><div><span>Format / language</span><strong>${esc(audit.video?.format || "UNAVAILABLE")} / ${esc(audit.video?.language || "UNAVAILABLE")}</strong></div><div><span>Metadata captured</span><strong>${esc(date(audit.published_reality?.captured_at))}</strong></div><div><span>Views</span><strong>${num(observed.latest_observation?.views)}</strong></div><div><span>Average viewed</span><strong>${observed.latest_observation?.avg_view_percentage == null ? "UNAVAILABLE" : `${num(observed.latest_observation.avg_view_percentage)}%`}</strong></div><div><span>Evidence maturity</span><strong>${esc(stateLabel(observed.maturity))}</strong></div><div><span>Causality</span><strong>NOT ESTABLISHED</strong></div></div>
    <h3 class="creator-section-heading">Findings</h3><div class="intel-evidence">${arr(audit.findings).map((item) => `<div><strong>${esc(stateLabel(item.severity))} / ${esc(item.code)}</strong><span>${esc(item.explanation)} ${esc(item.recommended_interpretation)}</span><small>${esc(item.evidence_state)} / ${esc(item.evidence)}</small></div>`).join("") || '<div>UNAVAILABLE</div>'}</div>
    <h3 class="creator-section-heading">Learning candidates</h3><div class="intel-evidence">${arr(audit.learning_candidates).map((item) => `<div><strong>${esc(item.variable)}: ${esc(item.value)}</strong><span>${esc(stateLabel(item.evidence_state))} / sample ${num(item.sample_size)}</span><small>${esc(item.interpretation)}</small></div>`).join("") || '<div>INSUFFICIENT EVIDENCE</div>'}</div>
    <h3 class="creator-section-heading">Evidence and limitations</h3><p class="metric-sub">${num(audit.evidence?.snapshot_count)} snapshots / ${num(audit.evidence?.mature_window_count)} mature windows / ${num(versions?.length)} immutable audit versions.</p><ul class="phase8-limitations">${arr(audit.limitations).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
}

async function openAudit(linkId) {
  selectedLinkId = linkId;
  try {
    const data = await apiRequest(`/api/audits/${linkId}`, { cache: "no-store" });
    renderAudit(data.audit, data.versions);
  } catch (error) {
    $("auditDetail").textContent = formatApiError(error, "Audit detail is unavailable.");
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
