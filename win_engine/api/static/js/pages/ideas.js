import { apiRequest } from "../api.js";
import { formatApiError, renderApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

const ideaState = { offset: 0, limit: 20, total: 0, status: "", selectedId: null, loading: false };

function dateValue(value) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function statusChip(status) {
  const tone = status === "published" ? "ok" : status === "archived" ? "warn" : status === "package_generated" ? "accent" : "";
  return chip(String(status || "unknown").replaceAll("_", " "), tone);
}

function renderIdeaList(data) {
  const root = $("ideasList");
  if (!root) return;
  const ideas = arr(data.ideas);
  ideaState.total = Number(data.total || 0);
  $("ideasCount").textContent = `${ideaState.total} saved idea${ideaState.total === 1 ? "" : "s"}`;
  $("ideasPageLabel").textContent = `Showing ${ideas.length ? ideaState.offset + 1 : 0}-${Math.min(ideaState.offset + ideas.length, ideaState.total)} of ${ideaState.total}`;
  $("ideasPrevBtn").disabled = ideaState.offset <= 0;
  $("ideasNextBtn").disabled = ideaState.offset + ideaState.limit >= ideaState.total;
  if (!ideas.length) {
    root.innerHTML = `<div class="creator-empty-state">No ideas match this filter. Save an original topic below; research and performance evidence will remain unavailable until collected.</div>`;
    return;
  }
  root.innerHTML = ideas.map((idea) => `
    <button type="button" class="ideas-card ${Number(idea.id) === Number(ideaState.selectedId) ? "selected" : ""}" data-idea-id="${Number(idea.id)}">
      <div class="ideas-card-head"><strong>${esc(idea.topic)}</strong>${statusChip(idea.status)}</div>
      <div class="ideas-card-meta">${esc(idea.format || "unknown")} / ${esc(idea.language || "unknown")} / ${esc(idea.region || "unknown")}</div>
      <p>${esc(idea.opportunity_explanation || "Research has not been run for this idea.")}</p>
      <div class="ideas-card-meta">Last research: ${esc(dateValue(idea.last_researched_at))} / Saved: ${esc(dateValue(idea.created_at))}</div>
    </button>`).join("");
}

function evidenceCard(idea) {
  const snapshot = idea.latest_research;
  if (!snapshot || !snapshot.evidence) {
    const reason = idea.research_is_stale
      ? "Creator fields changed after the saved research. Run Research now before generating; older dated snapshots remain preserved for traceability."
      : "Research unavailable. No search volume, trend percentage, competitor conclusion, or personal winning pattern is assumed.";
    return `<div class="creator-empty-state">${esc(reason)}</div>`;
  }
  const evidence = snapshot.evidence;
  const personal = evidence.personal_evidence || {};
  const results = arr(evidence.youtube_results);
  const competitors = results.length ? `
    <div class="ideas-evidence-list">${results.slice(0, 8).map((item) => `
      <div class="ideas-evidence-item"><strong>${esc(item.title || "Untitled public result")}</strong><span>${esc(item.channel_title || "Channel unavailable")} / Published: ${esc(dateValue(item.published_at))} / Views at capture: ${num(item.view_count)}</span></div>`).join("")}</div>` :
    `<div class="creator-empty-state">No relevant public results were returned in this dated snapshot.</div>`;
  return `
    <div class="ideas-evidence-summary">
      <div class="creator-card-heading">Dated research ${chip("Public observation", "accent")}</div>
      <p>${esc(evidence.opportunity_explanation || "Opportunity explanation unavailable.")}</p>
      <div class="ideas-card-meta">Captured: ${esc(dateValue(snapshot.captured_at))}</div>
    </div>
    <div class="ideas-evidence-summary">
      <div class="creator-card-heading">Personal evidence ${chip(personal.learning_allowed ? "Post-publish evidence" : "Unavailable", personal.learning_allowed ? "ok" : "warn")}</div>
      <p>${esc(personal.message || "Not enough personal evidence")}</p>
      <div class="ideas-card-meta">${num(personal.sample_size || 0)} comparable video(s) / ${esc(personal.confidence_label || "Collecting evidence")} / ${esc(personal.snapshot_window || "24h")}</div>
    </div>
    <div class="creator-card-heading">Relevant public results and publication dates</div>${competitors}`;
}

function renderIdeaDetail(idea) {
  const root = $("ideaDetail");
  if (!root) return;
  ideaState.selectedId = idea.id;
  const linked = Boolean(idea.published_video_link_id);
  const archived = idea.status === "archived";
  const generated = Boolean(idea.analysis_run_id);
  const demand = idea.latest_demand_research || null;
  root.innerHTML = `
    <div class="card-title"><span>Idea detail</span>${statusChip(idea.status)}</div>
    <h2 class="ideas-detail-title">${esc(idea.topic)}</h2>
    <p class="ideas-detail-notes">${esc(idea.notes || "No notes supplied.")}</p>
    <div class="ideas-facts">
      <div><span>Format / language</span><strong>${esc(idea.format || "unknown")} / ${esc(idea.language || "unknown")}</strong></div>
      <div><span>Region / duration</span><strong>${esc(idea.region || "unknown")} / ${idea.target_duration_seconds ? `${num(idea.target_duration_seconds)} sec` : "Not available"}</strong></div>
      <div><span>Generated package</span><strong>${generated ? `History run ${Number(idea.analysis_run_id)}` : "Not generated"}</strong></div>
      <div><span>Published link</span><strong>${linked ? `Linked record ${Number(idea.published_video_link_id)}` : "Not linked"}</strong></div>
    </div>
    <div class="creator-analysis-grid ideas-angles">
      <div class="creator-analysis-card"><div class="creator-card-heading">Search angle ${chip("Creator supplied")}</div><p>${esc(idea.search_angle || "Not supplied")}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Browse angle ${chip("Creator supplied")}</div><p>${esc(idea.browse_angle || "Not supplied")}</p></div>
      <div class="creator-analysis-card wide"><div class="creator-card-heading">Existing audience angle ${chip("Creator supplied")}</div><p>${esc(idea.audience_angle || "Not supplied")}</p></div>
    </div>
    <div class="creator-card-heading">Visual / on-screen plan</div>
    <p class="ideas-detail-notes">Visual: ${esc(idea.visual_or_background || "Not supplied")}<br>On-screen text: ${esc(idea.on_screen_text || "Not supplied")}<br>Emotion or intent: ${esc(idea.emotion_or_intent || "Not supplied")}</p>
    ${evidenceCard(idea)}
    <div class="ideas-evidence-summary"><div class="creator-card-heading">Topic-demand evidence ${demand ? chip(demand.classification, demand.stale ? "warn" : "accent") : chip("Unavailable", "warn")}</div><p>${demand ? (demand.stale ? "This demand snapshot is stale because relevant creator fields changed. Run demand research again." : "A current immutable demand snapshot is linked to this idea.") : "Demand research has not been run. No market-demand conclusion is assumed."}</p></div>
    <div id="ideaActionStatus" class="metric-sub" aria-live="polite"></div>
    <div class="creator-inline-actions ideas-actions">
      <button type="button" class="btn" data-idea-action="research" ${archived ? "disabled" : ""}>Research now</button>
      <button type="button" class="btn" data-idea-action="demand" ${archived ? "disabled" : ""}>Demand / outlier research</button>
      <button type="button" class="btn btn-primary" data-idea-action="generate" ${archived || idea.status === "published" ? "disabled" : ""}>Generate package</button>
      ${generated ? `<button type="button" class="btn" data-idea-action="history">Open package in History</button>` : ""}
      ${idea.status === "idea" ? `<button type="button" class="btn" data-idea-action="scripted">Mark scripted</button>` : ""}
      ${idea.status !== "archived" && idea.status !== "published" ? `<button type="button" class="btn" data-idea-action="published" ${linked ? "" : "disabled title='Link the generated History package to an owned YouTube video first.'"}>Mark published</button>` : ""}
      ${archived ? `<button type="button" class="btn" data-idea-action="restore">Restore idea</button>` : `<button type="button" class="btn" data-idea-action="archive">Archive</button>`}
    </div>
    <p class="metric-sub">Publishing remains manual in YouTube Studio. Mark published is enabled only after the generated package is linked to a verified owned video.</p>`;
}

async function loadIdeaDetail(id) {
  const root = $("ideaDetail");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading saved idea...</div>`;
  try {
    const data = await apiRequest(`/api/ideas/${Number(id)}`, { cache: "no-store" });
    renderIdeaDetail(data.idea || {});
  } catch (error) {
    if (root) renderApiError(root, error, "Could not load this idea.");
  }
}

export async function loadIdeasPage(resetOffset = false) {
  if (ideaState.loading) return;
  if (resetOffset) ideaState.offset = 0;
  ideaState.loading = true;
  const root = $("ideasList");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading ideas from SQLite...</div>`;
  const query = new URLSearchParams({ limit: String(ideaState.limit), offset: String(ideaState.offset) });
  if (ideaState.status) query.set("status", ideaState.status);
  try {
    const data = await apiRequest(`/api/ideas?${query.toString()}`, { cache: "no-store" });
    renderIdeaList(data);
  } catch (error) {
    if (root) renderApiError(root, error, "Could not load the idea backlog.");
  } finally {
    ideaState.loading = false;
  }
}

async function runIdeaAction(action) {
  const id = Number(ideaState.selectedId);
  if (!id) return;
  const status = $("ideaActionStatus");
  if (status) status.textContent = action === "generate" ? "Generating with the existing Creator engine..." : "Saving...";
  try {
    if (action === "history") {
      window.location.hash = "#history";
      return;
    }
    let data;
    if (action === "research" || action === "generate" || action === "demand") {
      const path = action === "demand" ? `/api/ideas/${id}/demand-research` : `/api/ideas/${id}/${action}`;
      data = await apiRequest(path, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: action === "generate" ? "{}" : undefined,
      });
      if (action === "demand") { await loadIdeaDetail(id); await loadIdeasPage(false); return; }
    } else {
      const nextStatus = action === "scripted" ? "scripted" : action === "published" ? "published" : action === "archive" ? "archived" : "idea";
      data = await apiRequest(`/api/ideas/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: nextStatus }) });
    }
    renderIdeaDetail(data.idea || {});
    await loadIdeasPage(false);
  } catch (error) {
    if (status) status.textContent = formatApiError(error, "The idea action failed.");
  }
}

export function mountIdeasPage() {
  const form = $("ideaCreateForm");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("ideaCreateStatus");
    const button = $("ideaCreateBtn");
    const durationRaw = $("ideaDuration").value.trim();
    const payload = {
      topic: $("ideaTopic").value.trim(), notes: $("ideaNotes").value.trim(), format: $("ideaFormat").value,
      language: $("ideaLanguage").value, region: $("ideaRegion").value,
      visual_or_background: $("ideaVisual").value.trim(), on_screen_text: $("ideaOnScreen").value.trim(),
      target_duration_seconds: durationRaw ? Number(durationRaw) : null,
      emotion_or_intent: $("ideaIntent").value.trim(), search_angle: $("ideaSearchAngle").value.trim(),
      browse_angle: $("ideaBrowseAngle").value.trim(), audience_angle: $("ideaAudienceAngle").value.trim(), status: "idea",
    };
    button.disabled = true;
    if (status) status.textContent = "Saving idea...";
    try {
      const data = await apiRequest("/api/ideas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      form.reset();
      ideaState.selectedId = data.idea.id;
      if (status) status.textContent = "Idea saved permanently in SQLite.";
      renderIdeaDetail(data.idea);
      await loadIdeasPage(true);
    } catch (error) {
      if (status) status.textContent = formatApiError(error, "Could not save this idea.");
    } finally {
      button.disabled = false;
    }
  });
  $("ideasStatusFilter").addEventListener("change", (event) => { ideaState.status = event.target.value; loadIdeasPage(true); });
  $("ideasRefreshBtn").addEventListener("click", () => loadIdeasPage(false));
  $("ideasPrevBtn").addEventListener("click", () => { ideaState.offset = Math.max(0, ideaState.offset - ideaState.limit); loadIdeasPage(false); });
  $("ideasNextBtn").addEventListener("click", () => { ideaState.offset += ideaState.limit; loadIdeasPage(false); });
  $("ideasList").addEventListener("click", (event) => {
    const card = event.target.closest("[data-idea-id]");
    if (card) loadIdeaDetail(card.dataset.ideaId);
  });
  $("ideaDetail").addEventListener("click", (event) => {
    const button = event.target.closest("[data-idea-action]");
    if (button && !button.disabled) runIdeaAction(button.dataset.ideaAction);
  });
}
