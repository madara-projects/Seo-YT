import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { $, arr, chip, esc, num } from "../utils.js";

let selected = { type: null, id: null };

const date = (v) => (v ? new Date(v).toLocaleString() : "Not available");

function cards(items, type) {
  if (!items.length) {
    return `
      <div class="empty-state-card" style="margin:8px 0">
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg>
        </div>
        <h4>No Saved ${type === "channel" ? "Channels" : "Videos"}</h4>
        <p>No saved ${type}s match this filter. Add public ${type}s above for read-only tracking and baseline outlier calculations.</p>
      </div>`;
  }
  return items.map((x) => `
    <button type="button" class="ideas-card ${selected.type === type && Number(selected.id) === Number(x.id) ? "selected" : ""}" data-watch-type="${type}" data-watch-id="${Number(x.id)}">
      <div class="ideas-card-head">
        <strong>${esc(x.title || (type === "channel" ? x.channel_id : x.video_id))}</strong>
        ${chip(x.state === "active" ? "Active Monitoring" : "Archived", x.state === "active" ? "ok" : "warn")}
      </div>
      <div class="ideas-card-meta" style="font-size:11px;color:var(--text-sub);margin:4px 0">
        ${type === "channel" ? `ID: ${esc(x.channel_id)}` : `Channel: ${esc(x.channel_title || "Channel unavailable")}`} &bull; Last research: ${esc(date(x.last_researched_at))}
      </div>
      ${type === "video"
        ? `<p style="font-size:12px;color:var(--text-muted);margin:4px 0">Views: <strong>${num((x.latest_snapshot || {}).view_count)}</strong> &bull; Outlier: <strong style="color:var(--accent)">${esc((x.outlier || {}).status || "not analyzed")}</strong></p>`
        : `<p style="font-size:12px;color:var(--text-muted);margin:4px 0">Subscribers: <strong>${num(x.subscriber_count)}</strong> &bull; Videos: <strong>${num(x.video_count)}</strong></p>`}
    </button>`).join("");
}

export async function loadWatchlist() {
  const state = $("watchState")?.value ?? "active";
  const q = $("watchSearch")?.value || "";
  try {
    const [c, v] = await Promise.all([
      apiRequest(`/api/watchlist/channels${state ? `?state=${encodeURIComponent(state)}` : ""}`, { cache: "no-store" }),
      apiRequest(`/api/watchlist/videos?state=${encodeURIComponent(state)}&q=${encodeURIComponent(q)}`, { cache: "no-store" }),
    ]);
    if ($("watchChannels")) $("watchChannels").innerHTML = cards(arr(c.channels), "channel");
    if ($("watchVideos")) $("watchVideos").innerHTML = cards(arr(v.videos), "video");
  } catch (e) {
    if ($("watchStatus")) $("watchStatus").textContent = formatApiError(e, "Watchlist unavailable.");
  }
}

function detail(item, type) {
  const snaps = arr(item.snapshots);
  const out = item.outlier || {};
  const isPossibleOutlier = out.status === "possible_outlier";

  $("watchDetail").innerHTML = `
    <div class="card-title">
      <span>${type === "channel" ? "Channel" : "Video"} Intelligence</span>
      ${chip(item.source || "Public YouTube Data", "accent")}
    </div>
    <h2 class="ideas-detail-title">${esc(item.title || (type === "channel" ? item.channel_id : item.video_id))}</h2>
    <p class="ideas-detail-notes">${esc(item.notes || "No creator notes entered.")}</p>

    <div class="ideas-facts">
      <div><span>Identifier</span><strong>${esc(type === "channel" ? item.channel_id : item.video_id)}</strong></div>
      <div><span>Monitoring state</span><strong>${esc(item.state)}</strong></div>
      ${type === "video" ? `
        <div><span>Format / Language</span><strong>${esc(item.format || "unknown")} / ${esc(item.language || "unknown")}</strong></div>
        <div><span>Published</span><strong>${esc(date(item.published_at))}</strong></div>` : ""}
    </div>

    ${type === "video" ? `
      <div class="ideas-evidence-summary">
        <div class="creator-card-heading">
          <span>Outlier analysis &amp; peer baseline</span>
          ${chip(out.provenance || "Unavailable", isPossibleOutlier ? "warn" : "")}
        </div>
        <p>${esc(out.explanation || "Not analyzed yet. At least five comparable peer upload observations from this channel are required.")}</p>
        ${out.status ? `
          <div class="intel-evidence" style="margin-top:8px">
            <div>
              <strong>Observed Multiplier</strong>
              <span>${num(out.relative_multiplier)}x relative to peer median (${num(out.baseline_median_views)} views)</span>
              <small>Status: ${esc(out.status)} / Sample: ${num(out.sample_size)} comparable peer videos</small>
            </div>
          </div>` : ""}
        <div class="ideas-card-meta" style="margin-top:6px">Observational outlier signal only. This is not a viral prediction or growth guarantee.</div>
      </div>` : ""}

    <div class="creator-card-heading">Immutable public snapshots (${snaps.length})</div>
    <div class="intel-evidence">
      ${snaps.length ? snaps.map((s) => `
        <div>
          <strong>Captured: ${esc(date(s.captured_at))} / Source: ${esc(s.source)}</strong>
          <span>${type === "channel" ? `${num(s.subscriber_count)} subscribers / ${num(s.video_count)} videos` : `${num(s.view_count)} views / ${num(s.like_count)} likes / ${num(s.comment_count)} comments`}</span>
        </div>`).join("") : "<div><span>Research has not been run yet; public metrics are unavailable.</span></div>"}
    </div>

    <div id="watchActionStatus" class="metric-sub" aria-live="polite"></div>
    <div class="creator-inline-actions ideas-actions" style="margin-top:16px">
      <button type="button" class="btn" data-watch-action="research">Research / refresh</button>
      ${type === "video" ? '<button type="button" class="btn" data-watch-action="outlier">Analyze outlier</button>' : ""}
      <button type="button" class="btn" data-watch-action="toggle">${item.state === "active" ? "Archive" : "Restore"}</button>
    </div>
    <p class="metric-sub">Public observations and local heuristics do not establish causation or guarantee future performance.</p>`;
}

