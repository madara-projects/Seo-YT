import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedExperimentId = null;
let publishedCandidates = [];
const label = (value) => String(value || "unavailable").replaceAll("_", " ").toUpperCase();

function cards(items) {
  if (!items.length) {
    return `
      <div class="empty-state-card" style="margin:8px 0">
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M8 15h8"/></svg>
        </div>
        <h4>No Comparisons Yet</h4>
        <p>No structured comparisons match this filter. Create a planned or observational comparison using the form above.</p>
      </div>`;
  }
  return items.map((item) => `
    <button type="button" class="ideas-card ${Number(item.id) === Number(selectedExperimentId) ? "selected" : ""}" data-experiment-id="${Number(item.id)}">
      <div class="ideas-card-head">
        <strong>${esc(item.name)}</strong>
        ${chip(label(item.mode), item.mode === "observational" ? "warn" : "accent")}
      </div>
      <div class="ideas-card-meta" style="font-size:11px;color:var(--text-sub);margin:4px 0">
        Status: <strong>${esc(label(item.status))}</strong> &bull; Variable: <strong>${esc(item.variable)}</strong> &bull; Window: <strong>${esc(item.observation_window)}</strong>
      </div>
      <p style="font-size:12px;color:var(--text-muted);margin:4px 0">Control: <strong>${num(item.assignment_counts?.control)}</strong> &bull; Variant: <strong>${num(item.assignment_counts?.variant)}</strong> &bull; Result: <strong>${esc(label(item.latest_result?.state || "not compared"))}</strong></p>
    </button>`).join("");
}

export async function loadExperiments() {
  const params = new URLSearchParams();
  if ($("experimentStatusFilter")?.value) params.set("status", $("experimentStatusFilter").value);
  if ($("experimentModeFilter")?.value) params.set("mode", $("experimentModeFilter").value);
  try {
    const [data, audits] = await Promise.all([
      apiRequest(`/api/experiment-center/experiments${params.size ? `?${params}` : ""}`, { cache: "no-store" }),
      apiRequest("/api/audits", { cache: "no-store" }),
    ]);
    publishedCandidates = arr(audits.candidates);
    $("experimentList").innerHTML = cards(arr(data.experiments));
  } catch (error) {
    if ($("experimentCreateStatus")) $("experimentCreateStatus").textContent = formatApiError(error, "Experiment Center is unavailable.");
  }
}

function assignmentOptions() {
  return publishedCandidates.map((item) => `<option value="${Number(item.id)}">${esc(item.youtube_metadata?.title || item.package_topic || item.youtube_video_id)}</option>`).join("");
}

function groupRows(items, role) {
  const rows = arr(items).filter((item) => item.role === role);
  if (!rows.length) return '<div class="creator-empty-state" style="padding:14px">No explicitly assigned videos in this group.</div>';
  return rows.map((item) => `
    <div class="phase8-assignment">
      <div>
        <strong>${esc(item.title || item.youtube_video_id)}</strong>
        <span style="display:block;font-size:11px;color:var(--text-muted)">ID: ${esc(item.youtube_video_id)} &bull; Role: ${esc(label(item.role))}</span>
      </div>
      <button type="button" class="btn btn-sm btn-danger" data-remove-assignment="${Number(item.id)}">Remove</button>
    </div>`).join("");
}

function metricRows(metrics) {
  return arr(metrics).map((item) => `
    <tr>
      <td><strong>${esc(label(item.metric))}</strong></td>
      <td>${item.control?.median == null ? "UNAVAILABLE" : num(item.control.median)} <span class="ideas-card-meta">(n=${num(item.control?.sample_size)})</span></td>
      <td>${item.variant?.median == null ? "UNAVAILABLE" : num(item.variant.median)} <span class="ideas-card-meta">(n=${num(item.variant?.sample_size)})</span></td>
      <td><strong>${item.relative_difference_percent == null ? "UNAVAILABLE" : `${num(item.relative_difference_percent)}%`}</strong></td>
      <td>${chip(label(item.observed_direction), item.observed_direction === "positive" ? "ok" : item.observed_direction === "negative" ? "bad" : "")}</td>
    </tr>`).join("");
}

