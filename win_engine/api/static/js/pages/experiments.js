import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selectedExperimentId = null;
let publishedCandidates = [];
const label = (value) => String(value || "unavailable").replaceAll("_", " ").toUpperCase();

function cards(items) {
  if (!items.length) return '<div class="creator-empty-state">No structured comparisons match this filter.</div>';
  return items.map((item) => `<button class="ideas-card" data-experiment-id="${Number(item.id)}"><div class="ideas-card-head"><strong>${esc(item.name)}</strong>${chip(label(item.mode), item.mode === "observational" ? "warn" : "accent")}</div><div class="ideas-card-meta">${esc(label(item.status))} / Variable: ${esc(item.variable)} / Window: ${esc(item.observation_window)}</div><p>Control ${num(item.assignment_counts?.control)} / Variant ${num(item.assignment_counts?.variant)} / Result ${esc(label(item.latest_result?.state || "not compared"))}</p></button>`).join("");
}

export async function loadExperiments() {
  const params = new URLSearchParams();
  if ($("experimentStatusFilter")?.value) params.set("status", $("experimentStatusFilter").value);
  if ($("experimentModeFilter")?.value) params.set("mode", $("experimentModeFilter").value);
  try {
    const [data, audits] = await Promise.all([apiRequest(`/api/experiment-center/experiments${params.size ? `?${params}` : ""}`, { cache: "no-store" }), apiRequest("/api/audits", { cache: "no-store" })]);
    publishedCandidates = arr(audits.candidates);
    $("experimentList").innerHTML = cards(arr(data.experiments));
  } catch (error) {
    $("experimentCreateStatus").textContent = formatApiError(error, "Experiment Center is unavailable.");
  }
}

function assignmentOptions() {
  return publishedCandidates.map((item) => `<option value="${Number(item.id)}">${esc(item.youtube_metadata?.title || item.package_topic || item.youtube_video_id)}</option>`).join("");
}

function groupRows(items, role) {
  const rows = arr(items).filter((item) => item.role === role);
  if (!rows.length) return '<div class="creator-empty-state">No explicitly assigned videos.</div>';
  return rows.map((item) => `<div class="phase8-assignment"><strong>${esc(item.title || item.youtube_video_id)}</strong><span>${esc(item.youtube_video_id)} / ${esc(label(item.role))}</span><button class="btn" data-remove-assignment="${Number(item.id)}">Remove</button></div>`).join("");
}

function metricRows(metrics) {
  return arr(metrics).map((item) => `<tr><td>${esc(label(item.metric))}</td><td>${item.control?.median == null ? "UNAVAILABLE" : num(item.control.median)} (${num(item.control?.sample_size)})</td><td>${item.variant?.median == null ? "UNAVAILABLE" : num(item.variant.median)} (${num(item.variant?.sample_size)})</td><td>${item.relative_difference_percent == null ? "UNAVAILABLE" : `${num(item.relative_difference_percent)}%`}</td><td>${esc(label(item.observed_direction))}</td></tr>`).join("");
}

