import { apiRequest } from "./api.js";
import { formatApiError, renderApiError } from "./errors.js";
import { $, arr, esc, num } from "./utils.js";
import { frontendState, invalidateHistorySummary } from "./state.js";
import { isPageKey, normalizePageKey, pages } from "./navigation.js";
import { mountCreatorPage, TEMPLATE_TEXT } from "./pages/creator.js";
import { loadIdeasPage, mountIdeasPage } from "./pages/ideas.js";
import { loadDemand, mountDemandPage } from "./pages/demand.js";
import { loadWatchlist, mountWatchlistPage } from "./pages/watchlist.js";
import { loadAudits, mountAuditsPage } from "./pages/audits.js";
import { loadExperiments, mountExperimentsPage } from "./pages/experiments.js";

    async function getHistorySummary(force = false) {
      const cacheFresh = frontendState.historySummaryCache && (Date.now() - frontendState.historySummaryFetchedAt < 15000);
      if (!force && cacheFresh) return frontendState.historySummaryCache;
      if (frontendState.historySummaryRequest) return frontendState.historySummaryRequest;
      // A request that was in flight when the summary was invalidated (a delete or
      // a new link) carries old data: it never fills the cache, and its callers get
      // the newer summary instead.
      const generation = frontendState.historySummaryGeneration;
      const request = apiRequest("/api/history", { cache: "no-store" }).then((data) => {
        if (generation !== frontendState.historySummaryGeneration) return getHistorySummary();
        frontendState.historySummaryCache = data;
        frontendState.historySummaryFetchedAt = Date.now();
        return data;
      }).finally(() => {
        if (frontendState.historySummaryRequest === request) frontendState.historySummaryRequest = null;
      });
      frontendState.historySummaryRequest = request;
      return request;
    }

    // Toast notification display helper. A newer toast restarts the timer, and a
    // longer message (a partial delete, a refresh warning) stays up long enough to read.
    let toastTimer = null;
    function showToast(msg) {
      const toast = $("toastNotification");
      if (!toast) return;
      toast.textContent = msg || "Copied to clipboard.";
      toast.classList.add("show");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove("show"), Math.max(2200, Math.min(8000, toast.textContent.length * 50)));
    }

    // Dynamic Theme Engine
    function setTheme(themeKey) {
      const validThemes = ["obsidian", "pearl", "light"];
      const safeTheme = validThemes.includes(themeKey) ? themeKey : "obsidian";
      document.documentElement.setAttribute("data-theme", safeTheme);
      try { localStorage.setItem("yt_seo_theme", safeTheme); } catch (_) {}
      const sel = $("themeSelector");
      if (sel) sel.value = safeTheme;
    }

    const savedTheme = (function() { try { return localStorage.getItem("yt_seo_theme") || "obsidian"; } catch(_) { return "obsidian"; } })();
    setTheme(savedTheme);

    const SIDEBAR_STORAGE_KEY = "yt_seo_sidebar_collapsed";

    function setSidebarCollapsed(collapsed, persist = true) {
      const isCollapsed = Boolean(collapsed);
      document.body.classList.toggle("sidebar-collapsed", isCollapsed);
      const toggle = $("sidebarToggle");
      if (toggle) {
        toggle.setAttribute("aria-expanded", String(!isCollapsed));
        toggle.setAttribute("aria-label", isCollapsed ? "Expand sidebar" : "Collapse sidebar");
        toggle.title = isCollapsed ? "Expand sidebar" : "Collapse sidebar";
      }
      document.querySelectorAll(".nav-item").forEach((item) => {
        if (isCollapsed) item.title = item.textContent.trim().replace(/\s+/g, " ");
        else item.removeAttribute("title");
      });
      if (persist) {
        try { localStorage.setItem(SIDEBAR_STORAGE_KEY, isCollapsed ? "1" : "0"); } catch (_) {}
      }
    }

    const savedSidebarCollapsed = (function() {
      try { return localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1"; } catch (_) { return false; }
    })();
    setSidebarCollapsed(savedSidebarCollapsed, false);

    const sidebarToggle = $("sidebarToggle");
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", () => {
        setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
      });
    }

    window.addEventListener("DOMContentLoaded", () => {
      const sel = $("themeSelector");
      if (sel) {
        sel.value = savedTheme;
        sel.addEventListener("change", (e) => setTheme(e.target.value));
      }
    });

    // 1-Click Starter Templates (the same sample text as the Creator's own template buttons).
    // They fill only the dashboard box; the Creator keeps its own input and state.
    function applyTemplate(key) {
      if (!Object.prototype.hasOwnProperty.call(TEMPLATE_TEXT, key)) return;
      const box = $("dashQuickScript");
      if (!box) return;
      box.value = TEMPLATE_TEXT[key];
      box.focus();
      showToast("Sample idea loaded into the quick generator.");
    }

    function switchPage(key, updateHistory = true) {
      const pageKey = isPageKey(key) ? key : "dashboard";
      const current = pages[pageKey];

      if ($("topTitle")) $("topTitle").innerHTML = current.title;
      if ($("topSub")) $("topSub").innerHTML = current.sub;

      document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
      document.querySelectorAll(".page-view").forEach((el) => el.classList.remove("active"));

      const navEl = $(current.navId);
      const viewEl = $(current.viewId);

      if (navEl) navEl.classList.add("active");
      if (viewEl) viewEl.classList.add("active");

     try {
       if (updateHistory && window.location.hash !== "#" + pageKey && history.pushState) {
          history.pushState(null, null, "#" + pageKey);
        } else if (updateHistory && window.location.hash !== "#" + pageKey) {
          window.location.hash = pageKey;
        }
      } catch (_) {}

      const appContainer = document.querySelector("main.app-container");
      if (appContainer) appContainer.scrollTop = 0;

      if (pageKey === "dashboard") {
        loadHistoryFeed();
        loadCohortLearning();
      }
      if (pageKey === "ideas") loadIdeasPage();
      if (pageKey === "demand") loadDemand();
      if (pageKey === "watchlist") loadWatchlist();
      if (pageKey === "audits") loadAudits();
      if (pageKey === "experiments") loadExperiments();
      if (pageKey === "analytics") loadAnalyticsPage();
      if (pageKey === "history") loadSavedHistory();
    }

    // Reasons the OAuth callback appends as ?youtube=error&reason=<code>.
    const OAUTH_ERROR_REASONS = {
      access_denied: "Access was declined on the Google consent screen, so nothing was connected.",
      expired_state: "The connection request expired or was already used. Start the connection again.",
      missing_scopes: "Both permissions are needed: allow access to your YouTube account and to YouTube Analytics, then connect again.",
      no_refresh_token: "Google did not return a lasting token. Remove Win-Engine in your Google Account permissions, then connect again.",
      no_channel: "That Google account has no YouTube channel. Connect with the account that owns your channel.",
      not_configured: "YouTube OAuth is not set up on this server. Add the OAuth settings to .env and restart it.",
      connect_failed: "Google's reply could not be completed, so nothing was connected. Try connecting again.",
      unknown: "Google reported an error it did not identify, so nothing was connected. Try connecting again.",
    };

    // The server only ever sends a short code like "access_denied". Anything else in
    // the address was typed or linked by someone else, so it is never shown.
    const OAUTH_REASON_PATTERN = /^[a-z_]{1,40}$/;

    function oauthReturnMessage(outcome, reason) {
      if (outcome === "connected") return "YouTube channel connected with read-only access.";
      if (Object.prototype.hasOwnProperty.call(OAUTH_ERROR_REASONS, reason)) return OAUTH_ERROR_REASONS[reason];
      return OAUTH_REASON_PATTERN.test(reason)
        ? `YouTube connection failed (${reason}). Nothing was changed; try connecting again.`
        : "YouTube connection failed. Nothing was changed; try connecting again.";
    }

    // The callback already synced the channel, so this only reports the outcome;
    // the page's normal loads pick up the saved data. Nothing here writes or spends quota.
    function handleOAuthReturn() {
      if (frontendState.oauthRedirectHandled) return;
      const params = new URLSearchParams(window.location.search);
      const outcome = params.get("youtube");
      if (outcome !== "connected" && outcome !== "error") return;
      frontendState.oauthRedirectHandled = true;
      const message = oauthReturnMessage(outcome, String(params.get("reason") || ""));
      // A failed connect started from Settings, so show the reason there.
      const openSettings = outcome === "error" && !window.location.hash;
      params.delete("youtube");
      params.delete("reason");
      if (window.history.replaceState) {
        const query = params.toString();
        window.history.replaceState({}, document.title, window.location.pathname + (query ? "?" + query : "") + (openSettings ? "#settings" : window.location.hash));
      }
      const notice = $("settOAuthNotice");
      if (notice) {
        notice.textContent = message;
        notice.className = "alert-banner " + (outcome === "connected" ? "alert-ok" : "alert-err");
      }
      if (openSettings) switchPage("settings", false);
      showToast(message);
    }

    function route() {
      const hash = normalizePageKey(window.location.hash || "#dashboard");
      const now = Date.now();
      if (hash === frontendState.lastRoutedHash && now - frontendState.lastRoutedAt < 100) return;
      frontendState.lastRoutedHash = hash;
      frontendState.lastRoutedAt = now;
      switchPage(hash, false);
      handleOAuthReturn();
    }

    window.addEventListener("hashchange", route);
    window.addEventListener("popstate", route);

    // Quick Launch Handler from Dashboard
    const dashQuickScript = $("dashQuickScript");
    const dashQuickLaunchBtn = $("dashQuickLaunchBtn");

    if (dashQuickLaunchBtn) {
      dashQuickLaunchBtn.addEventListener("click", () => {
        const val = dashQuickScript.value.trim();
        if (!val) { alert("Please enter a video topic or script idea first."); return; }
        $("scriptInput").value = val;
        $("language").value = $("dashQuickLang").value;
        $("region").value = $("dashQuickRegion").value;
        window.location.hash = "#creator";
        switchPage("creator");
        setTimeout(() => { $("analyzeBtn").click(); }, 200);
      });
    }

    // A count YouTube did not report (a hidden subscriber count, missing statistics) is unknown, never zero.
    const countText = (value) => value === null || value === undefined || value === "" ? "Unavailable" : num(value);

    function watchTimeText(minutes) {
      if (typeof minutes === "number" && minutes >= 60) return (minutes / 60).toFixed(1) + " hrs";
      if (typeof minutes === "number" && minutes > 0) return minutes + " mins";
      if (minutes === 0) return "0 mins";
      return "Unavailable";
    }

    const SYNC_PARTS = { uploads: "Uploads", analytics: "YouTube Analytics" };

    // The parts of the last sync YouTube did not return, e.g. ["uploads", "analytics"].
    function syncGapText(failures) {
      const names = arr(failures).map((part) => SYNC_PARTS[part] || String(part));
      return names.length ? names.join(" and ") + " could not be read in the last sync" : "";
    }

    // The latest sync, preferring the live status: it leaves out a sync that belongs to a previous channel.
    function latestSync() {
      const status = frontendState.latestChannelStatus;
      if (status) {
        const sync = status.latest_sync || {};
        return { ...(sync.data || {}), synced_at: sync.synced_at };
      }
      return (frontendState.latestOwnedPerformance || {}).latest_sync || {};
    }

    function channelStatsText(sync, linkedCount = null) {
      const channel = sync.channel || {};
      const current = sync.current_28_days || {};
      const part = (value, label, missing) => value === null || value === undefined || value === "" ? missing + " unavailable" : num(value) + " " + label;
      const parts = [
        part(channel.subscribers, "subscribers", "Subscribers"),
        part(channel.real_total_views, "lifetime views", "Lifetime views"),
        part(current.views, "views in the last 28 processed days", "28-day views"),
      ];
      if (typeof linkedCount === "number") parts.push(`${linkedCount} linked ${linkedCount === 1 ? "video" : "videos"}`);
      return parts.join(" / ");
    }

    // Channel figures come from two responses that load in parallel: the history
    // summary (linked videos, the linked-video watch time) and the connection
    // status (the latest sync and what it failed to read). Both loaders call this,
    // so the page ends the same whichever response arrives last.
    function renderChannelSummary() {
      const owned = frontendState.latestOwnedPerformance || {};
      const status = frontendState.latestChannelStatus;
      const sync = latestSync();
      const channel = sync.channel || {};
      const current = sync.current_28_days || {};
      const ownedChannel = owned.channel || {};
      const title = (status ? (status.channel || {}).title : "") || ownedChannel.title || channel.title || "";
      const connected = status ? Boolean(status.connected) : Boolean(ownedChannel.id || title);
      const channelName = connected ? title || "YouTube Channel" : "No channel connected";
      const linkedCount = typeof owned.linked_videos_count === "number" ? owned.linked_videos_count : null;
      const failures = arr(sync.partial_failures);
      const gaps = syncGapText(failures);
      const set = (id, text) => { const node = $(id); if (node) node.textContent = text; };

      // 28-day views and watch time come only from the channel's YouTube Analytics totals.
      const hasViews = current.views !== null && current.views !== undefined;
      set("dashMetricViews", connected ? countText(current.views) : "Not available");
      set("dashMetricViewsSub", !connected
        ? "Connect and refresh your channel in Settings."
        : hasViews ? "Real 28-day channel views synced from YouTube."
          : failures.includes("analytics") ? "YouTube Analytics could not be read in the last sync."
            : "YouTube Analytics has not reported 28-day views yet.");

      // Without a channel total, the summary falls back to linked videos' own watch time,
      // which is shown under its own label. When the summary's sync has a total, its
      // figure is that (possibly older) channel total, never a linked-video sum.
      const fallbackMinutes = owned.estimated_watch_minutes;
      const summaryHasChannelTotal = typeof (((owned.latest_sync || {}).current_28_days) || {}).estimatedMinutesWatched === "number";
      if (typeof current.estimatedMinutesWatched === "number") {
        set("dashMetricWatch", watchTimeText(current.estimatedMinutesWatched));
        set("dashMetricWatchSub", "Total estimated watch time from 28-day sync.");
      } else if (!summaryHasChannelTotal && typeof fallbackMinutes === "number" && fallbackMinutes > 0 && linkedCount > 0) {
        // The summary adds each linked video's highest snapshot, and only videos with watch time count.
        const withTime = typeof owned.linked_videos_with_watch_time === "number" ? owned.linked_videos_with_watch_time : linkedCount;
        const scope = withTime < linkedCount
          ? `${withTime} of your ${linkedCount} linked videos`
          : `your ${linkedCount} linked ${linkedCount === 1 ? "video" : "videos"}`;
        set("dashMetricWatch", watchTimeText(fallbackMinutes));
        set("dashMetricWatchSub", `Across ${scope}, at each video's highest snapshot, not a 28-day channel total.`);
      } else {
        set("dashMetricWatch", "Unavailable");
        set("dashMetricWatchSub", "Not available until YouTube Analytics sync succeeds.");
      }

      set("anaSubscribers", connected ? countText(channel.subscribers) : "--");
      set("anaLifetimeViews", connected ? countText(channel.real_total_views) : "--");
      set("ana28dViews", connected ? countText(current.views) : "--");
      set("anaWatchTime", connected ? watchTimeText(current.estimatedMinutesWatched) : "--");
      const period = sync.period || {};
      const periodText = period.start && period.end ? ` / Analytics period ${period.start} to ${period.end}` : "";
      set("anaSyncStatus", `Last synced: ${sync.synced_at ? historyDate(sync.synced_at) : "Never"}${periodText}${gaps ? " / " + gaps : ""}`);
      if ($("anaSyncStatus")) $("anaSyncStatus").style.color = "";

      set("dashChannelName", channelName);
      set("anaChannelName", channelName);
      set("dashChannelAvatar", connected ? channelName.charAt(0).toUpperCase() : "");
      const disconnectedText = "Connect YouTube in Settings to load actual performance.";
      set("dashChannelStats", connected ? channelStatsText(sync, linkedCount)
        : status && !status.configured ? "OAuth setup required." : status ? "Ready to connect." : disconnectedText);
      set("anaChannelStats", connected ? channelStatsText(sync, linkedCount) : disconnectedText);
      set("dashChannelLastSync", sync.synced_at ? historyDate(sync.synced_at) : connected ? "Not synced yet" : "Not connected");
      set("dashChannelLinked", linkedCount === null ? "Unavailable" : String(linkedCount));

      const chipNode = $("dashChannelChip");
      if (chipNode) {
        chipNode.className = connected ? "chip chip-ok" : "chip";
        if (connected) chipNode.innerHTML = `<span class="dot"></span> Connected`;
        else chipNode.textContent = frontendState.channelStatusFailed && !status ? "Status unavailable"
          : status && !status.configured ? "OAuth setup required" : "Not connected";
      }
    }

    // History table dates, in IST as the column headers say.
    function historyShortDate(value) {
      return new Date(value).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    function historyRowActions(runId) {
      if (!Number.isInteger(runId) || runId <= 0) {
        return `<button class="btn" style="padding:2px 8px;font-size:11px" disabled title="Reload history to restore this record ID">Link unavailable</button>`;
      }
      return `<a href="#history" class="btn" style="padding:2px 8px;font-size:11px" data-action="inspect-run" data-run-id="${runId}">Inspect</a>
                <button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)" data-action="link-video" data-run-id="${runId}">Link</button>
                <button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.3);color:#ef4444" data-action="delete-run" data-run-id="${runId}">Delete</button>`;
    }

    // Load Real Recent Runs from SQLite via API
    async function loadHistoryFeed(force = false) {
      try {
        const data = await getHistorySummary(force);
        const runs = (data.learning || {}).recent_runs || [];
        const scorecard = data.scorecard || {};
        frontendState.latestOwnedPerformance = data.owned_performance || {};
        renderChannelSummary();

        // Avg Opportunity Score Card
        if (scorecard.total_runs !== undefined) {
          // A missing average reads "Not available" on its own, never "Not available / 100".
          const scoreText = (value, round, scale) => typeof value === "number" && Number.isFinite(value) ? round(value) + " / " + scale : "Not available";
          const oppText = scoreText(scorecard.avg_opportunity_score, Math.round, 100);
          if ($("dashMetricOpp")) $("dashMetricOpp").textContent = oppText;
          if ($("dashMetricOppSub")) $("dashMetricOppSub").textContent = `Calculated from your ${num(scorecard.total_runs)} saved analyses.`;
          if ($("anaTotalRuns")) $("anaTotalRuns").textContent = num(scorecard.total_runs);
          if ($("anaAvgTitle")) $("anaAvgTitle").textContent = scoreText(scorecard.avg_title_score, (value) => Math.round(value * 10) / 10, 10);
          if ($("anaAvgOpp")) $("anaAvgOpp").textContent = oppText;
        } else if ($("anaTotalRuns")) {
          $("anaTotalRuns").textContent = "Not available";
        }

        const dashBody = $("dashHistoryBody");
        const anaBody = $("anaHistoryBody");

        if (runs.length === 0) {
          const emptyRow = `<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:16px">No analysis runs yet. Generate a package to populate your SQLite database.</td></tr>`;
          if (dashBody) dashBody.innerHTML = emptyRow;
          if (anaBody) anaBody.innerHTML = emptyRow;
          return;
        }

        const rowsHtml = runs.map((run) => {
          const dtStr = run.created_at ? historyShortDate(run.created_at) : "Recently";
          return `
            <tr>
              <td style="font-weight:600;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span class="chip">${num(run.title_score)} / 10</span></td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score)}</span> / 100</td>
              <td style="font-size:12px;color:var(--text-muted)">${dtStr}</td>
              <td style="display:flex;gap:6px">
                ${historyRowActions(Number(run.id))}
              </td>
            </tr>`;
        }).join("");

        const anaRowsHtml = runs.map((run) => {
          const dtStr = run.created_at ? historyShortDate(run.created_at) : "Recently";
          return `
            <tr>
              <td style="font-size:12px;color:var(--text-muted)">${dtStr} IST</td>
              <td style="font-weight:600;max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score)}</span> / 100</td>
              <td><span class="chip">${num(run.title_score)} / 10</span></td>
              <td style="display:flex;gap:6px">
                ${historyRowActions(Number(run.id))}
              </td>
            </tr>`;
        }).join("");

        if (dashBody) dashBody.innerHTML = rowsHtml;
        if (anaBody) anaBody.innerHTML = anaRowsHtml;
      } catch (err) {
        const message = esc(formatApiError(err, "History could not be loaded."));
        const errorRow = `<tr><td colspan="5" style="color:var(--bad);text-align:center;padding:16px">${message}</td></tr>`;
        if ($("dashHistoryBody")) $("dashHistoryBody").innerHTML = errorRow;
        if ($("anaHistoryBody")) $("anaHistoryBody").innerHTML = errorRow;
        // The stored count is unknown, not zero, when the summary could not be read.
        if ($("anaTotalRuns")) $("anaTotalRuns").textContent = "Not available";
      }
    }

    // Shell and History controls are wired from data attributes through delegated
    // listeners, so the page runs without inline handlers (script-src 'self').
    const CLICK_ACTIONS = {
      "apply-template": (node) => applyTemplate(node.dataset.template),
      // "Inspect" on a recent-package row opens that package in History.
      "inspect-run": (node) => { switchPage("history"); openHistoryRun(Number(node.dataset.runId)); },
      "open-run": (node) => openHistoryRun(Number(node.dataset.runId)),
      "close-run": () => closeHistoryDetail(),
      "link-video": (node) => linkVideoPrompt(Number(node.dataset.runId)),
      "delete-run": (node) => deleteHistoryRun(Number(node.dataset.runId)),
      "delete-selected-runs": () => deleteSelectedHistoryRuns(),
      "refresh-linked-video": (node) => refreshLinkedVideo(Number(node.dataset.linkId), node),
      "save-comparable-metadata": (node) => saveComparableMetadata(Number(node.dataset.linkId), Number(node.dataset.runId)),
      "refresh-history-performance": (node) => refreshHistoryPerformance(Number(node.dataset.linkId), Number(node.dataset.runId), node),
    };

    document.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const pageLink = target.closest("[data-page]");
      if (pageLink) {
        event.preventDefault();
        switchPage(pageLink.dataset.page);
        return;
      }
      const actionNode = target.closest("[data-action]");
      const action = actionNode ? CLICK_ACTIONS[actionNode.dataset.action] : null;
      if (!action) return;
      if (actionNode.tagName === "A") event.preventDefault();
      action(actionNode);
    });

    document.addEventListener("change", (event) => {
      const target = event.target;
      if (target instanceof Element && target.dataset.action === "select-run") toggleHistoryRunSelection(Number(target.dataset.runId), target.checked);
    });

    if ($("historySearch")) $("historySearch").addEventListener("input", (event) => filterHistoryRuns(event.target.value));
    if ($("historySelectAll")) $("historySelectAll").addEventListener("change", (event) => toggleAllVisibleHistory(event.target.checked));

    // A package's linked video loses its collected evidence with it; say so before deleting.
    function linkedEvidenceNote(ids) {
      const runs = ids.map((id) => savedHistoryRuns.find((run) => Number(run.id) === Number(id)));
      if (runs.some((run) => !run)) {
        return " If a package is linked to a video, that video's collected snapshots, audits and experiment assignments are deleted with it.";
      }
      const linked = runs.filter((run) => run.linked_youtube_video_id).length;
      if (!linked) return "";
      if (ids.length === 1) return " Its linked video's collected snapshots, audits and experiment assignments are deleted with it.";
      return ` ${linked === ids.length ? "All of them are" : linked + " of them are"} linked to a video; those videos' collected snapshots, audits and experiment assignments are deleted with them.`;
    }

    async function deleteHistoryRun(runId) {
      if (!confirm("Delete this saved package? It will be removed from this device and marked deleted for your synced devices." + linkedEvidenceNote([runId]))) return;
      return deleteHistoryRuns([Number(runId)], false);
    }

    async function deleteSelectedHistoryRuns() {
      const ids = [...selectedHistoryRunIds];
      if (!ids.length) return;
      if (!confirm("Delete " + ids.length + " selected packages? They will be removed locally and marked deleted in cloud sync for every synced device." + linkedEvidenceNote(ids))) return;
      return deleteHistoryRuns(ids, true);
    }

    // The bulk endpoint takes at most 100 IDs a request, so a larger selection goes
    // in batches. The server deletes each batch completely or not at all.
    const HISTORY_DELETE_BATCH = 100;

    // A delete only asks the background sync to run; it does not wait for the cloud.
    function cloudDeletionNote(cloudSync) {
      const sync = cloudSync && typeof cloudSync === "object" ? cloudSync : {};
      if (sync.enabled === false || sync.state === "disabled") return " Cloud sync is off; deleted on this device only.";
      if (sync.configured === false || sync.state === "unconfigured") return " Cloud sync is not configured; deleted on this device only.";
      if (sync.run_requested === true) return " Cloud deletion requested; your synced devices update after the next sync.";
      return " Cloud deletion is saved and will be sent when cloud sync next runs.";
    }

    async function deleteHistoryRuns(runIds, bulk) {
      const ids = runIds.map(Number);
      const deleted = [];
      let cloudSync = null;
      let failure = null;
      const bulkButton = $("historyBulkDeleteBtn");
      if (bulk && bulkButton) bulkButton.disabled = true;
      const batches = bulk ? [] : [ids.slice(0, 1)];
      if (bulk) for (let start = 0; start < ids.length; start += HISTORY_DELETE_BATCH) batches.push(ids.slice(start, start + HISTORY_DELETE_BATCH));
      // One batch failing (a package already deleted elsewhere, a rate limit) does not stop the others.
      for (const batch of batches) {
        try {
          const result = bulk
            ? await apiRequest("/api/history/runs", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_ids: batch }) })
            : await apiRequest(`/api/history/runs/${batch[0]}`, { method: "DELETE" });
          deleted.push(...(Array.isArray(result.deleted_run_ids) ? result.deleted_run_ids.map(Number) : batch));
          if (result.cloud_sync) cloudSync = result.cloud_sync;
        } catch (err) {
          if (!failure) failure = err;
        }
      }
      deleted.forEach((id) => selectedHistoryRunIds.delete(id));
      if (!deleted.length) {
        updateHistorySelectionControls();
        showToast(formatApiError(failure, "Could not delete selected package(s)."));
        return;
      }
      const requested = bulk ? ids.length : 1;
      const summary = failure ? `Deleted ${deleted.length} of ${requested} packages.`
        : requested === 1 ? "Saved package deleted." : deleted.length + " packages deleted.";
      showToast(summary + cloudDeletionNote(cloudSync) +
        (failure ? " The rest were not deleted: " + formatApiError(failure, "Request failed.") : ""));
      if ($("historyDetail")) $("historyDetail").classList.add("hidden");
      invalidateHistorySummary();
      loadHistoryFeed(true);
      await loadSavedHistory();
    }

    // Relinking deletes what the current video collected, so the server asks first (HTTP 409).
    // The dialog is plain text; counts are coerced to numbers and labels never reach innerHTML.
    function relinkConfirmationText(error) {
      const details = error.details && typeof error.details === "object" ? error.details : {};
      const evidence = details.evidence && typeof details.evidence === "object" ? details.evidence : {};
      const counts = Object.entries(evidence)
        .map(([label, count]) => [String(label), Number(count)])
        .filter(([, count]) => Number.isFinite(count) && count > 0)
        .map(([label, count]) => `- ${count.toLocaleString()} ${label}`);
      return (error.message || "Linking another video deletes the evidence collected for the current one.") +
        (counts.length ? "\n\nEvidence that would be deleted:\n" + counts.join("\n") : "") +
        "\n\nReplace the link and delete this evidence? Cancel keeps the current link.";
    }

    async function linkVideoPrompt(runId) {
      if (!Number.isInteger(Number(runId)) || Number(runId) <= 0) {
        alert("This history row is missing its database ID. Reload the page and try again.");
        return;
      }
      const videoId = prompt("Enter your published YouTube Video ID or URL for this package:");
      if (!videoId) return;
      const linkVideo = (replaceExistingEvidence) => apiRequest(`/api/history/runs/${runId}/link-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(replaceExistingEvidence ? { youtube_video_id: videoId, replace_existing_evidence: true } : { youtube_video_id: videoId })
      });
      try {
        let result;
        try {
          result = await linkVideo(false);
        } catch (err) {
          if (err.status !== 409 || err.code !== "relink_would_delete_evidence") throw err;
          if (!confirm(relinkConfirmationText(err))) {
            showToast("Link unchanged. The collected evidence was kept.");
            return;
          }
          result = await linkVideo(true);
        }
        // The link is saved even when the follow-up analytics refresh fails; say so.
        const warning = typeof result.refresh_warning === "string" ? result.refresh_warning.trim() : "";
        showToast((result.ownership_message || "Package linked to YouTube Video ID.") + (warning ? " " + warning : ""));
        invalidateHistorySummary();
        loadHistoryFeed(true);
        loadSavedHistory();
      } catch (err) {
        showToast(formatApiError(err, "Could not link video."));
      }
    }

    async function loadPublishedVideos(force = false) {
      const body = $("publishedVideoBody");
     if (!body) return;
     try {
       const [pubData, histData] = await Promise.all([
          apiRequest("/api/published-videos", { cache: "no-store" }),
          getHistorySummary(force)
        ]);
        const links = (pubData.links || []).slice().sort((left, right) =>
          String(right.published_at || "").localeCompare(String(left.published_at || "")) || Number(right.id || 0) - Number(left.id || 0)
        );
        const uploadedVideos = (((histData.owned_performance || {}).videos) || []).slice().sort((left, right) =>
          String(right.published_at || "").localeCompare(String(left.published_at || "")) || String(left.video_id || "").localeCompare(String(right.video_id || ""))
        );
        const linksByVideo = new Map(links.map((link) => [String(link.youtube_video_id || ""), link]));

        if (!links.length && !uploadedVideos.length) {
          body.innerHTML = `<tr><td colspan="5" style="color:var(--text-sub);text-align:center;padding:16px">No linked or uploaded videos found yet. Connect YouTube in Settings to sync your channel videos.</td></tr>`;
          return;
        }

        const countLabel = (value, label) => value === null || value === undefined || value === "" ? label + " unavailable" : num(value) + " " + label;
        let html = "";
        if (uploadedVideos.length > 0) {
          html += uploadedVideos.map((v) => {
            const title = v.title || v.video_id || "YouTube Upload";
            const retention = v.average_view_percentage === null || v.average_view_percentage === undefined ? "Not collected" : num(v.average_view_percentage) + "% retention";
            const pubAt = v.published_at ? new Date(v.published_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" }) : "Unknown date";
            const vidId = String(v.video_id || "");
            const linked = linksByVideo.get(vidId);
            if (linked) linksByVideo.delete(vidId);
            const ytLink = vidId ? "https://www.youtube.com/watch?v=" + encodeURIComponent(vidId) : "#";
            const refreshAction = linked ? `<button class="btn" style="padding:4px 8px;font-size:11px" data-action="refresh-linked-video" data-link-id="${Number(linked.id)}">Refresh snapshot</button>` : "";
            return `<tr><td style="font-weight:600"><span class="chip chip-ok" style="font-size:10px;margin-right:6px">Channel Upload</span> ${esc(title)}<div class="metric-sub" style="font-size:11px">ID: ${esc(vidId)}</div></td>` +
              `<td>${pubAt}</td><td><strong style="color:var(--accent);font-size:15px">${countText(v.views)}</strong></td><td>${countLabel(v.likes, "likes")} / ${countLabel(v.comments, "comments")}<div class="metric-sub" style="font-size:11px">${retention}</div></td>` +
              `<td style="display:flex;gap:6px;flex-wrap:wrap"><a href="${esc(ytLink)}" target="_blank" rel="noopener" class="btn" style="padding:4px 8px;font-size:11px">Watch</a>${refreshAction}</td></tr>`;
          }).join("");
        }

        const unmatchedLinks = Array.from(linksByVideo.values());
        if (unmatchedLinks.length) {
          html += unmatchedLinks.map((link) => {
            const metric = link.latest_performance || {};
            const title = link.selected_title || link.package_topic || link.youtube_video_id;
            const views = metric.views === null || metric.views === undefined ? "Not collected" : num(metric.views);
            const retention = metric.avg_view_percentage === null || metric.avg_view_percentage === undefined ? "Not collected" : num(metric.avg_view_percentage) + "%";
            const published = link.published_at ? new Date(link.published_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" }) : "Unknown date";
            return `<tr><td style="font-weight:600"><span class="chip chip-accent" style="font-size:10px;margin-right:6px">Linked Package</span> ${esc(title)}<div class="metric-sub" style="font-size:11px">ID: ${esc(link.youtube_video_id)}</div></td>` +
              `<td>${published} / ${esc(metric.snapshot_window || "No snapshot")}</td><td><strong>${views}</strong></td><td>${retention} retention</td>` +
              `<td><button class="btn" style="padding:4px 8px;font-size:11px" data-action="refresh-linked-video" data-link-id="${Number(link.id)}">Refresh snapshot</button></td></tr>`;
          }).join("");
        }

        body.innerHTML = html;
      } catch (error) {
        body.innerHTML = `<tr><td colspan="5" style="color:var(--bad);text-align:center;padding:16px">${esc(formatApiError(error, "Could not load channel video performance."))}</td></tr>`;
      }
    }

    async function refreshLinkedVideo(linkId, button) {
      button.disabled = true;
      try {
        const data = await apiRequest("/api/published-videos/" + linkId + "/refresh", { method: "POST" });
        showToast(data.message || ((data.captured || []).length ? "Snapshot saved." : "No snapshot due yet."));
        invalidateHistorySummary();
        loadPublishedVideos(true);
        loadCohortLearning();
      } catch (error) {
        showToast(formatApiError(error, "Could not refresh this video."));
      } finally { button.disabled = false; }
    }

    // The dashboard evidence card, from the same live cohort the Analytics page uses.
    function renderDashboardLearning(data) {
      const set = (id, text) => { const node = $(id); if (node) node.textContent = text; };
      if (!data) {
        ["dashLearningStatus", "dashLearningSample", "dashLearningConfidence"].forEach((id) => set(id, "Unavailable"));
        return;
      }
      const sample = typeof data.sample_size === "number" ? data.sample_size : 0;
      const threshold = typeof data.next_threshold === "number" ? data.next_threshold : null;
      set("dashLearningStatus", data.learning_allowed ? "Enough mature evidence" : "Not enough mature evidence");
      set("dashLearningSample", threshold === null ? sample.toLocaleString() : `${sample.toLocaleString()} of ${threshold.toLocaleString()} for the next level`);
      set("dashLearningConfidence", data.confidence_label || "Unavailable");
    }

    async function loadCohortLearning() {
      try {
        const data = await apiRequest("/api/learning/cohorts");
        if ($("anaWinningAngle")) $("anaWinningAngle").textContent = data.confidence_label || "Collecting evidence";
        if ($("anaObservation")) {
          $("anaObservation").textContent = data.recommendation || "Link and refresh published videos to build evidence.";
          $("anaObservation").style.color = "";
        }
        // The only writer of this line: the live cohort, not the recommendation saved with the last sync.
        if ($("anaRecommendation")) $("anaRecommendation").textContent = data.sample_size ? ("Cohort: " + data.sample_size + " linked videos. " + (data.recommendation || "")) : "Learning begins after linked videos receive real snapshots.";
        renderDashboardLearning(data);
      } catch (error) {
        if ($("anaWinningAngle")) $("anaWinningAngle").textContent = "Unavailable";
        if ($("anaObservation")) renderApiError($("anaObservation"), error, "Learning evidence is unavailable.");
        renderDashboardLearning(null);
      }
    }

    async function refreshYouTubeAnalytics(button = null, silent = false) {
      if (frontendState.analyticsRefreshRequest) return frontendState.analyticsRefreshRequest;
      const buttons = [button, $("anaRefreshBtn"), $("settRefreshBtn")].filter(Boolean);
      buttons.forEach((item) => { item.disabled = true; });
      if ($("anaSyncStatus")) $("anaSyncStatus").textContent = "Refreshing current counts from YouTube...";
      frontendState.analyticsRefreshRequest = (async () => {
        const data = await apiRequest("/youtube/channel/refresh", { method: "POST" });
        invalidateHistorySummary();
        await Promise.all([
          loadHistoryFeed(true),
          loadPublishedVideos(true),
          loadCohortLearning(),
          loadChannelStatus(true),
        ]);
        const gaps = syncGapText((data || {}).partial_failures);
        if (!silent) showToast(gaps ? "YouTube refresh finished. " + gaps + "." : "YouTube analytics and video counts updated.");
        return data;
      })().catch((error) => {
        if ($("anaSyncStatus")) renderApiError($("anaSyncStatus"), error, "YouTube refresh failed.");
        if (!silent) showToast(formatApiError(error, "YouTube refresh failed."));
        return null;
      }).finally(() => {
        buttons.forEach((item) => { item.disabled = false; });
        frontendState.analyticsRefreshRequest = null;
      });
      return frontendState.analyticsRefreshRequest;
    }

    async function loadAnalyticsPage(force = false) {
      await Promise.all([
        loadHistoryFeed(force),
        loadPublishedVideos(force),
        loadCohortLearning(),
       loadChannelStatus(force),
     ]);
     const syncTime = frontendState.latestChannelStatus?.latest_sync?.synced_at;
      const stale = !syncTime || (Date.now() - new Date(syncTime).getTime() > 2 * 60 * 1000);
      if (!frontendState.analyticsAutoRefreshAttempted && frontendState.latestChannelStatus?.connected && stale) {
        frontendState.analyticsAutoRefreshAttempted = true;
        refreshYouTubeAnalytics($("anaRefreshBtn"), true);
      }
    }

    function historyDate(value) {
      if (!value) return "Unknown";
      return new Date(value).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      }) + " IST";
    }

    // The list endpoint returns at most 100 packages per request, so the History page pages through them.
    // Pages share the route's 60-requests-a-minute budget; past 2,000 packages the page says "N of total loaded".
    const HISTORY_PAGE_SIZE = 100;
    const HISTORY_MAX_PAGES = 20;
    let savedHistoryRuns = [];
    let savedHistoryTotal = null;
    let savedHistoryComplete = true;
    // Set when a later page failed; the pages loaded before it stay listed.
    let savedHistoryLoadError = null;
    let savedHistoryRequest = 0;
    const selectedHistoryRunIds = new Set();

    function visibleHistoryRuns(query = $("historySearch") ? $("historySearch").value : "") {
      const needle = String(query || "").trim().toLowerCase();
      return needle ? savedHistoryRuns.filter((run) =>
        [run.title, run.query, run.content_angle, run.intent].some((value) => String(value || "").toLowerCase().includes(needle))
      ) : savedHistoryRuns;
    }

    function historyRowHtml(run) {
      const runId = Number(run.id);
      const title = run.title || run.query || "Untitled package";
      const isLinked = Boolean(run.linked_youtube_video_id);
      const selection = run.selected_package_id
        ? `<span class="chip chip-ok">Selected package</span>`
        : `<span class="chip">Selection unknown</span>`;
      const selected = selectedHistoryRunIds.has(runId);
      return `<article class="history-row${selected ? " is-selected" : ""}" data-history-run="${runId}">` +
        `<label class="history-row-select" title="Select package"><span class="sr-only">Select ${esc(title)}</span><input type="checkbox" ${selected ? "checked" : ""} data-action="select-run" data-run-id="${runId}"></label>` +
        `<div class="history-row-main"><div class="history-row-title" title="${esc(title)}"><button data-action="open-run" data-run-id="${runId}">${esc(title)}</button></div>` +
          `<div class="history-row-meta"><span>${historyDate(run.created_at)}</span><span aria-hidden="true">·</span><span>${esc(run.content_angle || run.intent || "General")}</span>${selection}${isLinked ? `<span class="chip chip-ok">YouTube linked</span>` : ""}</div></div>` +
        `<div class="history-score-group" aria-label="Package scores"><div class="history-score"><span class="history-score-label">Opportunity</span><span class="history-score-value">${num(run.opportunity_score)}/100</span></div><div class="history-score"><span class="history-score-label">Title quality</span><span class="history-score-value">${num(run.title_score)}/10</span></div></div>` +
        `<div class="history-row-actions"><button class="btn btn-primary history-action-btn" data-action="open-run" data-run-id="${runId}">View package</button><button class="btn history-action-btn" data-action="link-video" data-run-id="${runId}">${isLinked ? "Change link" : "Link video"}</button><button class="btn history-action-btn history-action-danger" data-action="delete-run" data-run-id="${runId}">Delete</button></div>` +
      `</article>`;
    }

    function renderSavedHistory(query = "") {
      const body = $("historyPageBody");
      if (!body) return;
      const needle = String(query || "").trim().toLowerCase();
      const visibleRuns = visibleHistoryRuns(query);
      const loaded = savedHistoryRuns.length;
      // The count is the server's total; without one it is everything paging reached.
      const total = savedHistoryTotal === null ? loaded : Math.max(savedHistoryTotal, loaded);
      const more = savedHistoryTotal === null && !savedHistoryComplete ? "+" : "";
      const count = $("historyRunCount");
      const summary = $("historyResultSummary");
      if (count) count.textContent = total + more + " saved " + (total === 1 && !more ? "package" : "packages");
      if (summary) summary.textContent = needle
        ? visibleRuns.length + " of " + loaded + " packages match “" + String(query) + "”"
        : loaded < total || more
          ? loaded + " of " + total + more + " packages loaded"
          : loaded + " package" + (loaded === 1 ? "" : "s") + " available";
      if (summary && savedHistoryLoadError) {
        summary.textContent += ". The list is incomplete; the rest could not be loaded: " + formatApiError(savedHistoryLoadError, "Request failed.");
      }
      if (!visibleRuns.length) {
        body.innerHTML = `<div class="history-empty">${savedHistoryRuns.length ? "No saved packages match your search." : "No saved packages yet. Generate an SEO package and it will appear here."}</div>`;
        updateHistorySelectionControls(visibleRuns);
        return;
      }
      body.innerHTML = visibleRuns.map(historyRowHtml).join("");
      updateHistorySelectionControls(visibleRuns);
    }

    function updateHistorySelectionControls(visibleRuns = null) {
      const existing = new Set(savedHistoryRuns.map((run) => Number(run.id)));
      [...selectedHistoryRunIds].forEach((id) => { if (!existing.has(id)) selectedHistoryRunIds.delete(id); });
      const visible = visibleRuns || savedHistoryRuns;
      const selectedVisible = visible.filter((run) => selectedHistoryRunIds.has(Number(run.id))).length;
      if ($("historySelectedCount")) $("historySelectedCount").textContent = selectedHistoryRunIds.size + " selected";
      if ($("historyBulkDeleteBtn")) $("historyBulkDeleteBtn").disabled = selectedHistoryRunIds.size === 0;
      if ($("historySelectAll")) {
        $("historySelectAll").checked = visible.length > 0 && selectedVisible === visible.length;
        $("historySelectAll").indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
      }
    }

    // One checkbox changes one row and the toolbar; re-rendering every loaded row
    // (up to 2,000) would be slow and would take focus off the checkbox.
    function toggleHistoryRunSelection(runId, checked) {
      const id = Number(runId);
      if (checked) selectedHistoryRunIds.add(id); else selectedHistoryRunIds.delete(id);
      const row = $("historyPageBody") ? $("historyPageBody").querySelector(`[data-history-run="${id}"]`) : null;
      if (row) row.classList.toggle("is-selected", Boolean(checked));
      updateHistorySelectionControls(visibleHistoryRuns());
    }

    function toggleAllVisibleHistory(checked) {
      visibleHistoryRuns().forEach((run) => checked ? selectedHistoryRunIds.add(Number(run.id)) : selectedHistoryRunIds.delete(Number(run.id)));
      renderSavedHistory($("historySearch") ? $("historySearch").value : "");
    }

    function filterHistoryRuns(query = "") {
      renderSavedHistory(query);
    }

    async function fetchAllHistoryRuns() {
      const runs = [];
      const seen = new Set();
      let total = null;
      let complete = false;
      let error = null;
      let offset = 0;
      for (let page = 0; page < HISTORY_MAX_PAGES && !complete; page += 1) {
        let data;
        try {
          data = await apiRequest(`/api/history/runs?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`, { cache: "no-store" });
        } catch (err) {
          // A later page failing (say a rate limit) keeps the pages already loaded.
          if (page === 0) throw err;
          error = err;
          break;
        }
        const batch = arr(data.runs);
        if (typeof data.total === "number" && Number.isFinite(data.total)) total = data.total;
        const fresh = batch.filter((run) => !seen.has(String(run.id)));
        fresh.forEach((run) => { seen.add(String(run.id)); runs.push(run); });
        const pageSize = Math.min(HISTORY_PAGE_SIZE, Number(data.limit) || HISTORY_PAGE_SIZE);
        complete = batch.length < pageSize || (total !== null && runs.length >= total);
        // A full page with nothing new means the offset was ignored; stop instead of looping.
        if (!complete && !fresh.length) break;
        offset += batch.length;
      }
      return { runs, total, complete, error };
    }

    async function loadSavedHistory() {
      const body = $("historyPageBody");
      if (!body) return;
      savedHistoryRequest += 1;
      const request = savedHistoryRequest;
      try {
        const result = await fetchAllHistoryRuns();
        if (request !== savedHistoryRequest) return;
        savedHistoryRuns = result.runs;
        savedHistoryTotal = result.total;
        savedHistoryComplete = result.complete;
        savedHistoryLoadError = result.error;
        renderSavedHistory($("historySearch") ? $("historySearch").value : "");
      } catch (error) {
        if (request !== savedHistoryRequest) return;
        savedHistoryRuns = [];
        savedHistoryTotal = null;
        savedHistoryComplete = true;
        savedHistoryLoadError = null;
        if ($("historyRunCount")) $("historyRunCount").textContent = "Records unavailable";
        if ($("historyResultSummary")) $("historyResultSummary").textContent = "Could not load saved packages.";
        body.innerHTML = `<div class="history-empty" style="color:var(--bad)">${esc(formatApiError(error, "Could not load saved packages."))}</div>`;
      }
    }

    async function openHistoryRun(runId) {
      const panel = $("historyDetail");
      if (!panel) return;
      panel.classList.remove("hidden");
      panel.innerHTML = `<div class="metric-sub">Loading saved package...</div>`;
      try {
        const run = await apiRequest("/api/history/runs/" + runId);
        const id = Number(run.id);
        const packageData = run.package || {};
        const fullScript = packageData.creator_brief && packageData.creator_brief.content
          ? packageData.creator_brief.content
          : run.query;
        // A saved empty list means nothing was generated; only a list the record lacks is "not stored".
        const emptyListText = (value) => Array.isArray(value) ? "None generated." : "Not stored in this older record.";
        const tags = arr(packageData.tags).map((tag) => `<span class="tag-item">${esc(tag)}</span>`).join("") || `<span class="metric-sub">${emptyListText(packageData.tags)}</span>`;
        const hashtags = arr(packageData.hashtags).map((tag) => `<span class="tag-item">${esc(tag)}</span>`).join("") || `<span class="metric-sub">${emptyListText(packageData.hashtags)}</span>`;
        const variants = arr(packageData.title_variants).map((item) => `<li>${esc(typeof item === "string" ? item : item.title || "")}</li>`).join("") || `<li>${emptyListText(packageData.title_variants)}</li>`;
        const chapters = arr(packageData.chapters).map((item) => `<li>${esc((item.timestamp || "") + " " + (item.title || item))}</li>`).join("") || `<li>${emptyListText(packageData.chapters)}</li>`;
        const report = run.linked_video_report || {};
        const selection = run.selected_package || null;
        const selectedData = selection && selection.package ? selection.package : null;
        const selectionHtml = selectedData
          ? `<div class="history-link-callout"><div><strong>Creator-selected package</strong><div class="metric-sub">${esc(selectedData.title || "Selected package")} · selected ${historyDate(selection.selected_at)}</div></div><span class="chip chip-ok">Explicitly recorded</span></div>`
          : `<div class="history-link-callout"><div><strong>Creator-selected package</strong><div class="metric-sub">No explicit selection was recorded. The tool will not infer one after publishing.</div></div><span class="chip">Unknown</span></div>`;
        const retention = packageData.retention_assistant || {};
        const retentionRisks = arr(retention.risk_map).flatMap((stage) => arr((stage || {}).risks));
        const retentionHtml = Object.keys(retention).length
          ? `<div class="history-link-callout"><div><strong>Retention guidance: ${esc(retention.risk_level || "unknown")} risk</strong><div class="metric-sub">${esc((retention.trace || {}).timing_basis || "relative stage")} · ${retentionRisks.length} deterministic finding(s). This is pre-publish guidance, not measured retention.</div></div><span class="chip">${esc(retention.rule_version || "Local rules")}</span></div>`
          : "";
        const linkedHtml = report.linked ? linkedVideoReportHtml(report, run.id) :
          `<div class="history-link-callout"><div><strong>Published-video learning</strong><div class="metric-sub">No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package.</div></div><button class="btn" data-action="link-video" data-run-id="${id}">Link video</button></div>`;
        const legacy = !run.package
          ? `<div class="alert-banner" style="background:var(--warn-bg);border:1px solid rgba(245,158,11,.3);color:#fcd34d;margin-top:16px">This package was created before full-package history was added. Its saved title, script, and scores are shown below; future packages retain the complete generated output.</div>`
          : "";
        const linkState = report.linked ? "Linked to YouTube" : "Not linked";
        panel.innerHTML =
          `<div class="history-detail-header"><div><div class="eyebrow">SAVED PACKAGE · ${historyDate(run.created_at)}</div><h2 class="history-detail-title">${esc(packageData.title || run.title || "Untitled package")}</h2><div class="history-detail-meta"><span>${esc(run.content_angle || run.intent || "General")}</span><span aria-hidden="true">·</span><span>${esc(run.opportunity_label || "Saved generation")}</span></div></div><div class="history-detail-actions"><button class="btn history-action-danger" data-action="delete-run" data-run-id="${id}">Delete package</button><button class="btn" data-action="close-run">Close</button></div></div>` +
          `<div class="history-detail-body"><div class="history-summary-grid"><div class="history-summary-stat"><span>Opportunity</span><strong>${num(run.opportunity_score)} / 100</strong></div><div class="history-summary-stat"><span>Title quality</span><strong>${num(run.title_score)} / 10</strong></div><div class="history-summary-stat"><span>Package selection</span><strong>${selectedData ? "Recorded" : "Unknown"}</strong></div><div class="history-summary-stat"><span>Publishing status</span><strong>${linkState}</strong></div></div>` +
          legacy + selectionHtml + retentionHtml + linkedHtml +
          `<div class="history-detail-grid"><section class="history-section"><div class="history-section-heading">Description</div><div class="history-longform">${esc(packageData.description || "Not stored in this older record.")}</div></section>` +
          `<section class="history-section"><div class="history-section-heading">Original video content / script</div><div class="history-longform">${esc(fullScript || "Not stored.")}</div></section>` +
          `<section class="history-section"><div class="history-section-heading">Tags &amp; hashtags</div><div class="tag-list">${tags}</div><div class="history-section-heading" style="margin-top:18px">Hashtags</div><div class="tag-list">${hashtags}</div></section>` +
          `<section class="history-section"><details open><summary>Title variations</summary><div><ol class="history-detail-list">${variants}</ol></div></details><details><summary>Chapters</summary><div><ol class="history-detail-list">${chapters}</ol></div></details></section></div></div>`;
        const syncedAt = report.metadata_synced_at || (report.performance || {}).captured_at;
        const stale = !syncedAt || Date.now() - new Date(syncedAt).getTime() > 10 * 60 * 1000;
        if (report.linked && stale && !historyPerformanceAutoRefresh.has(Number(report.link_id))) {
          historyPerformanceAutoRefresh.add(Number(report.link_id));
          refreshHistoryPerformance(Number(report.link_id), id, null, true);
        }
      } catch (error) {
        panel.innerHTML = `<div class="alert-banner alert-err">${esc(formatApiError(error, "Could not open this saved package."))}</div>`;
      }
    }

    const historyPerformanceAutoRefresh = new Set();

    function linkedVideoReportHtml(report, runId) {
      const yt = report.youtube || {};
      const usage = report.package_usage || {};
      const perf = report.performance || {};
      const diagnosis = report.diagnosis || {};
      const ownershipVerified = report.ownership_verified === true;
      const baseline = report.baseline || {};
      const linkId = Number(report.link_id);
      const watchUrl = /^https:\/\//i.test(String(report.video_url || "")) ? report.video_url : "#";
      const metric = (value, suffix = "") => value === null || value === undefined ? "Not available yet" : num(value) + suffix;
      const list = (items, empty) => arr(items).length
        ? `<ul style="padding-left:20px;line-height:1.65;margin:8px 0">${arr(items).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`
        : `<div class="metric-sub">${esc(empty)}</div>`;
      const tagList = (items, empty) => arr(items).length
        ? `<div class="tag-list">${arr(items).map((item) => `<span class="tag-item">${esc(item)}</span>`).join("")}</div>`
        : `<div class="metric-sub">${esc(empty)}</div>`;
      const titleStatus = usage.title_match ? "Exact generated title used" : "Uploaded title differs from generated title";
      const attribution = usage.attribution_status === "creator_selected" ? "Creator-selected package" : "Package selection unknown";
      const comparable = report.comparable_metadata || {};
      const retentionLearning = report.retention_learning || {};
      const learningCount = num(retentionLearning.sample_size || 0);
      const learningMinimum = num(retentionLearning.minimum_samples || 5);
      const learningPercent = Math.min(100, Math.round((Number(retentionLearning.sample_size || 0) / Math.max(1, Number(retentionLearning.minimum_samples || 5))) * 100)) || 0;
      const retentionLearningHtml = `<section class="history-learning-panel"><div class="history-panel-heading"><div><div class="eyebrow">CHANNEL LEARNING</div><h3>Retention evidence</h3></div><span class="chip">${esc(retentionLearning.status || "insufficient_evidence").replaceAll("_", " ")}</span></div>` +
        `<div class="history-learning-progress"><div><strong>${learningCount} of ${learningMinimum} comparable videos</strong><span>with verified 24-hour retention data</span></div><div class="history-progress-track" aria-label="${learningCount} of ${learningMinimum} comparable videos"><span style="width:${learningPercent}%"></span></div></div>` +
        `<p class="metric-sub">${esc(retentionLearning.message || "No eligible retention pattern is available.")} The tool surfaces patterns only after enough like-for-like videos exist; it does not claim that a package caused views or retention.</p></section>`;
      const sources = comparable.sources || {};
      const sourceLabel = (source) => ({creator:"Creator confirmed", youtube_verified:"YouTube verified", package:"From package", unknown:"Unknown"}[source] || "Unknown");
      const metadataEditor = `<section class="history-comparable-panel"><div class="history-panel-heading"><div><div class="eyebrow">COMPARISON SETUP</div><h3>Comparable learning metadata</h3></div><span class="chip">Local only</span></div><p class="metric-sub">These labels group similar videos for future learning. Saving them does not edit the YouTube video.</p><div class="history-metadata-grid">` +
        ["language","format","duration_bucket","topic_category"].map((field) => `<label class="history-metadata-field"><span>${esc(field.replaceAll("_", " "))} <small class="chip">${esc(sourceLabel(sources[field]))}</small></span><input id="comparable-${field}" value="${esc(comparable[field] === "unknown" ? "" : comparable[field] || "")}" maxlength="80" placeholder="Not set"></label>`).join("") +
        `</div><div class="history-form-actions"><button class="btn btn-primary" data-action="save-comparable-metadata" data-link-id="${linkId}" data-run-id="${Number(runId)}">Save local labels</button><button class="btn" data-action="open-run" data-run-id="${Number(runId)}">Discard changes</button></div><div id="comparable-meta-error" class="metric-sub" style="color:var(--bad);margin-top:8px"></div></section>`;
      const snapshots = arr(report.snapshots);
      const snapshotRows = snapshots.map((snapshot) => {
        const complete = snapshot.avg_view_percentage !== null && snapshot.avg_view_percentage !== undefined;
        const windowLabel = snapshot.snapshot_window || "current";
        const state = complete ? "Retention available" : windowLabel === "current" ? "Live counts" : "Retention pending";
        return `<div class="history-snapshot-row"><div><strong>${esc(windowLabel)}</strong><span class="chip ${complete ? "chip-ok" : ""}">${state}</span></div><div><span>Views</span><strong>${metric(snapshot.views)}</strong></div><div><span>Likes</span><strong>${metric(snapshot.likes)}</strong></div><div><span>Average viewed</span><strong>${metric(snapshot.avg_view_percentage, "%")}</strong></div><div><span>Captured</span><strong>${historyDate(snapshot.captured_at)}</strong></div></div>`;
      }).join("") || `<div class="history-empty">No performance snapshot has been captured yet.</div>`;
      return `<section class="history-linked-report">` +
       `<header class="history-linked-header"><div><div class="eyebrow">LINKED YOUTUBE VIDEO</div><h3>${esc(diagnosis.verdict || "Collecting evidence")}</h3><p>Published ${historyDate(report.published_at)} · Last refreshed ${historyDate(report.metadata_synced_at || perf.captured_at)}</p></div><div class="history-detail-actions"><span class="chip ${ownershipVerified ? "chip-ok" : ""}">${ownershipVerified ? "Owner analytics verified" : "Public data only"}</span><a class="btn" target="_blank" rel="noopener" href="${esc(watchUrl)}">Watch video</a><button class="btn" data-action="refresh-history-performance" data-link-id="${linkId}" data-run-id="${Number(runId)}">Refresh data</button></div></header>` +
        `<div class="history-linked-grid"><section class="history-section"><div class="history-section-heading">Actual YouTube upload</div>` +
          (yt.thumbnail_url ? `<img class="history-youtube-thumb" src="${esc(yt.thumbnail_url)}" alt="">` : "") +
          `<div class="history-upload-title">${esc(yt.title || usage.uploaded_title || "Metadata not refreshed yet")}</div><div class="history-detail-meta"><span>${esc(attribution)}</span><span>·</span><span>${esc(titleStatus)}</span><span>·</span><span>Description match ${metric(usage.description_match_percent, "%")}</span></div>` +
          `<details><summary>Description currently on YouTube</summary><div class="history-longform">${esc(yt.description || "No description returned.")}</div></details><details><summary>Tags &amp; hashtags found on YouTube</summary><div><div class="history-mini-label">Uploaded tags</div>${tagList(usage.uploaded_tags, "No uploaded tags were returned by YouTube.")}<div class="history-mini-label">Generated tags used</div>${tagList(usage.matching_tags, "None of the generated tags currently match the uploaded tags.")}<div class="history-mini-label">Hashtags in description</div>${tagList(usage.uploaded_hashtags, "No hashtags were detected in the uploaded description.")}</div></details></section>` +
          `<section class="history-section"><div class="history-section-heading">Current observed performance <span class="chip">Video-level data</span></div><div class="history-performance-grid">` +
            `<div><span>Views</span><strong>${metric(perf.views)}</strong></div><div><span>Likes</span><strong>${metric(perf.likes)}</strong></div><div><span>Comments</span><strong>${metric(perf.comments)}</strong></div><div><span>Average viewed</span><strong>${metric(perf.average_view_percentage, "%")}</strong></div><div><span>Avg. view duration</span><strong>${metric(perf.average_view_duration_seconds, " sec")}</strong></div><div><span>Subscribers gained</span><strong>${metric(perf.subscribers_gained)}</strong></div></div>` +
            `<p class="metric-sub">Public counts can update before retention analytics. Comparable baseline: ${num(baseline.sample_size || 0)} other videos at ${esc(baseline.window || "no scheduled window")}.</p></section>` +
          `<section class="history-section"><div class="history-section-heading">What the evidence supports</div>${list(diagnosis.what_worked, "No positive conclusion is supported yet.")}</section><section class="history-section"><div class="history-section-heading">What remains unknown</div>${list(diagnosis.needs_improvement, "No issue has been detected from the available evidence.")}</section></div>` +
          retentionLearningHtml + metadataEditor +
          `<section class="history-snapshots-panel"><div class="history-panel-heading"><div><div class="eyebrow">OBSERVATION HISTORY</div><h3>Performance snapshots</h3></div><span class="metric-sub">Video ID ${esc(report.video_id)}</span></div><div class="history-snapshot-list">${snapshotRows}</div><p class="metric-sub">${esc(diagnosis.attribution_note || "YouTube reports video-level performance; it cannot attribute views to individual tags.")}</p></section>` +
        `</section>`;
    }

    async function saveComparableMetadata(linkId, runId) {
      const fields = ["language", "format", "duration_bucket", "topic_category"];
      const payload = {};
      fields.forEach((field) => { const node = $("comparable-" + field); if (node) payload[field] = node.value.trim() || null; });
      const errorNode = $("comparable-meta-error");
      if (errorNode) errorNode.textContent = "Saving...";
      try {
        await apiRequest("/api/published-videos/" + Number(linkId) + "/comparable-metadata", { method: "PATCH", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) });
        await openHistoryRun(Number(runId));
        loadCohortLearning();
      } catch (error) {
        if (errorNode) errorNode.textContent = formatApiError(error, "Metadata could not be saved.");
      }
    }

    async function refreshHistoryPerformance(linkId, runId, button, silent = false) {
      if (!Number.isInteger(Number(linkId)) || Number(linkId) <= 0) return;
      const original = button ? button.textContent : "";
      if (button) { button.disabled = true; button.textContent = "Refreshing..."; }
      try {
        const result = await apiRequest("/api/published-videos/" + Number(linkId) + "/refresh", { method: "POST" });
        if (!silent) showToast(result.message || "YouTube metadata and available analytics refreshed.");
        invalidateHistorySummary();
        await openHistoryRun(Number(runId));
        loadHistoryFeed(true);
        loadPublishedVideos(true);
        loadCohortLearning();
      } catch (error) {
        if (!silent) showToast(formatApiError(error, "YouTube refresh failed."));
      } finally {
        if (button) { button.disabled = false; button.textContent = original; }
      }
    }

    function closeHistoryDetail() {
      const panel = $("historyDetail");
      if (panel) panel.classList.add("hidden");
    }

    $("runDiagBtn").addEventListener("click", async () => {
      const out = $("settDiagOut");
      const button = $("runDiagBtn");
      button.disabled = true;
      out.style.color = "";
      out.textContent = "Running one live YouTube Data API check (1 quota unit)...";
      try {
        // POST only, and only from this button: the probe spends YouTube quota.
        const data = await apiRequest("/diagnostics", { method: "POST" });
        const yt = data.youtube || {};
        const gemini = data.gemini || {};
        // Only an "ok" status is a request that succeeded; a missing key sends no request at all.
        const ytResult = yt.status === "ok"
          ? "Request succeeded: a configured key answered a 1-unit region-list check." + (yt.warning ? " " + yt.warning : "")
          : yt.status === "missing_api_key"
            ? "No YouTube Data API key is configured, so no request was made."
            : yt.error || yt.warning || "The YouTube check did not report a result.";
        out.innerHTML = `<div class="kv-list"><div class="kv-item"><span class="kv-key">YouTube live request</span><span class="kv-val"><span class="chip ${yt.status === "ok" ? "chip-ok" : ""}">${esc(yt.status || "unavailable")}</span></span></div><div class="kv-item"><span class="kv-key">YouTube result</span><span class="kv-val">${esc(ytResult)}</span></div><div class="kv-item"><span class="kv-key">Gemini configuration</span><span class="kv-val"><span class="chip ${gemini.configured ? "chip-ok" : ""}">${gemini.configured ? `Configured / ${esc(gemini.model)}` : "Not configured; fallback will be used"}</span></span></div></div>`;
      } catch (e) {
        renderApiError(out, e, "Diagnostics failed.");
      } finally {
        button.disabled = false;
      }
    });

    // A size the server could not read is unknown, never "0 B".
    function formatBytes(value) {
      const bytes = typeof value === "number" ? value : NaN;
      if (!Number.isFinite(bytes) || bytes < 0) return "Not available";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1048576).toFixed(1)} MB`;
    }

    async function loadSettingsStatus() {
      try {
        const data = await apiRequest("/api/settings/status", { cache: "no-store" });
        const app = data.app || {}, db = data.database || {}, providers = data.providers || {};
        const gemini = providers.gemini || {}, yt = providers.youtube_data_api || {}, counts = db.counts || {};
        const fallback = providers.local_fallback || {};
        // The database state is what the server reports; a missing flag is unknown, not healthy.
        const dbState = db.healthy === true ? "healthy" : db.healthy === false ? "error" : "unknown";
        const dbError = typeof db.last_error === "string" && db.last_error ? db.last_error : typeof db.error === "string" ? db.error : "";
        if ($("appVersionBadge")) $("appVersionBadge").textContent = `OS v${app.version || "unknown"}`;
        if ($("dashVersionChip")) $("dashVersionChip").textContent = app.version ? `Creator Intelligence OS v${app.version}` : "Creator Intelligence OS";
        if ($("dashGeminiStatus")) $("dashGeminiStatus").textContent = gemini.configured ? `Gemini ${gemini.model || "configured"}` : "Local fallback only";
        if ($("sidebarRuntimeStatus")) $("sidebarRuntimeStatus").innerHTML = `<span class="dot${dbState === "healthy" ? "" : dbState === "error" ? " dot-bad" : " dot-muted"}"></span> ${gemini.configured ? `Gemini ${esc(gemini.model)}` : "Local fallback"} / DB ${dbState}`;
        $("settGeminiProvider").innerHTML = `<span class="chip ${gemini.configured ? "chip-ok" : ""}">${gemini.configured ? `Configured / ${esc(gemini.model)}` : "Not configured"}</span>`;
        $("settFallbackProvider").innerHTML = fallback.available === true
          ? `<span class="chip chip-ok">Available / used when Gemini fails</span>`
          : `<span class="chip">${fallback.available === false ? "Unavailable" : "Unknown"}</span>`;
        $("settYouTubeKeys").innerHTML = `<span class="chip ${yt.configured ? "chip-ok" : ""}">${yt.configured ? `${num(yt.key_count)} configured` : "Not configured"}</span>`;
        $("settRedisStatus").innerHTML = `<span class="chip ${providers.redis?.configured ? "chip-ok" : ""}">${providers.redis?.configured ? "Configured" : "Not configured"}</span>`;
        const known = (value) => typeof value === "number" && Number.isFinite(value);
        const schemaText = known(db.schema_version) ? `schema v${num(db.schema_version)}` : "schema version not available";
        const sizeText = known(db.size_bytes) ? formatBytes(db.size_bytes) : "size not available";
        $("settDatabaseStatus").innerHTML = `<span class="chip ${dbState === "healthy" ? "chip-ok" : dbState === "error" ? "chip-bad" : ""}">${dbState === "healthy" ? "Healthy" : dbState === "error" ? "Error" : "Unknown"}</span>${dbError ? ` ${esc(dbError)} /` : ""} ${esc(db.name || "Unknown")} / ${schemaText} / ${sizeText}`;
        // Counts the server could not read (an unhealthy database) are not zero.
        const countLabels = [["packages", "packages"], ["ideas", "ideas"], ["published_links", "linked videos"], ["performance_snapshots", "performance snapshots"]];
        $("settDatabaseCounts").textContent = countLabels.some(([key]) => known(counts[key]))
          ? countLabels.map(([key, label]) => known(counts[key]) ? `${counts[key].toLocaleString()} ${label}` : `${label} not available`).join(" / ")
          : "Not available";
        $("settBackupStatus").textContent = db.last_backup_at ? historyDate(db.last_backup_at) : "No migration backup recorded";
      } catch (error) {
        ["settGeminiProvider","settFallbackProvider","settYouTubeKeys","settRedisStatus","settDatabaseStatus","settDatabaseCounts","settBackupStatus","dashGeminiStatus"].forEach(id => { if ($(id)) $(id).textContent = "Status unavailable"; });
        if ($("sidebarRuntimeStatus")) $("sidebarRuntimeStatus").innerHTML = `<span class="dot dot-muted"></span> Runtime status unavailable`;
        if ($("appVersionBadge")) $("appVersionBadge").textContent = "OS";
      }
    }

    async function loadChannelStatus(force = false) {
      try {
        const data = await apiRequest("/youtube/channel/status", { cache: force ? "reload" : "no-store" });
        frontendState.latestChannelStatus = data;
        frontendState.channelStatusFailed = false;
        renderChannelSummary();
        const settStatus = $("settChannelStatus");
        const connectBtn = $("settConnectBtn");
        const refreshBtn = $("settRefreshBtn");
        const disconnectBtn = $("settDisconnectBtn");
        settStatus.style.color = "";

        if (!data.configured) {
          settStatus.textContent = data.setup_message || "OAuth setup is required.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Set up OAuth";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return data;
        }
        if (!data.connected) {
          settStatus.textContent = "Ready to connect with read-only permissions.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Connect Channel";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return data;
        }
        const sync = latestSync();
        const channelTitle = (data.channel || {}).title || "YouTube Channel";
        const lastChannelSync = sync.synced_at ? historyDate(sync.synced_at) : "not refreshed yet";
        const gaps = syncGapText(sync.partial_failures);
        settStatus.textContent = `Connected to ${channelTitle}. ${channelStatsText(sync)}. Last analytics refresh: ${lastChannelSync}.${gaps ? " " + gaps + "." : ""}`;

        connectBtn.style.display = "none";
        refreshBtn.style.display = "inline-flex";
        disconnectBtn.style.display = "inline-flex";
        return data;
      } catch (error) {
        frontendState.channelStatusFailed = true;
        renderChannelSummary();
        const settStatus = $("settChannelStatus");
        if (settStatus) renderApiError(settStatus, error, "Could not load channel settings.");
        return null;
      }
    }
    async function loadCollectorStatus() {
      const statusNode = $("settCollectorStatus");
      const detailsNode = $("settCollectorDetails");
      if (!statusNode) return;
      try {
        const data = await apiRequest("/api/snapshot-collector/status", { cache: "no-store" });
        const state = String(data.state || "unknown");
       const knownStates = new Set(["disabled", "dry-run", "unconfigured", "waiting", "running", "healthy/idle", "cooldown", "error"]);
       statusNode.textContent = "Status: " + (knownStates.has(state) ? state : "Unavailable");
       if (detailsNode) {
          const counts = data.last_counts || {};
          detailsNode.textContent = data.dry_run
            ? `Dry-run: no YouTube/Gemini calls or database writes. Last check: ${data.last_finished_at ? historyDate(data.last_finished_at) : "not run"}; planned ${num(counts.links)} linked videos / ${num(counts.windows)} due windows. Next check: ${data.next_run_at ? historyDate(data.next_run_at) : "not scheduled"}.`
            : state === "disabled"
              ? "Automatic collection is disabled by configuration."
              : state === "unconfigured"
                ? "Collector is not configured; no collection has run."
                : state === "error"
                  ? "Collector error: " + String(data.last_error || "The collector reported an error.")
                  : "Last run: " + (data.last_finished_at ? historyDate(data.last_finished_at) : "Not run") + " / Planned links: " + num(counts.links) + " / Windows: " + num(counts.windows);
        }
      } catch (error) {
        statusNode.textContent = "Status unavailable";
        if (detailsNode) detailsNode.textContent = formatApiError(error, "Collector status unavailable.");
      }
    }
    async function loadCloudSyncStatus() {
      const statusNode = $("settCloudSyncStatus");
      const detailsNode = $("settCloudSyncDetails");
      if (!statusNode) return;
      try {
        const data = await apiRequest("/api/cloud-sync/status", { cache: "no-store" });
        statusNode.textContent = `Status: ${String(data.state || "unknown")} / Device: ${String(data.device_id || "unconfigured")}`;
        const counts = data.last_counts || {};
        detailsNode.textContent = data.enabled
          ? `Local ${num(data.local_packages)} / synced ${num(data.synced_packages)} / cloud ${num(data.remote_packages)} / pending ${num(data.pending_uploads)}. Last check: ${data.last_finished_at ? historyDate(data.last_finished_at) : "not run"}; uploaded ${num(counts.pushed)}, downloaded ${num(counts.pulled)}. Next: ${data.next_run_at ? historyDate(data.next_run_at) : "not scheduled"}${data.last_error ? ` / ${String(data.last_error)}` : ""}`
          : "Cloud synchronization is disabled. Packages remain safely stored in local SQLite.";
      } catch (error) {
        statusNode.textContent = "Cloud sync status unavailable";
        detailsNode.textContent = formatApiError(error, "Cloud sync status unavailable.");
      }
    }
    if ($("settCloudSyncBtn")) $("settCloudSyncBtn").onclick = async () => {
      const button = $("settCloudSyncBtn");
      button.disabled = true;
      try {
        const data = await apiRequest("/api/cloud-sync/run", { method: "POST" });
        showToast(`Sync ${String(data.state || "finished")}.`);
        await loadCloudSyncStatus();
        await loadSavedHistory();
        await loadSettingsStatus();
      } catch (error) {
        showToast(formatApiError(error, "Cloud sync failed; local packages are unchanged."));
      } finally { button.disabled = false; }
    };
    if ($("anaRefreshBtn")) $("anaRefreshBtn").onclick = () => refreshYouTubeAnalytics($("anaRefreshBtn"));
    // Wired once at startup, so the buttons work even when the status request failed;
    // loadChannelStatus only chooses which of them to show.
    if ($("settConnectBtn")) $("settConnectBtn").addEventListener("click", () => { window.location.href = "/youtube/channel/connect"; });
    if ($("settRefreshBtn")) $("settRefreshBtn").addEventListener("click", () => refreshYouTubeAnalytics($("settRefreshBtn")));
    if ($("settDisconnectBtn")) $("settDisconnectBtn").addEventListener("click", async () => {
      if (!confirm("Disconnect YouTube channel?")) return;
      try {
        await apiRequest("/youtube/channel/disconnect", { method: "POST" });
      } catch (error) {
        renderApiError($("settChannelStatus"), error, "Could not disconnect the channel.");
        return;
      }
      await loadChannelStatus();
    });
    // The Creator receives only explicit app-shell callbacks and owns all of its
    // rendering and behavior.
    mountCreatorPage(document, {
      notify: showToast,
      onAnalysisSaved: () => {
        invalidateHistorySummary();
        loadHistoryFeed(true);
      },
    });
    mountIdeasPage();
    mountDemandPage();
    mountWatchlistPage();
    mountAuditsPage();
    mountExperimentsPage();
    route();
    loadCollectorStatus();
    loadCloudSyncStatus();
    loadSettingsStatus();
    if ((window.location.hash || "#dashboard") !== "#analytics") loadChannelStatus();