function renderExperiment(item, versions = []) {
  selectedExperimentId = item.id;
  const result = item.latest_result;
  const next = { draft: "planned", planned: "active", active: "completed", paused: "active" }[item.status];
  const isObservational = item.mode === "observational";

  $("experimentDetail").innerHTML = `
    <div class="card-title">
      <span>${isObservational ? "Observational Comparison" : "Planned Controlled Experiment"}</span>
      ${chip(isObservational ? "OBSERVATIONAL" : "PLANNED EXPERIMENT", isObservational ? "warn" : "accent")}
    </div>
    <h2 class="ideas-detail-title">${esc(item.name)}</h2>
    <p class="ideas-detail-notes">${esc(item.hypothesis)}</p>
    <div class="phase8-warning">${isObservational ? "OBSERVATIONAL COMPARISON — NOT A CONTROLLED EXPERIMENT" : "DIRECTIONAL EVIDENCE — NOT CAUSAL PROOF"}</div>

    <div class="ideas-facts">
      <div><span>Status</span><strong>${esc(label(item.status))}</strong></div>
      <div><span>Variable</span><strong>${esc(item.variable)}</strong></div>
      <div><span>Observation Window</span><strong>${esc(item.observation_window)}</strong></div>
      <div><span>Primary Metric</span><strong>${esc(label(item.success_metric))}</strong></div>
    </div>

    <div class="creator-analysis-grid" style="margin:16px 0">
      <div class="creator-analysis-card">
        <div class="creator-card-heading">Control definition &amp; assignments</div>
        <p class="metric-sub" style="margin-bottom:8px">${esc(item.control_definition)}</p>
        ${groupRows(item.assignments, "control")}
      </div>
      <div class="creator-analysis-card">
        <div class="creator-card-heading">Variant definition &amp; assignments</div>
        <p class="metric-sub" style="margin-bottom:8px">${esc(item.variant_definition)}</p>
        ${groupRows(item.assignments, "variant")}
      </div>
    </div>

    ${isObservational ? `<h3 class="creator-section-heading">Observational references</h3>${groupRows(item.assignments, "observational_reference")}` : ""}

    <div class="phase8-assign">
      <select id="experimentAssignVideo"><option value="">Select verified linked video</option>${assignmentOptions()}</select>
      <select id="experimentAssignRole">
        <option value="control">Control</option>
        <option value="variant">Variant</option>
        ${isObservational ? '<option value="observational_reference">Observational reference</option>' : ""}
      </select>
      <button type="button" class="btn" data-experiment-action="assign">Assign explicitly</button>
    </div>

    <div class="creator-inline-actions ideas-actions" style="margin:14px 0">
      <button type="button" class="btn btn-primary" data-experiment-action="compare">Calculate comparison</button>
      ${next ? `<button type="button" class="btn" data-experiment-action="status" data-next-status="${next}">Mark ${esc(next)}</button>` : ""}
    </div>
    <div id="experimentActionStatus" class="metric-sub" aria-live="polite"></div>

    <h3 class="creator-section-heading">Comparative Result &amp; Observations</h3>
    ${result ? `
      <div class="phase8-result">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px">
          <strong>${esc(result.label || "Comparison Result")}</strong>
          ${chip(label(result.state), result.state === "insufficient_evidence" ? "warn" : "ok")}
        </div>
        <p>${esc(result.interpretation)}</p>
        <div class="phase8-table-wrap">
          <table class="history-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Control Median (n)</th>
                <th>Variant Median (n)</th>
                <th>Relative Difference</th>
                <th>Observed Direction</th>
              </tr>
            </thead>
            <tbody>${metricRows(result.metrics)}</tbody>
          </table>
        </div>
        <p class="metric-sub">Eligible control: ${num(result.sample?.eligible_control)} &bull; Variant: ${num(result.sample?.eligible_variant)} &bull; Minimum required: ${num(result.sample?.minimum_per_group)} each.</p>
        <p style="margin-top:6px;font-size:12.5px;color:var(--text)">${esc(result.next_recommendation || "")}</p>
        <ul class="phase8-limitations" style="margin-top:8px">
          ${arr(result.limitations).map((text) => `<li>${esc(text)}</li>`).join("")}
        </ul>
        ${result.learning_candidate ? `
          <div class="ideas-evidence-summary" style="margin-top:10px">
            <strong>Learning candidate observation</strong>
            <p>${esc(result.learning_candidate.variable)}: ${esc(label(result.learning_candidate.evidence_state))} / Sample: ${num(result.learning_candidate.sample_size)}. ${esc(result.learning_candidate.interpretation)}</p>
          </div>` : ""}
      </div>` : '<div class="creator-empty-state">INSUFFICIENT EVIDENCE until a comparison is calculated from assigned videos. No fake statistical significance is assumed.</div>'}
    <p class="metric-sub" style="margin-top:10px">${num(versions.length)} immutable comparison snapshot(s). No result is automatically applied to future generation.</p>`;
}

