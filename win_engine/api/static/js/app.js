import { apiRequest } from "./api.js";
import { formatApiError, renderApiError } from "./errors.js";
import { $, arr, esc, num } from "./utils.js";
import { frontendState, invalidateHistorySummary } from "./state.js";
import { normalizePageKey, pages } from "./navigation.js";
import { mountDashboardPage } from "./pages/dashboard.js";
import { mountSettingsPage } from "./pages/settings.js";
import { mountAnalyticsPage } from "./pages/analytics.js";
import { mountHistoryPage } from "./pages/history.js";
import { mountCreatorPage } from "./pages/creator.js";
import { loadIdeasPage, mountIdeasPage } from "./pages/ideas.js";
import { loadDemand, mountDemandPage } from "./pages/demand.js";
import { loadWatchlist, mountWatchlistPage } from "./pages/watchlist.js";
import { loadAudits, mountAuditsPage } from "./pages/audits.js";
import { loadExperiments, mountExperimentsPage } from "./pages/experiments.js";

    async function getHistorySummary(force = false) {
      const cacheFresh = frontendState.historySummaryCache && (Date.now() - frontendState.historySummaryFetchedAt < 15000);
      if (!force && cacheFresh) return frontendState.historySummaryCache;
      if (frontendState.historySummaryRequest) return frontendState.historySummaryRequest;
      frontendState.historySummaryRequest = apiRequest("/api/history", { cache: "no-store" }).then((data) => {
        frontendState.historySummaryCache = data;
        frontendState.historySummaryFetchedAt = Date.now();
        return frontendState.historySummaryCache;
      }).finally(() => { frontendState.historySummaryRequest = null; });
      return frontendState.historySummaryRequest;
    }

    function invalidateDashboardCache() {
      invalidateHistorySummary();
    }

    // Toast notification display helper
    function showToast(msg) {
      const toast = $("toastNotification");
      if (!toast) return;
      toast.textContent = msg || "Copied to clipboard.";
      toast.classList.add("show");
      setTimeout(() => toast.classList.remove("show"), 2200);
    }

    // Dynamic Theme Engine
    function setTheme(themeKey) {
      const validThemes = ["obsidian", "pearl", "light", "cyber", "emerald"];
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

    // 1-Click Starter Templates
    const TEMPLATES = {
      tech: "How to build a full YouTube SEO automation app in Python and Tamil using Gemini AI and FastAPI.",
      quote: "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
      growth: "How I grew my YouTube channel from 0 to 10,000 subscribers in 30 days using stronger title and topic choices.",
      review: "Top 5 AI productivity tools in 2026 that will double your coding and video creation output."
    };

    function applyTemplate(key) {
      const text = TEMPLATES[key] || "";
      if ($("dashQuickScript")) $("dashQuickScript").value = text;
      if ($("scriptInput")) $("scriptInput").value = text;
      showToast("Sample idea loaded into input.");
    }

    function switchPage(key, updateHistory = true) {
      const pageKey = pages[key] ? key : "dashboard";
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

      if (pageKey === "dashboard") loadHistoryFeed();
      if (pageKey === "ideas") loadIdeasPage();
      if (pageKey === "demand") loadDemand();
      if (pageKey === "watchlist") loadWatchlist();
      if (pageKey === "audits") loadAudits();
      if (pageKey === "experiments") loadExperiments();
      if (pageKey === "analytics") loadAnalyticsPage();
      if (pageKey === "history") loadSavedHistory();
    }

    async function checkOAuthRedirect() {
      if (frontendState.oauthRedirectHandled) return;
      if (window.location.search.includes("youtube=connected")) {
        frontendState.oauthRedirectHandled = true;
        console.log("YouTube OAuth connected! Auto-syncing channel analytics...");
        try {
          await apiRequest("/youtube/channel/refresh", { method: "POST" });
        } catch (_) {}
        if (window.history.replaceState) {
          const cleanUrl = window.location.pathname + window.location.hash;
          window.history.replaceState({}, document.title, cleanUrl);
        }
        invalidateDashboardCache();
        loadAnalyticsPage(true);
      }
    }

    function route() {
      const hash = normalizePageKey(window.location.hash || "#dashboard");
      const now = Date.now();
      if (hash === frontendState.lastRoutedHash && now - frontendState.lastRoutedAt < 100) return;
      frontendState.lastRoutedHash = hash;
      frontendState.lastRoutedAt = now;
      switchPage(hash, false);
      checkOAuthRedirect();
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

    // Load Real Recent Runs from SQLite via API
    async function loadHistoryFeed(force = false) {
      try {
        const data = await getHistorySummary(force);
        const runs = (data.learning || {}).recent_runs || [];
        const scorecard = data.scorecard || {};
        const owned = data.owned_performance || {};

        const ch = owned.channel || {};
        const sync = owned.latest_sync || {};
        const syncPeriod = sync.period || {};
        const chTitle = ch.title || (sync.channel || {}).title || "";
        const isConnected = !!(ch.id || chTitle);

        // 1. 28d Views Milestone Card
        const totalViews = owned.total_views;
        if ($("dashMetricViews")) $("dashMetricViews").textContent = isConnected ? num(totalViews) : "Not available";
        if ($("dashMetricViewsSub")) {
          $("dashMetricViewsSub").textContent = isConnected ? "Real 28-day channel views synced from YouTube." : "Connect and refresh your channel in Settings.";
        }

        // 2. Estimated Watch Time Card
        const watchMins = owned.estimated_watch_minutes;
        let watchStr = "--";
        if (typeof watchMins === "number" && watchMins >= 60) {
          watchStr = (watchMins / 60).toFixed(1) + " hrs";
        } else if (typeof watchMins === "number" && watchMins > 0) {
          watchStr = watchMins + " mins";
        } else if (isConnected && watchMins === 0) {
          watchStr = "0 mins";
        }
        if ($("dashMetricWatch")) $("dashMetricWatch").textContent = watchStr;
        if ($("dashMetricWatchSub")) {
          $("dashMetricWatchSub").textContent = isConnected ? "Total estimated watch time from 28-day sync." : "Not available until YouTube Analytics sync succeeds.";
        }
        if ($("anaSubscribers")) $("anaSubscribers").textContent = owned.subscribers === null || owned.subscribers === undefined ? "--" : num(owned.subscribers);
        if ($("anaLifetimeViews")) $("anaLifetimeViews").textContent = owned.lifetime_views === null || owned.lifetime_views === undefined ? "--" : num(owned.lifetime_views);
        if ($("ana28dViews")) $("ana28dViews").textContent = isConnected ? num(owned.views_28_days) : "--";
        if ($("anaWatchTime")) $("anaWatchTime").textContent = watchStr;
        if ($("anaSyncStatus")) {
          const synced = sync.synced_at ? historyDate(sync.synced_at) : "Never";
          const period = syncPeriod.start && syncPeriod.end ? ` / Analytics period ${syncPeriod.start} to ${syncPeriod.end}` : "";
          $("anaSyncStatus").textContent = `Last synced: ${synced}${period}`;
        }

        // 3. Avg Opportunity Score Card
        if (scorecard.total_runs !== undefined) {
          const roundedOpp = scorecard.avg_opportunity_score === null || scorecard.avg_opportunity_score === undefined ? "Not available" : Math.round(scorecard.avg_opportunity_score);
          const roundedTitle = scorecard.avg_title_score === null || scorecard.avg_title_score === undefined ? "Not available" : (Math.round(scorecard.avg_title_score * 10) / 10);
          if ($("dashMetricOpp")) $("dashMetricOpp").textContent = roundedOpp + " / 100";
          if ($("dashMetricOppSub")) $("dashMetricOppSub").textContent = `Calculated from your ${num(scorecard.total_runs)} saved analyses.`;
          if ($("dashTotalRuns")) $("dashTotalRuns").textContent = num(scorecard.total_runs);
          if ($("anaTotalRuns")) $("anaTotalRuns").textContent = num(scorecard.total_runs);
         if ($("anaAvgTitle")) $("anaAvgTitle").textContent = roundedTitle + " / 10";
         if ($("anaAvgOpp")) $("anaAvgOpp").textContent = roundedOpp + " / 100";
       }

        // 4. Connected Channel Card
        if (isConnected) {
          const lifetimeViews = owned.lifetime_views === null || owned.lifetime_views === undefined ? "--" : num(owned.lifetime_views);
          const subscribers = owned.subscribers === null || owned.subscribers === undefined ? "--" : num(owned.subscribers);
          const linkedCount = owned.linked_videos_count || 0;
          if ($("dashChannelName")) $("dashChannelName").textContent = chTitle;
          if ($("anaChannelName")) $("anaChannelName").textContent = chTitle;
          if ($("dashChannelAvatar")) $("dashChannelAvatar").textContent = chTitle.charAt(0).toUpperCase();
          const statsText = `${subscribers} subscribers / ${lifetimeViews} lifetime views / ${num(totalViews)} views in the last 28 processed days / ${linkedCount} linked ${linkedCount === 1 ? 'video' : 'videos'}`;
          if ($("dashChannelStats")) $("dashChannelStats").textContent = statsText;
          if ($("anaChannelStats")) $("anaChannelStats").textContent = statsText;
        } else {
          if ($("dashChannelName")) $("dashChannelName").textContent = "No channel connected";
          if ($("anaChannelName")) $("anaChannelName").textContent = "No channel connected";
          if ($("dashChannelStats")) $("dashChannelStats").textContent = "Connect YouTube in Settings to load actual performance.";
          if ($("anaChannelStats")) $("anaChannelStats").textContent = "Connect YouTube in Settings to load actual performance.";
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
          const dtStr = run.created_at ? new Date(run.created_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : "Recently";
          const runId = Number(run.id);
          const linkButton = Number.isInteger(runId) && runId > 0
            ? `<button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)" onclick="linkVideoPrompt(${runId})">Link</button>`
            : `<button class="btn" style="padding:2px 8px;font-size:11px" disabled title="Reload history to restore this record ID">Link unavailable</button>`;
          return `
            <tr>
              <td style="font-weight:600;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span class="chip">Title quality heuristic</span></td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score)}</span> / 100</td>
              <td style="font-size:12px;color:var(--text-muted)">${dtStr}</td>
              <td style="display:flex;gap:6px">
                <a href="#creator" class="btn" style="padding:2px 8px;font-size:11px" onclick="switchPage('creator'); return false;">Inspect</a>
                ${linkButton}
                ${Number.isInteger(runId) && runId > 0 ? `<button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.3);color:#ef4444" onclick="deleteHistoryRun(${runId})">Delete</button>` : ""}
              </td>
            </tr>`;
        }).join("");

        const anaRowsHtml = runs.map((run) => {
          const dtStr = run.created_at ? new Date(run.created_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : "Recently";
          const runId = Number(run.id);
          const linkButton = Number.isInteger(runId) && runId > 0
            ? `<button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)" onclick="linkVideoPrompt(${runId})">Link</button>`
            : `<button class="btn" style="padding:2px 8px;font-size:11px" disabled title="Reload history to restore this record ID">Link unavailable</button>`;
          return `
            <tr>
              <td style="font-size:12px;color:var(--text-muted)">${dtStr} IST</td>
              <td style="font-weight:600;max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(run.title)}">${esc(run.title || run.query || "Untitled Video Analysis")}</td>
              <td><span style="font-weight:700;color:var(--accent)">${num(run.opportunity_score)}</span> / 100</td>
              <td><span class="chip">${num(run.title_score)} / 10</span></td>
              <td style="display:flex;gap:6px">
                <a href="#creator" class="btn" style="padding:2px 8px;font-size:11px" onclick="switchPage('creator'); return false;">Studio</a>
                ${linkButton}
                ${Number.isInteger(runId) && runId > 0 ? `<button class="btn" style="padding:2px 8px;font-size:11px;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.3);color:#ef4444" onclick="deleteHistoryRun(${runId})">Delete</button>` : ""}
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
      }
    }

    async function deleteHistoryRun(runId) {
      if (!confirm("Delete this saved package? It will be removed from this device and marked deleted for your synced devices.")) return;
      try {
        await apiRequest(`/api/history/runs/${runId}`, { method: "DELETE" });
        showToast("Saved package deleted successfully.");
        if ($("historyDetail")) $("historyDetail").classList.add("hidden");
        invalidateDashboardCache();
        loadHistoryFeed(true);
        loadSavedHistory();
      } catch (err) {
        showToast(formatApiError(err, "Could not delete package."));
      }
    }

    async function linkVideoPrompt(runId) {
      if (!Number.isInteger(Number(runId)) || Number(runId) <= 0) {
        alert("This history row is missing its database ID. Reload the page and try again.");
        return;
      }
      const videoId = prompt("Enter your published YouTube Video ID or URL for this package:");
      if (!videoId) return;
      try {
        await apiRequest(`/api/history/runs/${runId}/link-video`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ youtube_video_id: videoId })
        });
        showToast("Package linked to YouTube Video ID.");
        invalidateDashboardCache();
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
          body.innerHTML = "<tr><td colspan='5' style='color:var(--text-sub);text-align:center;padding:16px'>No linked or uploaded videos found yet. Connect YouTube in Settings to sync your channel videos.</td></tr>";
          return;
        }

        let html = "";
        if (uploadedVideos.length > 0) {
          html += uploadedVideos.map((v) => {
            const title = v.title || v.video_id || "YouTube Upload";
            const views = num(v.views || 0);
            const likes = num(v.likes || 0);
            const comments = num(v.comments || 0);
            const retention = v.average_view_percentage === null || v.average_view_percentage === undefined ? "Not collected" : num(v.average_view_percentage) + "% retention";
            const pubAt = v.published_at ? new Date(v.published_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', year:'numeric' }) : "Unknown date";
            const vidId = v.video_id || "";
            const linked = linksByVideo.get(String(vidId));
            if (linked) linksByVideo.delete(String(vidId));
            const ytLink = vidId ? `https://www.youtube.com/watch?v=${vidId}` : "#";
            const refreshAction = linked ? "<button class='btn' style='padding:4px 8px;font-size:11px' onclick='refreshLinkedVideo(" + Number(linked.id) + ", this)'>Refresh snapshot</button>" : "";
            return "<tr><td style='font-weight:600'><span class='chip chip-ok' style='font-size:10px;margin-right:6px'>Channel Upload</span> " + esc(title) + "<div class='metric-sub' style='font-size:11px'>ID: " + esc(vidId) + "</div></td>" +
              "<td>" + pubAt + "</td><td><strong style='color:var(--accent);font-size:15px'>" + views + "</strong></td><td>" + likes + " likes / " + comments + " comments<div class='metric-sub' style='font-size:11px'>" + retention + "</div></td>" +
              "<td style='display:flex;gap:6px;flex-wrap:wrap'><a href='" + ytLink + "' target='_blank' rel='noopener' class='btn' style='padding:4px 8px;font-size:11px'>Watch</a>" + refreshAction + "</td></tr>";
          }).join("");
        }

        const unmatchedLinks = Array.from(linksByVideo.values());
        if (unmatchedLinks.length) {
          html += unmatchedLinks.map((link) => {
            const metric = link.latest_performance || {};
            const title = link.selected_title || link.package_topic || link.youtube_video_id;
            const views = metric.views === null || metric.views === undefined ? "Not collected" : num(metric.views);
            const retention = metric.avg_view_percentage === null || metric.avg_view_percentage === undefined ? "Not collected" : num(metric.avg_view_percentage) + "%";
            const published = link.published_at ? new Date(link.published_at).toLocaleDateString('en-IN', { month:'short', day:'numeric', year:'numeric' }) : "Unknown date";
            return "<tr><td style='font-weight:600'><span class='chip chip-accent' style='font-size:10px;margin-right:6px'>Linked Package</span> " + esc(title) + "<div class='metric-sub' style='font-size:11px'>ID: " + esc(link.youtube_video_id) + "</div></td>" +
              "<td>" + published + " / " + esc(metric.snapshot_window || "No snapshot") + "</td><td><strong>" + views + "</strong></td><td>" + retention + " retention</td>" +
              "<td><button class='btn' style='padding:4px 8px;font-size:11px' onclick='refreshLinkedVideo(" + Number(link.id) + ", this)'>Refresh snapshot</button></td></tr>";
          }).join("");
        }

        body.innerHTML = html;
      } catch (error) {
        body.innerHTML = "<tr><td colspan='5' style='color:var(--bad);text-align:center;padding:16px'>" + esc(formatApiError(error, "Could not load channel video performance.")) + "</td></tr>";
      }
    }

    async function refreshLinkedVideo(linkId, button) {
      button.disabled = true;
      try {
        const data = await apiRequest("/api/published-videos/" + linkId + "/refresh", { method: "POST" });
        showToast(data.message || ((data.captured || []).length ? "Snapshot saved." : "No snapshot due yet."));
        invalidateDashboardCache();
        loadPublishedVideos(true);
        loadCohortLearning();
      } catch (error) {
        showToast(formatApiError(error, "Could not refresh this video."));
      } finally { button.disabled = false; }
    }

    async function loadCohortLearning() {
      try {
        const data = await apiRequest("/api/learning/cohorts");
        if ($("anaWinningAngle")) $("anaWinningAngle").textContent = data.confidence_label || "Collecting evidence";
        if ($("anaObservation")) $("anaObservation").textContent = data.recommendation || "Link and refresh published videos to build evidence.";
        if ($("anaRecommendation")) $("anaRecommendation").textContent = data.sample_size ? ("Cohort: " + data.sample_size + " linked videos. " + (data.recommendation || "")) : "Learning begins after linked videos receive real snapshots.";
      } catch (error) {
        if ($("anaWinningAngle")) $("anaWinningAngle").textContent = "Unavailable";
        if ($("anaObservation")) renderApiError($("anaObservation"), error, "Learning evidence is unavailable.");
      }
    }

    async function refreshYouTubeAnalytics(button = null, silent = false) {
      if (frontendState.analyticsRefreshRequest) return frontendState.analyticsRefreshRequest;
      const buttons = [button, $("anaRefreshBtn"), $("settRefreshBtn")].filter(Boolean);
      buttons.forEach((item) => { item.disabled = true; });
      if ($("anaSyncStatus")) $("anaSyncStatus").textContent = "Refreshing current counts from YouTube...";
      frontendState.analyticsRefreshRequest = (async () => {
        const data = await apiRequest("/youtube/channel/refresh", { method: "POST" });
        invalidateDashboardCache();
        await Promise.all([
          loadHistoryFeed(true),
          loadPublishedVideos(true),
          loadCohortLearning(),
          loadChannelStatus(true),
        ]);
        if (!silent) showToast("YouTube analytics and video counts updated.");
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

    let savedHistoryRuns = [];

    function historyRowHtml(run) {
      const title = run.title || run.query || "Untitled package";
      const isLinked = Boolean(run.linked_youtube_video_id);
      const selection = run.selected_package_id
        ? "<span class='chip chip-ok'>Selected package</span>"
        : "<span class='chip'>Selection unknown</span>";
      const linkAction = isLinked
        ? "<button class='btn history-action-btn' onclick='linkVideoPrompt(" + Number(run.id) + ")'>Change link</button>"
        : "<button class='btn history-action-btn' onclick='linkVideoPrompt(" + Number(run.id) + ")'>Link video</button>";
      return "<article class='history-row' data-history-run='" + Number(run.id) + "'>" +
        "<div class='history-row-main'><div class='history-row-title' title='" + esc(title) + "'><button onclick='openHistoryRun(" + Number(run.id) + ")'>" + esc(title) + "</button></div>" +
          "<div class='history-row-meta'><span>" + historyDate(run.created_at) + "</span><span aria-hidden='true'>·</span><span>" + esc(run.content_angle || run.intent || "General") + "</span>" + selection + (isLinked ? "<span class='chip chip-ok'>YouTube linked</span>" : "") + "</div></div>" +
        "<div class='history-score-group' aria-label='Package scores'><div class='history-score'><span class='history-score-label'>Opportunity</span><span class='history-score-value'>" + num(run.opportunity_score) + "/100</span></div><div class='history-score'><span class='history-score-label'>Title quality</span><span class='history-score-value'>" + num(run.title_score) + "/10</span></div></div>" +
        "<div class='history-row-actions'><button class='btn btn-primary history-action-btn' onclick='openHistoryRun(" + Number(run.id) + ")'>View package</button>" + linkAction + "<button class='btn history-action-btn history-action-danger' onclick='deleteHistoryRun(" + Number(run.id) + ")'>Delete</button></div>" +
      "</article>";
    }

    function renderSavedHistory(query = "") {
      const body = $("historyPageBody");
      if (!body) return;
      const needle = String(query || "").trim().toLowerCase();
      const visibleRuns = needle ? savedHistoryRuns.filter((run) =>
        [run.title, run.query, run.content_angle, run.intent].some((value) => String(value || "").toLowerCase().includes(needle))
      ) : savedHistoryRuns;
      const count = $("historyRunCount");
      const summary = $("historyResultSummary");
      if (count) count.textContent = savedHistoryRuns.length + " saved " + (savedHistoryRuns.length === 1 ? "package" : "packages");
      if (summary) summary.textContent = needle
        ? visibleRuns.length + " of " + savedHistoryRuns.length + " packages match “" + String(query) + "”"
        : savedHistoryRuns.length + " package" + (savedHistoryRuns.length === 1 ? "" : "s") + " available";
      if (!visibleRuns.length) {
        body.innerHTML = "<div class='history-empty'>" + (savedHistoryRuns.length ? "No saved packages match your search." : "No saved packages yet. Generate an SEO package and it will appear here.") + "</div>";
        return;
      }
      body.innerHTML = visibleRuns.map(historyRowHtml).join("");
    }

    function filterHistoryRuns(query = "") {
      renderSavedHistory(query);
    }

    async function loadSavedHistory() {
      const body = $("historyPageBody");
      if (!body) return;
      try {
        const data = await apiRequest("/api/history/runs");
        savedHistoryRuns = data.runs || [];
        renderSavedHistory($("historySearch") ? $("historySearch").value : "");
      } catch (error) {
        savedHistoryRuns = [];
        if ($("historyRunCount")) $("historyRunCount").textContent = "Records unavailable";
        if ($("historyResultSummary")) $("historyResultSummary").textContent = "Could not load saved packages.";
        body.innerHTML = "<div class='history-empty' style='color:var(--bad)'>" + esc(formatApiError(error, "Could not load saved packages.")) + "</div>";
      }
    }

    async function openHistoryRun(runId) {
      const panel = $("historyDetail");
      if (!panel) return;
      panel.classList.remove("hidden");
      panel.innerHTML = "<div class='metric-sub'>Loading saved package...</div>";
      try {
        const run = await apiRequest("/api/history/runs/" + runId);
        const packageData = run.package || {};
        const fullScript = packageData.creator_brief && packageData.creator_brief.content
          ? packageData.creator_brief.content
          : run.query;
        const tags = arr(packageData.tags).map((tag) => "<span class='tag-item'>" + esc(tag) + "</span>").join("") || "<span class='metric-sub'>Not stored in this older record.</span>";
        const hashtags = arr(packageData.hashtags).map((tag) => "<span class='tag-item'>" + esc(tag) + "</span>").join("") || "<span class='metric-sub'>Not stored in this older record.</span>";
        const variants = arr(packageData.title_variants).map((item) => "<li>" + esc(typeof item === "string" ? item : item.title || "") + "</li>").join("") || "<li>Not stored in this older record.</li>";
        const chapters = arr(packageData.chapters).map((item) => "<li>" + esc((item.timestamp || "") + " " + (item.title || item)) + "</li>").join("") || "<li>Not stored in this older record.</li>";
        const report = run.linked_video_report || {};
        const selection = run.selected_package || null;
        const selectedData = selection && selection.package ? selection.package : null;
        const selectionHtml = selectedData
          ? "<div class='history-link-callout'><div><strong>Creator-selected package</strong><div class='metric-sub'>" + esc(selectedData.title || "Selected package") + " · selected " + historyDate(selection.selected_at) + "</div></div><span class='chip chip-ok'>Explicitly recorded</span></div>"
          : "<div class='history-link-callout'><div><strong>Creator-selected package</strong><div class='metric-sub'>No explicit selection was recorded. The tool will not infer one after publishing.</div></div><span class='chip'>Unknown</span></div>";
        const retention = packageData.retention_assistant || {};
        const retentionRisks = arr(retention.risk_map).flatMap((stage) => arr((stage || {}).risks));
        const retentionHtml = Object.keys(retention).length
          ? "<div class='history-link-callout'><div><strong>Retention guidance: " + esc(retention.risk_level || "unknown") + " risk</strong><div class='metric-sub'>" + esc((retention.trace || {}).timing_basis || "relative stage") + " · " + retentionRisks.length + " deterministic finding(s). This is pre-publish guidance, not measured retention.</div></div><span class='chip'>" + esc(retention.rule_version || "Local rules") + "</span></div>"
          : "";
        const linkedHtml = report.linked ? linkedVideoReportHtml(report, run.id) :
          "<div class='history-link-callout'><div><strong>Published-video learning</strong><div class='metric-sub'>No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package.</div></div><button class='btn' onclick='linkVideoPrompt(" + Number(run.id) + ")'>Link video</button></div>";
        const legacy = !run.package
          ? "<div class='alert-banner' style='background:var(--warn-bg);border:1px solid rgba(245,158,11,.3);color:#fcd34d;margin-top:16px'>This package was created before full-package history was added. Its saved title, script, and scores are shown below; future packages retain the complete generated output.</div>"
          : "";
        const linkState = report.linked ? "Linked to YouTube" : "Not linked";
        panel.innerHTML =
          "<div class='history-detail-header'><div><div class='eyebrow'>SAVED PACKAGE · " + historyDate(run.created_at) + "</div><h2 class='history-detail-title'>" + esc(packageData.title || run.title || "Untitled package") + "</h2><div class='history-detail-meta'><span>" + esc(run.content_angle || run.intent || "General") + "</span><span aria-hidden='true'>·</span><span>" + esc(run.opportunity_label || "Saved generation") + "</span></div></div><div class='history-detail-actions'><button class='btn history-action-danger' onclick='deleteHistoryRun(" + Number(run.id) + ")'>Delete package</button><button class='btn' onclick='closeHistoryDetail()'>Close</button></div></div>" +
          "<div class='history-detail-body'><div class='history-summary-grid'><div class='history-summary-stat'><span>Opportunity</span><strong>" + num(run.opportunity_score) + " / 100</strong></div><div class='history-summary-stat'><span>Title quality</span><strong>" + num(run.title_score) + " / 10</strong></div><div class='history-summary-stat'><span>Package selection</span><strong>" + (selectedData ? "Recorded" : "Unknown") + "</strong></div><div class='history-summary-stat'><span>Publishing status</span><strong>" + linkState + "</strong></div></div>" +
          legacy + selectionHtml + retentionHtml + linkedHtml +
          "<div class='history-detail-grid'><section class='history-section'><div class='history-section-heading'>Description</div><div class='history-longform'>" + esc(packageData.description || "Not stored in this older record.") + "</div></section>" +
          "<section class='history-section'><div class='history-section-heading'>Original video content / script</div><div class='history-longform'>" + esc(fullScript || "Not stored.") + "</div></section>" +
          "<section class='history-section'><div class='history-section-heading'>Tags &amp; hashtags</div><div class='tag-list'>" + tags + "</div><div class='history-section-heading' style='margin-top:18px'>Hashtags</div><div class='tag-list'>" + hashtags + "</div></section>" +
          "<section class='history-section'><details open><summary>Title variations</summary><div><ol class='history-detail-list'>" + variants + "</ol></div></details><details><summary>Chapters</summary><div><ol class='history-detail-list'>" + chapters + "</ol></div></details></section></div></div>";
        const syncedAt = report.metadata_synced_at || (report.performance || {}).captured_at;
        const stale = !syncedAt || Date.now() - new Date(syncedAt).getTime() > 10 * 60 * 1000;
        if (report.linked && stale && !historyPerformanceAutoRefresh.has(Number(report.link_id))) {
          historyPerformanceAutoRefresh.add(Number(report.link_id));
          refreshHistoryPerformance(Number(report.link_id), Number(run.id), null, true);
        }
      } catch (error) {
        panel.innerHTML = "<div class='alert-banner alert-err'>" + esc(formatApiError(error, "Could not open this saved package.")) + "</div>";
      }
    }

    const historyPerformanceAutoRefresh = new Set();

    function linkedVideoReportHtml(report, runId) {
      const yt = report.youtube || {};
      const usage = report.package_usage || {};
      const perf = report.performance || {};
      const diagnosis = report.diagnosis || {};
      const baseline = report.baseline || {};
      const metric = (value, suffix = "") => value === null || value === undefined ? "Not available yet" : num(value) + suffix;
      const list = (items, empty) => arr(items).length
        ? "<ul style='padding-left:20px;line-height:1.65;margin:8px 0'>" + arr(items).map((item) => "<li>" + esc(item) + "</li>").join("") + "</ul>"
        : "<div class='metric-sub'>" + esc(empty) + "</div>";
      const tagList = (items, empty) => arr(items).length
        ? "<div class='tag-list'>" + arr(items).map((item) => "<span class='tag-item'>" + esc(item) + "</span>").join("") + "</div>"
        : "<div class='metric-sub'>" + esc(empty) + "</div>";
      const titleStatus = usage.title_match ? "Exact generated title used" : "Uploaded title differs from generated title";
      const attribution = usage.attribution_status === "creator_selected" ? "Creator-selected package" : "Package selection unknown";
      const comparable = report.comparable_metadata || {};
      const retentionLearning = report.retention_learning || {};
      const learningCount = num(retentionLearning.sample_size || 0);
      const learningMinimum = num(retentionLearning.minimum_samples || 5);
      const retentionLearningHtml = "<section class='history-learning-panel'><div class='history-panel-heading'><div><div class='eyebrow'>CHANNEL LEARNING</div><h3>Retention evidence</h3></div><span class='chip'>" + esc(retentionLearning.status || "insufficient_evidence").replaceAll("_", " ") + "</span></div>" +
        "<div class='history-learning-progress'><div><strong>" + learningCount + " of " + learningMinimum + " comparable videos</strong><span>with verified 24-hour retention data</span></div><div class='history-progress-track' aria-label='" + learningCount + " of " + learningMinimum + " comparable videos'><span style='width:" + Math.min(100, Math.round((Number(retentionLearning.sample_size || 0) / Math.max(1, Number(retentionLearning.minimum_samples || 5))) * 100)) + "%'></span></div></div>" +
        "<p class='metric-sub'>" + esc(retentionLearning.message || "No eligible retention pattern is available.") + " The tool surfaces patterns only after enough like-for-like videos exist; it does not claim that a package caused views or retention.</p></section>";
      const sources = comparable.sources || {};
      const sourceLabel = (source) => ({creator:"Creator confirmed", youtube_verified:"YouTube verified", package:"From package", unknown:"Unknown"}[source] || "Unknown");
      const metadataEditor = "<section class='history-comparable-panel'><div class='history-panel-heading'><div><div class='eyebrow'>COMPARISON SETUP</div><h3>Comparable learning metadata</h3></div><span class='chip'>Local only</span></div><p class='metric-sub'>These labels group similar videos for future learning. Saving them does not edit the YouTube video.</p><div class='history-metadata-grid'>" +
        ["language","format","duration_bucket","topic_category"].map((field) => "<label class='history-metadata-field'><span>" + esc(field.replaceAll("_", " ")) + " <small class='chip'>" + esc(sourceLabel(sources[field])) + "</small></span><input id='comparable-" + field + "' value='" + esc(comparable[field] === "unknown" ? "" : comparable[field] || "") + "' maxlength='80' placeholder='Not set'></label>").join("") +
        "</div><div class='history-form-actions'><button class='btn btn-primary' onclick='saveComparableMetadata(" + Number(report.link_id) + "," + Number(runId) + ")'>Save local labels</button><button class='btn' onclick='openHistoryRun(" + Number(runId) + ")'>Discard changes</button></div><div id='comparable-meta-error' class='metric-sub' style='color:var(--bad);margin-top:8px'></div></section>";
      const snapshots = arr(report.snapshots);
      const snapshotRows = snapshots.map((snapshot) => {
        const complete = snapshot.avg_view_percentage !== null && snapshot.avg_view_percentage !== undefined;
        const windowLabel = snapshot.snapshot_window || "current";
        const state = complete ? "Retention available" : windowLabel === "current" ? "Live counts" : "Retention pending";
        return "<div class='history-snapshot-row'><div><strong>" + esc(windowLabel) + "</strong><span class='chip " + (complete ? "chip-ok" : "") + "'>" + state + "</span></div><div><span>Views</span><strong>" + metric(snapshot.views) + "</strong></div><div><span>Likes</span><strong>" + metric(snapshot.likes) + "</strong></div><div><span>Average viewed</span><strong>" + metric(snapshot.avg_view_percentage, "%") + "</strong></div><div><span>Captured</span><strong>" + historyDate(snapshot.captured_at) + "</strong></div></div>";
      }).join("") || "<div class='history-empty'>No performance snapshot has been captured yet.</div>";
      return "<section class='history-linked-report'>" +
       "<header class='history-linked-header'><div><div class='eyebrow'>LINKED YOUTUBE VIDEO</div><h3>" + esc(diagnosis.verdict || "Collecting evidence") + "</h3><p>Published " + historyDate(report.published_at) + " · Last refreshed " + historyDate(report.metadata_synced_at || perf.captured_at) + "</p></div><div class='history-detail-actions'><span class='chip chip-ok'>" + esc(diagnosis.confidence || "LOW") + " confidence</span><a class='btn' target='_blank' rel='noopener' href='" + esc(report.video_url) + "'>Watch video</a><button class='btn' onclick='refreshHistoryPerformance(" + Number(report.link_id) + "," + Number(runId) + ",this)'>Refresh data</button></div></header>" +
        "<div class='history-linked-grid'><section class='history-section'><div class='history-section-heading'>Actual YouTube upload</div>" +
          (yt.thumbnail_url ? "<img class='history-youtube-thumb' src='" + esc(yt.thumbnail_url) + "' alt=''>" : "") +
          "<div class='history-upload-title'>" + esc(yt.title || usage.uploaded_title || "Metadata not refreshed yet") + "</div><div class='history-detail-meta'><span>" + esc(attribution) + "</span><span>·</span><span>" + esc(titleStatus) + "</span><span>·</span><span>Description match " + metric(usage.description_match_percent, "%") + "</span></div>" +
          "<details><summary>Description currently on YouTube</summary><div class='history-longform'>" + esc(yt.description || "No description returned.") + "</div></details><details><summary>Tags &amp; hashtags found on YouTube</summary><div><div class='history-mini-label'>Uploaded tags</div>" + tagList(usage.uploaded_tags, "No uploaded tags were returned by YouTube.") + "<div class='history-mini-label'>Generated tags used</div>" + tagList(usage.matching_tags, "None of the generated tags currently match the uploaded tags.") + "<div class='history-mini-label'>Hashtags in description</div>" + tagList(usage.uploaded_hashtags, "No hashtags were detected in the uploaded description.") + "</div></details></section>" +
          "<section class='history-section'><div class='history-section-heading'>Current observed performance <span class='chip'>Video-level data</span></div><div class='history-performance-grid'>" +
            "<div><span>Views</span><strong>" + metric(perf.views) + "</strong></div><div><span>Likes</span><strong>" + metric(perf.likes) + "</strong></div><div><span>Comments</span><strong>" + metric(perf.comments) + "</strong></div><div><span>Average viewed</span><strong>" + metric(perf.average_view_percentage, "%") + "</strong></div><div><span>Avg. view duration</span><strong>" + metric(perf.average_view_duration_seconds, " sec") + "</strong></div><div><span>Subscribers gained</span><strong>" + metric(perf.subscribers_gained) + "</strong></div></div>" +
            "<p class='metric-sub'>Public counts can update before retention analytics. Comparable baseline: " + num(baseline.sample_size || 0) + " other videos at " + esc(baseline.window || "no scheduled window") + ".</p></section>" +
          "<section class='history-section'><div class='history-section-heading'>What the evidence supports</div>" + list(diagnosis.what_worked, "No positive conclusion is supported yet.") + "</section><section class='history-section'><div class='history-section-heading'>What remains unknown</div>" + list(diagnosis.needs_improvement, "No issue has been detected from the available evidence.") + "</section></div>" +
          retentionLearningHtml + metadataEditor +
          "<section class='history-snapshots-panel'><div class='history-panel-heading'><div><div class='eyebrow'>OBSERVATION HISTORY</div><h3>Performance snapshots</h3></div><span class='metric-sub'>Video ID " + esc(report.video_id) + "</span></div><div class='history-snapshot-list'>" + snapshotRows + "</div><p class='metric-sub'>" + esc(diagnosis.attribution_note || "YouTube reports video-level performance; it cannot attribute views to individual tags.") + "</p></section>" +
        "</section>";
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
        await apiRequest("/api/published-videos/" + Number(linkId) + "/refresh", { method: "POST" });
        if (!silent) showToast("YouTube metadata and available analytics refreshed.");
        invalidateDashboardCache();
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
      out.textContent = "Running one live YouTube Data API search check...";
      try {
        const data = await apiRequest("/diagnostics");
        const yt = data.youtube || {};
        const gemini = data.gemini || {};
        out.innerHTML = `<div class="kv-list"><div class="kv-item"><span class="kv-key">YouTube live request</span><span class="kv-val"><span class="chip ${yt.status === "ok" ? "chip-ok" : ""}">${esc(yt.status || "unavailable")}</span></span></div><div class="kv-item"><span class="kv-key">YouTube result</span><span class="kv-val">${esc(yt.error || yt.warning || "Request succeeded; one configured key was used.")}</span></div><div class="kv-item"><span class="kv-key">Gemini configuration</span><span class="kv-val"><span class="chip ${gemini.configured ? "chip-ok" : ""}">${gemini.configured ? `Configured / ${esc(gemini.model)}` : "Not configured; fallback will be used"}</span></span></div></div>`;
      } catch (e) {
        renderApiError(out, e, "Diagnostics failed.");
      } finally {
        button.disabled = false;
      }
    });

    function formatBytes(value) {
      const bytes = Number(value);
      if (!Number.isFinite(bytes)) return "Unavailable";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1048576).toFixed(1)} MB`;
    }

    async function loadSettingsStatus() {
      try {
        const data = await apiRequest("/api/settings/status", { cache: "no-store" });
        const app = data.app || {}, db = data.database || {}, providers = data.providers || {};
        const gemini = providers.gemini || {}, yt = providers.youtube_data_api || {}, counts = db.counts || {};
        if ($("appVersionBadge")) $("appVersionBadge").textContent = `OS v${app.version || "unknown"}`;
        if ($("sidebarRuntimeStatus")) $("sidebarRuntimeStatus").innerHTML = `<span class="dot"></span> ${gemini.configured ? `Gemini ${esc(gemini.model)}` : "Local fallback"} / DB ${db.healthy ? "healthy" : "error"}`;
        $("settGeminiProvider").innerHTML = `<span class="chip ${gemini.configured ? "chip-ok" : ""}">${gemini.configured ? `Configured / ${esc(gemini.model)}` : "Not configured"}</span>`;
        $("settFallbackProvider").innerHTML = `<span class="chip chip-ok">Available / used when Gemini fails</span>`;
        $("settYouTubeKeys").innerHTML = `<span class="chip ${yt.configured ? "chip-ok" : ""}">${yt.configured ? `${num(yt.key_count)} configured` : "Not configured"}</span>`;
        $("settRedisStatus").innerHTML = `<span class="chip ${providers.redis?.configured ? "chip-ok" : ""}">${providers.redis?.configured ? "Configured" : "Not configured"}</span>`;
        $("settDatabaseStatus").innerHTML = `<span class="chip ${db.healthy ? "chip-ok" : ""}">${db.healthy ? "Healthy" : "Error"}</span> ${esc(db.name || "Unknown")} / schema v${num(db.schema_version)} / ${formatBytes(db.size_bytes)}`;
        $("settDatabaseCounts").textContent = `${num(counts.packages)} packages / ${num(counts.ideas)} ideas / ${num(counts.published_links)} linked videos / ${num(counts.performance_snapshots)} performance snapshots`;
        $("settBackupStatus").textContent = db.last_backup_at ? historyDate(db.last_backup_at) : "No migration backup recorded";
      } catch (error) {
        ["settGeminiProvider","settFallbackProvider","settYouTubeKeys","settRedisStatus","settDatabaseStatus","settDatabaseCounts","settBackupStatus"].forEach(id => { if ($(id)) $(id).textContent = "Status unavailable"; });
      }
    }

    async function loadChannelStatus(force = false) {
      try {
        const data = await apiRequest("/youtube/channel/status", { cache: force ? "reload" : "no-store" });
        frontendState.latestChannelStatus = data;
        const settStatus = $("settChannelStatus");
        const connectBtn = $("settConnectBtn");
        const refreshBtn = $("settRefreshBtn");
        const disconnectBtn = $("settDisconnectBtn");
        connectBtn.onclick = () => { window.location.href = "/youtube/channel/connect"; };

        if (!data.configured) {
          settStatus.textContent = data.setup_message || "OAuth setup is required.";
          $("dashChannelStats").textContent = "OAuth setup required.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Set up OAuth";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return data;
        }
        if (!data.connected) {
          settStatus.textContent = "Ready to connect with read-only permissions.";
          $("dashChannelStats").textContent = "Ready to connect.";
          connectBtn.style.display = "inline-flex";
          connectBtn.textContent = "Connect Channel";
          refreshBtn.style.display = "none";
          disconnectBtn.style.display = "none";
          return data;
        }
        const channel = data.channel || {};
        const sync = (data.latest_sync || {}).data || {};
        const current = sync.current_28_days || {};
        const liveChannel = sync.channel || {};
        const learning = sync.video_learning || {};

        const channelTitle = channel.title || "YouTube Channel";
        const statsStr = `${num(liveChannel.subscribers)} subscribers / ${num(liveChannel.real_total_views)} lifetime views / ${num(current.views)} views in the last 28 processed days`;
        const recStr = learning.recommendation || "Refresh analytics to update learning.";

        $("dashChannelName").textContent = channelTitle;
        $("dashChannelStats").textContent = statsStr;
        $("anaChannelName").textContent = channelTitle;
        $("anaChannelStats").textContent = statsStr;
        if ($("anaSubscribers")) $("anaSubscribers").textContent = num(liveChannel.subscribers);
        if ($("anaLifetimeViews")) $("anaLifetimeViews").textContent = num(liveChannel.real_total_views);
        if ($("ana28dViews")) $("ana28dViews").textContent = num(current.views);
        if ($("anaWatchTime")) $("anaWatchTime").textContent = num(current.estimatedMinutesWatched) + " mins";
        if ($("anaSyncStatus")) $("anaSyncStatus").textContent = data.latest_sync?.synced_at ? "Last synced: " + historyDate(data.latest_sync.synced_at) : "No completed YouTube sync.";
        $("anaRecommendation").textContent = recStr;
        const lastChannelSync = data.latest_sync?.synced_at ? historyDate(data.latest_sync.synced_at) : "not refreshed yet";
        settStatus.textContent = `Connected to ${channelTitle}. ${statsStr}. Last analytics refresh: ${lastChannelSync}.`;

        connectBtn.style.display = "none";
        refreshBtn.style.display = "inline-flex";
        disconnectBtn.style.display = "inline-flex";
        refreshBtn.onclick = () => refreshYouTubeAnalytics(refreshBtn);
        disconnectBtn.onclick = async () => {
          if (!confirm("Disconnect YouTube channel?")) return;
          try {
            await apiRequest("/youtube/channel/disconnect", {method:"POST"});
          } catch (error) {
            renderApiError(settStatus, error, "Could not disconnect the channel.");
            return;
          }
          await loadChannelStatus();
        };
        return data;
      } catch (error) {
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
    // Page modules own their guarded lifecycle seams. The Creator receives only
    // explicit app-shell callbacks and owns all of its rendering and behavior.
    mountDashboardPage();
    mountSettingsPage();
    mountAnalyticsPage();
    mountHistoryPage();
    mountCreatorPage(document, {
      notify: showToast,
      onAnalysisSaved: () => {
        invalidateDashboardCache();
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

    // History and shell markup still use these narrow compatibility handlers.
    // Creator actions are delegated inside pages/creator.js and expose no globals.
    Object.assign(window, {
      applyTemplate, switchPage, deleteHistoryRun,
      linkVideoPrompt, refreshLinkedVideo, openHistoryRun, closeHistoryDetail,
      filterHistoryRuns,
      saveComparableMetadata, refreshHistoryPerformance,
    });
