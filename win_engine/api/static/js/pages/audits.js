import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedLinkId = null;
const date = (value) => (value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " IST" : "UNAVAILABLE");
const stateLabel = (value) => String(value || "unavailable").replaceAll("_", " ").toUpperCase();
const value = (item, fallback = "UNAVAILABLE") => item === null || item === undefined || item === "" ? fallback : String(item);
const comparisonText = (item) => {
  const text = Array.isArray(item) ? item.join(", ") : value(item);
  return text.length > 110 ? `${text.slice(0, 107)}...` : text;
};

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
    <button type="button" class="ideas-card audit-card audit-card-${esc(item.evidence_state || "unavailable")} ${Number(item.id) === Number(selectedLinkId) ? "selected" : ""}" data-audit-link="${Number(item.id)}">
      <div class="ideas-card-head">
        <strong class="audit-card-title">${esc(item.youtube_metadata?.title || item.selected_title || item.package_topic || item.youtube_video_id)}</strong>
        ${chip(stateLabel(item.audit_state), item.audit_state === "actionable_observation" ? "ok" : item.audit_state === "not_run" ? "warn" : "accent")}
      </div>
      <div class="audit-card-meta"><span>${esc(date(item.published_at))}</span><span>${num(item.latest_performance?.views)} views</span><span>${esc(stateLabel(item.evidence_state))}</span>${item.ownership_verified ? "<span>Channel verified</span>" : ""}</div>
    </button>`).join("");
}

export async function loadAudits() {
  const params = new URLSearchParams();
  if ($("auditStateFilter")?.value) params.set("audit_state", $("auditStateFilter").value);
  if ($("auditEvidenceFilter")?.value) params.set("evidence_state", $("auditEvidenceFilter").value);
  try {
    const [data, channel] = await Promise.all([
      apiRequest(`/api/audits${params.size ? `?${params}` : ""}`, { cache: "no-store" }),
      apiRequest("/youtube/channel/status", { cache: "no-store" }),
    ]);
    $("auditList").innerHTML = auditCards(arr(data.candidates));
    $("auditStatus").textContent = `${num(data.total)} linked video(s). Refreshing a video contacts the connected channel, then saves a new immutable audit snapshot.`;
    if ($("auditCountChip")) $("auditCountChip").textContent = `${num(data.total)} linked`;
    if ($("auditConnectionStatus")) $("auditConnectionStatus").textContent = channel.connected
      ? `Connected: ${channel.channel?.title || "YouTube channel"}`
      : (channel.setup_message || "YouTube connection is not available");
  } catch (error) {
    $("auditStatus").textContent = formatApiError(error, "Published audits are unavailable.");
    if ($("auditConnectionStatus")) $("auditConnectionStatus").textContent = "Channel status unavailable";
  }
}

function fieldRows(comparisons, hasSelection) {
  return arr(comparisons).map((item) => `
    <tr>
      <td><strong>${esc(item.field)}</strong></td>
      <td title="${esc(Array.isArray(item.generated) ? item.generated.join(", ") : value(item.generated))}">${esc(comparisonText(item.generated))}</td>
      <td title="${esc(Array.isArray(item.published) ? item.published.join(", ") : value(item.published))}">${esc(comparisonText(item.published))}</td>
      <td>${chip(stateLabel(item.generated_to_published), item.generated_to_published === "match" ? "ok" : "warn")}</td>
      ${hasSelection ? `<td title="${esc(Array.isArray(item.selected) ? item.selected.join(", ") : value(item.selected))}">${esc(comparisonText(item.selected))}</td>` : ""}
    </tr>`).join("");
}

function renderAudit(audit, versions) {
  if (!audit) {
    $("auditDetail").innerHTML = `
      <div class="audit-empty-detail"><div><div class="eyebrow">NO SNAPSHOT YET</div><h3>Audit not run</h3><p class="metric-sub">This video is linked, but it has no saved audit version yet.</p></div>
      <div class="audit-explainer"><strong>What Refresh does</strong><span class="metric-sub">It reads the video from your connected channel, saves its current metadata and available performance, then creates a timestamped audit record.</span></div>
      <div><button type="button" class="btn btn-primary audit-refresh-button" data-audit-action="refresh">Refresh data</button></div></div>
      <div id="auditActionStatus" class="metric-sub" aria-live="polite"></div>`;
    return;
  }
  const before = audit.before_publication || {};
  const observed = audit.observed_performance || {};
  const comparisons = arr(audit.comparisons);
  const hasSelection = comparisons.some((item) => item.selected !== null && item.selected !== undefined && item.selected !== "");
  const metadataMatches = comparisons.length > 0 && comparisons.every((item) => item.generated_to_published === "match");
  const mature = observed.maturity === "mature_observation";

  $("auditDetail").innerHTML = `
    <header class="audit-detail-header"><div class="eyebrow">PUBLISHED VIDEO AUDIT</div>
    <h2>${esc(audit.published_reality?.title || audit.intent?.generated_package?.title || audit.video?.youtube_video_id)}</h2>
    <p class="metric-sub">Captured ${esc(date(audit.captured_at))} from the connected channel.</p>
    <div class="audit-detail-actions">${chip(stateLabel(audit.summary?.state), audit.summary?.state === "actionable_observation" ? "ok" : "warn")}<button type="button" class="btn btn-primary audit-refresh-button" data-audit-action="refresh">Refresh data</button></div></header>

    <div class="ideas-facts audit-facts audit-summary-grid">
      <div><span>Published</span><strong>${esc(date(audit.video?.published_at))}</strong></div>
      <div><span>Current views</span><strong>${num(observed.latest_observation?.views)}</strong></div>
      <div><span>Evidence</span><strong>${esc(stateLabel(observed.maturity))}</strong></div>
      <div><span>Versions</span><strong>${num(versions?.length)}</strong></div>
    </div>
    <div id="auditActionStatus" class="metric-sub" aria-live="polite"></div>

    <section class="audit-section"><h3 class="audit-section-heading">Metadata check ${chip(metadataMatches ? "MATCHES SAVED PACKAGE" : "DIFFERENCES FOUND", metadataMatches ? "ok" : "warn")}</h3>
    <p class="audit-evidence-note">${metadataMatches ? "The title, description, tags, and hashtags currently on YouTube match the saved generated package." : "The published values below differ from the saved generated package."}${hasSelection ? " A creator-selected package was recorded and is shown in the final column." : " No creator-selected package was recorded, so the comparison uses the saved generated package."}</p>
    <div class="phase8-table-wrap">
      <table class="history-table audit-comparison-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Saved package</th>
            <th>On YouTube</th>
            <th>Status</th>
            ${hasSelection ? "<th>Selected package</th>" : ""}
          </tr>
        </thead>
        <tbody>${fieldRows(comparisons, hasSelection)}</tbody>
      </table>
    </div></section>

    <section class="audit-section"><h3 class="audit-section-heading">Performance snapshot</h3>
    <div class="ideas-facts audit-facts">
      <div><span>Likes</span><strong>${num(observed.latest_observation?.likes)}</strong></div>
      <div><span>Comments</span><strong>${num(observed.latest_observation?.comments)}</strong></div>
      <div><span>Average viewed</span><strong>${observed.latest_observation?.avg_view_percentage == null ? "UNAVAILABLE" : `${num(observed.latest_observation.avg_view_percentage)}%`}</strong></div>
      <div><span>Snapshot</span><strong>${esc(value(observed.latest_observation?.snapshot_window, "Current"))}</strong></div>
    </div></section>

    <section class="audit-section"><h3 class="audit-section-heading">What this means</h3>
      <div class="audit-conclusion ${mature ? "is-mature" : "is-collecting"}">
        <strong>${mature ? "Enough observation time is available for comparison." : "More observation time is needed."}</strong>
        <span>${mature ? "This can be compared with similar videos once enough comparable examples exist." : "Current counts are useful, but completed 24-hour, 7-day, and 28-day windows provide stronger evidence."} Causality: NOT ESTABLISHED.</span>
      </div>
    </section>

    <details class="audit-details"><summary>Audit notes and saved pre-publish checks</summary>
      <div class="ideas-facts audit-facts">
        <div><span>Generation quality</span><strong>${esc(stateLabel(before.generation_quality?.status))}</strong></div>
        <div><span>Retention risk</span><strong>${esc(stateLabel(before.retention_assistant?.risk_level || before.retention_assistant?.status))}</strong></div>
        <div><span>Demand</span><strong>${esc(stateLabel(before.demand_research?.classification))}</strong></div>
        <div><span>Idea topic</span><strong>${esc(before.idea?.topic || "UNAVAILABLE")}</strong></div>
      </div>
      <div class="audit-findings">
        ${arr(audit.findings).map((item) => `<div class="audit-finding"><strong>${esc(stateLabel(item.severity))} / ${esc(item.code)}</strong><span>${esc(item.explanation)} ${esc(item.recommended_interpretation || "")}</span></div>`).join("")}
      </div>
      <p class="metric-sub">${num(audit.evidence?.snapshot_count)} snapshots / ${num(audit.evidence?.mature_window_count)} mature windows / ${num(versions?.length)} saved audit version(s). Learning status: ${mature ? "COLLECTING COMPARABLE EVIDENCE" : "INSUFFICIENT EVIDENCE"}.</p>
    </details>`;
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
  const original = button.textContent;
  button.textContent = "Refreshing channel data...";
  try {
    const data = await apiRequest(`/api/audits/${selectedLinkId}/refresh`, { method: "POST" });
    renderAudit(data.audit, data.versions);
    const status = $("auditActionStatus");
    if (status) {
      const captured = arr(data.video_refresh?.captured).map((item) => item.snapshot_window).filter(Boolean);
      status.textContent = captured.length
        ? `Connected-channel data refreshed. Captured ${captured.join(", ")} evidence window(s) and saved audit version ${num(data.audit?.id)}.`
        : `Connected-channel metadata and current counts refreshed. Saved audit version ${num(data.audit?.id)}.`;
    }
    await loadAudits();
  } catch (error) {
    const status = $("auditActionStatus");
    if (status) status.textContent = formatApiError(error, "Audit could not be refreshed.");
  } finally {
    button.disabled = false;
    button.textContent = original;
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