function renderExperiment(item, versions = []) {
  selectedExperimentId = item.id;
  const result = item.latest_result;
  const next = { draft: "planned", planned: "active", active: "completed", paused: "active" }[item.status];
  $("experimentDetail").innerHTML = `<div class="card-title"><span>EXPERIMENT</span>${chip(item.mode === "observational" ? "OBSERVATIONAL" : "PLANNED EXPERIMENT", item.mode === "observational" ? "warn" : "accent")}</div>
    <h2 class="ideas-detail-title">${esc(item.name)}</h2><p>${esc(item.hypothesis)}</p><p class="phase8-warning">${item.mode === "observational" ? "OBSERVATIONAL COMPARISON — NOT A CONTROLLED EXPERIMENT" : "DIRECTIONAL EVIDENCE — NOT CAUSAL PROOF"}</p>
    <div class="ideas-facts"><div><span>Status</span><strong>${esc(label(item.status))}</strong></div><div><span>Variable</span><strong>${esc(item.variable)}</strong></div><div><span>Window</span><strong>${esc(item.observation_window)}</strong></div><div><span>Primary metric</span><strong>${esc(label(item.success_metric))}</strong></div></div>
    <h3 class="creator-section-heading">Control</h3><p>${esc(item.control_definition)}</p>${groupRows(item.assignments, "control")}
    <h3 class="creator-section-heading">Variant</h3><p>${esc(item.variant_definition)}</p>${groupRows(item.assignments, "variant")}
    ${item.mode === "observational" ? `<h3 class="creator-section-heading">Observational references</h3>${groupRows(item.assignments, "observational_reference")}` : ""}
    <div class="phase8-assign"><select id="experimentAssignVideo"><option value="">Select verified linked video</option>${assignmentOptions()}</select><select id="experimentAssignRole"><option value="control">Control</option><option value="variant">Variant</option>${item.mode === "observational" ? '<option value="observational_reference">Observational reference</option>' : ""}</select><button class="btn" data-experiment-action="assign">Assign explicitly</button></div>
    <div class="creator-inline-actions ideas-actions"><button class="btn btn-primary" data-experiment-action="compare">Calculate comparison</button>${next ? `<button class="btn" data-experiment-action="status" data-next-status="${next}">Mark ${esc(next)}</button>` : ""}</div><div id="experimentActionStatus" class="metric-sub"></div>
    <h3 class="creator-section-heading">Comparison</h3>${result ? `<div class="phase8-result">${chip(label(result.state), result.state === "insufficient_evidence" ? "warn" : "ok")}<strong>${esc(result.label)}</strong><p>${esc(result.interpretation)}</p><div class="phase8-table-wrap"><table class="history-table"><thead><tr><th>Metric</th><th>Control median (n)</th><th>Variant median (n)</th><th>Relative difference</th><th>Observed direction</th></tr></thead><tbody>${metricRows(result.metrics)}</tbody></table></div><p class="metric-sub">Eligible control ${num(result.sample?.eligible_control)} / variant ${num(result.sample?.eligible_variant)} / minimum ${num(result.sample?.minimum_per_group)} each.</p><p>${esc(result.next_recommendation)}</p><ul class="phase8-limitations">${arr(result.limitations).map((text) => `<li>${esc(text)}</li>`).join("")}</ul>${result.learning_candidate ? `<div class="ideas-evidence-summary"><strong>Learning candidate</strong><p>${esc(result.learning_candidate.variable)} / ${esc(label(result.learning_candidate.evidence_state))} / sample ${num(result.learning_candidate.sample_size)}. ${esc(result.learning_candidate.interpretation)}</p></div>` : ""}</div>` : '<div class="creator-empty-state">INSUFFICIENT EVIDENCE until a comparison is calculated from assigned videos.</div>'}
    <p class="metric-sub">${num(versions.length)} immutable comparison snapshot(s). No result is automatically applied to future generation.</p>`;
}

async function openExperiment(id) {
  try {
    const data = await apiRequest(`/api/experiment-center/experiments/${id}`, { cache: "no-store" });
    renderExperiment(data.experiment, data.result_versions);
  } catch (error) {
    $("experimentDetail").textContent = formatApiError(error, "Experiment detail is unavailable.");
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
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}/assignments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ published_video_link_id: linkId, role: $("experimentAssignRole").value }) });
    } else if (kind === "compare") {
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}/compare`, { method: "POST" });
    } else if (kind === "status") {
      await apiRequest(`/api/experiment-center/experiments/${selectedExperimentId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: button.dataset.nextStatus }) });
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
  }
}

export function mountExperimentsPage() {
  if (!$("experimentForm")) return;
  $("experimentForm").onsubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = event.submitter || $("experimentCreateBtn");
    if (button.disabled) return;
    button.disabled = true;
    try {
      const payload = { name: $("experimentName").value, hypothesis: $("experimentHypothesis").value, mode: $("experimentMode").value, variable: $("experimentVariable").value, variable_category: "creator_decision", control_definition: $("experimentControl").value, variant_definition: $("experimentVariant").value, success_metric: $("experimentMetric").value, secondary_metrics: [], minimum_sample_size: 5, observation_window: $("experimentWindow").value };
      const data = await apiRequest("/api/experiment-center/experiments", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      form.reset();
      await loadExperiments();
      await openExperiment(data.experiment.id);
    } catch (error) {
      $("experimentCreateStatus").textContent = formatApiError(error, "Experiment could not be created.");
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
    const remove = event.target.closest("[data-remove-assignment]");
    if (remove) return removeAssignment(Number(remove.dataset.removeAssignment), remove);
    const button = event.target.closest("[data-experiment-action]");
    if (button) action(button);
  };
}