async function open(type, id) {
  selected = { type, id };
  const root = $("watchDetail");
  if (root) root.innerHTML = `<div class="creator-empty-state">Loading monitoring evidence...</div>`;
  try {
    const d = await apiRequest(`/api/watchlist/${type}s/${id}`, { cache: "no-store" });
    detail(d[type], type);
  } catch (e) {
    if (root) root.textContent = formatApiError(e, "Could not load evidence.");
  }
}

async function action(kind, button) {
  button.disabled = true;
  try {
    let d;
    if (kind === "research") {
      d = await apiRequest(`/api/watchlist/${selected.type}s/${selected.id}/research`, { method: "POST" });
    } else if (kind === "outlier") {
      d = await apiRequest(`/api/watchlist/videos/${selected.id}/analyze-outlier`, { method: "POST" });
    } else {
      const current = await apiRequest(`/api/watchlist/${selected.type}s/${selected.id}`);
      d = await apiRequest(`/api/watchlist/${selected.type}s/${selected.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: current[selected.type].state === "active" ? "archived" : "active" }),
      });
    }
    detail(d[selected.type] || d.video || d.channel, selected.type);
    await loadWatchlist();
  } catch (e) {
    if ($("watchActionStatus")) $("watchActionStatus").textContent = formatApiError(e, "Action failed.");
  } finally {
    button.disabled = false;
  }
}

export function mountWatchlistPage() {
  if (!$("watchChannelForm")) return;
  $("watchChannelForm").onsubmit = async (e) => {
    e.preventDefault();
    const b = e.submitter || e.currentTarget.querySelector('button[type="submit"]');
    if (b) b.disabled = true;
    try {
      await apiRequest("/api/watchlist/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel_id: $("watchChannelId").value, notes: $("watchChannelNotes").value }),
      });
      e.target.reset();
      await loadWatchlist();
    } catch (x) {
      if ($("watchStatus")) $("watchStatus").textContent = formatApiError(x, "Could not add channel.");
    } finally {
      if (b) b.disabled = false;
    }
  };

  $("watchVideoForm").onsubmit = async (e) => {
    e.preventDefault();
    const b = e.submitter || e.currentTarget.querySelector('button[type="submit"]');
    if (b) b.disabled = true;
    try {
      await apiRequest("/api/watchlist/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: $("watchVideoId").value, notes: $("watchVideoNotes").value }),
      });
      e.target.reset();
      await loadWatchlist();
    } catch (x) {
      if ($("watchStatus")) $("watchStatus").textContent = formatApiError(x, "Could not add video.");
    } finally {
      if (b) b.disabled = false;
    }
  };

  $("watchRefreshBtn").onclick = loadWatchlist;
  $("watchState").onchange = loadWatchlist;
  $("watchSearch").oninput = () => loadWatchlist();

  for (const id of ["watchChannels", "watchVideos"]) {
    $(id).onclick = (e) => {
      const c = e.target.closest("[data-watch-id]");
      if (c) open(c.dataset.watchType, Number(c.dataset.watchId));
    };
  }

  $("watchDetail").onclick = (e) => {
    const b = e.target.closest("[data-watch-action]");
    if (b && !b.disabled) action(b.dataset.watchAction, b);
  };
}