async function openExperiment(id) {
  const root = $("experimentDetail");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading experiment details...</div>`;
  try {
    const data = await apiRequest(`/api/experiment-center/experiments/${id}`, { cache: "no-store" });
    renderExperiment(data.experiment, data.result_versions);
  } catch (error) {
    if (root) root.textContent = formatApiError(error, "Experiment detail is unavailable.");
  }
}

async function action(button) {
  if (!selectedExperimentId || button.disabled) return;
  button.disabled = true;
  try {
    const kind = button.dataset.experimentAction;
    if (kind === "assign") {
      const linkId = Number($("experimentAssignVideo").value);
      if (!linkId) throw new Error("Select a verified linked video.");
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}/assignments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ published_video_link_id: linkId, role: $("experimentAssignRole").value }),
      });
    } else if (kind === "compare") {
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}/compare`, { method: "POST" });
    } else if (kind === "status") {
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: button.dataset.nextStatus }),
      });
    }
    await openExperiment(selectedExperimentId);
    await loadExperiments();
  } catch (error) {
    const status = $("experimentActionStatus");
    if (status) status.textContent = formatApiError(error, error.message || "Experiment action failed.");
  } finally {
    button.disabled = false;
  }
}

async function removeAssignment(id, button) {
  if (button.disabled) return;
  button.disabled = true;
  try {
    await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}/assignments/${id}`, { method: "DELETE" });
    await openExperiment(selectedExperimentId);
    await loadExperiments();
  } catch (error) {
    const status = $("experimentActionStatus");
    if (status) status.textContent = formatApiError(error, "Assignment could not be removed.");
  } finally {
    button.disabled = false;
  }
}

export function mountExperimentsPage() {
  if (!$("experimentForm")) return;
  $("experimentForm").onsubmit = async (event) => {
    event.preventDefault();
    const button = $("experimentCreateBtn");
    if (button.disabled) return;
    button.disabled = true;
    const status = $("experimentCreateStatus");
    if (status) status.textContent = "Creating structured comparison in SQLite...";
    try {
      const payload = {
        name: $("experimentName").value,
        hypothesis: $("experimentHypothesis").value,
        mode: $("experimentMode").value,
        variable: $("experimentVariable").value,
        control_definition: $("experimentControl").value,
        variant_definition: $("experimentVariant").value,
        success_metric: $("experimentMetric").value,
        observation_window: $("experimentWindow").value,
      };
      const data = await apiRequest("/api/experiment-center/experiments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      event.target.reset();
      await openExperiment(data.experiment.id);
      await loadExperiments();
      if (status) status.textContent = "Comparison created.";
    } catch (error) {
      if (status) status.textContent = formatApiError(error, "Could not create comparison.");
    } finally {
      button.disabled = false;
    }
  };

  $("experimentRefreshList").onclick = loadExperiments;
  $("experimentStatusFilter").onchange = loadExperiments;
  $("experimentModeFilter").onchange = loadExperiments;

  $("experimentList").onclick = (event) => {
    const card = event.target.closest("[data-experiment-id]");
    if (card) openExperiment(Number(card.dataset.experimentId));
  };

  $("experimentDetail").onclick = (event) => {
    const actionBtn = event.target.closest("[data-experiment-action]");
    if (actionBtn) action(actionBtn);
    const removeBtn = event.target.closest("[data-remove-assignment]");
    if (removeBtn) removeAssignment(Number(removeBtn.dataset.removeAssignment), removeBtn);
  };
}
