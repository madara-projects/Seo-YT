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
      const validThemes = ["obsidian", "cyber", "emerald", "light"];
      const safeTheme = validThemes.includes(themeKey) ? themeKey : "obsidian";
      document.documentElement.setAttribute("data-theme", safeTheme);
      try { localStorage.setItem("yt_seo_theme", safeTheme); } catch (_) {}
      const sel = $("themeSelector");
      if (sel) sel.value = safeTheme;
    }

    const savedTheme = (function() { try { return localStorage.getItem("yt_seo_theme") || "obsidian"; } catch(_) { return "obsidian"; } })();
    setTheme(savedTheme);

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
      if (!confirm("Are you sure you want to delete this saved package from your SQLite database?")) return;
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

    async function loadSavedHistory() {
      const body = $("historyPageBody");
      if (!body) return;
      try {
        const data = await apiRequest("/api/history/runs");
        const runs = data.runs || [];
        if (!runs.length) {
          body.innerHTML = "<tr><td colspan='5' style='color:var(--text-muted);text-align:center;padding:16px'>No saved packages yet.</td></tr>";
          return;
        }
        body.innerHTML = runs.map((run) => {
          const linkControl = run.linked_youtube_video_id
            ? "<span class='chip chip-ok'>Linked</span><button class='btn' style='padding:4px 10px;font-size:11px' onclick='linkVideoPrompt(" + Number(run.id) + ")'>Change link</button>"
            : "<button class='btn' style='padding:4px 10px;font-size:11px;background:rgba(229,9,20,0.15);border-color:rgba(229,9,20,0.3)' onclick='linkVideoPrompt(" + Number(run.id) + ")'>Link</button>";
          return "<tr>" +
          "<td style='font-size:12px;color:var(--text-muted)'>" + historyDate(run.created_at) + "</td>" +
          "<td style='font-weight:600;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='" + esc(run.title) + "'>" + esc(run.title || run.query || "Untitled package") + "</td>" +
          "<td><span style='font-weight:700;color:var(--accent)'>" + num(run.opportunity_score) + "</span> / 100</td>" +
          "<td><span class='chip chip-ok'>" + num(run.title_score) + " / 10</span></td>" +
          "<td style='display:flex;gap:6px'>" +
          "<button class='btn' style='padding:4px 10px;font-size:11px' onclick='openHistoryRun(" + Number(run.id) + ")'>Open</button>" +
          linkControl +
          "<button class='btn' style='padding:4px 10px;font-size:11px;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.3);color:#ef4444' onclick='deleteHistoryRun(" + Number(run.id) + ")'>Delete</button>" +
          "</td>" +
          "</tr>";
        }).join("");
      } catch (error) {
        body.innerHTML = "<tr><td colspan='5' style='color:var(--bad);text-align:center;padding:16px'>" + esc(formatApiError(error, "Could not load saved packages.")) + "</td></tr>";
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
        const linkedHtml = report.linked ? linkedVideoReportHtml(report, run.id) :
          "<div class='bento-card' style='margin-top:18px'><div class='card-title'>Published-video learning</div><div class='metric-sub'>No YouTube video is linked to this package yet. Use Link on the History row after publishing.</div></div>";
        const legacy = !run.package
          ? "<div class='alert-banner' style='background:var(--warn-bg);border:1px solid rgba(245,158,11,.3);color:#fcd34d;margin-top:16px'>This package was created before full-package history was added. Its saved title, script, and scores are shown below; future packages retain the complete generated output.</div>"
          : "";
        panel.innerHTML =
          "<div class='card-title'><span>Saved Package / " + historyDate(run.created_at) + "</span><div style='display:flex;gap:8px'><button class='btn' style='padding:4px 10px;font-size:11px;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.3);color:#ef4444' onclick='deleteHistoryRun(" + Number(run.id) + ")'>Delete Package</button><button class='btn' style='padding:4px 10px;font-size:11px' onclick='closeHistoryDetail()'>Close</button></div></div>" +
          "<div class='metric-value' style='font-size:24px'>" + esc(packageData.title || run.title || "Untitled package") + "</div>" +
          "<div class='metric-sub' style='margin-top:8px'>Opportunity " + num(run.opportunity_score) + "/100 / Title score " + num(run.title_score) + "/10 / " + esc(run.content_angle || "General") + "</div>" +
          legacy +
          linkedHtml +
          "<div class='bento-grid' style='margin-top:18px'>" +
          "<div class='bento-card span-6'><div class='card-title'>Description</div><div style='white-space:pre-wrap;line-height:1.6'>" + esc(packageData.description || "Not stored in this older record.") + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Original video content / script</div><div style='white-space:pre-wrap;line-height:1.6;max-height:420px;overflow-y:auto'>" + esc(fullScript || "Not stored.") + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Tags</div><div class='tag-list'>" + tags + "</div><div class='card-title' style='margin-top:18px'>Hashtags</div><div class='tag-list'>" + hashtags + "</div></div>" +
          "<div class='bento-card span-6'><div class='card-title'>Title variations</div><ol style='padding-left:20px;line-height:1.8'>" + variants + "</ol><div class='card-title' style='margin-top:18px'>Chapters</div><ol style='padding-left:20px;line-height:1.8'>" + chapters + "</ol></div>" +
          "</div>";
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
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
      const comparable = report.comparable_metadata || {};
      const sources = comparable.sources || {};
      const sourceLabel = (source) => ({creator:"Creator confirmed", youtube_verified:"YouTube verified", package:"From package", unknown:"Unknown"}[source] || "Unknown");
      const metadataEditor = "<div class='bento-card span-12' style='margin-top:12px'><div class='card-title'>Comparable learning metadata</div><div class='metric-sub'>These local labels control future cohort comparisons. They do not edit YouTube.</div><div class='bento-grid' style='margin-top:10px'>" +
        ["language","format","duration_bucket","topic_category"].map((field) => "<label class='field span-3' style='display:block'><span class='field-label'>" + esc(field.replaceAll("_", " ")) + " <small class='chip'>" + esc(sourceLabel(sources[field])) + "</small></span><input id='comparable-" + field + "' value='" + esc(comparable[field] === "unknown" ? "" : comparable[field] || "") + "' maxlength='80' placeholder='Unknown'></label>").join("") +
        "</div><div style='display:flex;gap:8px;margin-top:10px'><button class='btn btn-primary' onclick='saveComparableMetadata(" + Number(report.link_id) + "," + Number(runId) + ")'>Save metadata</button><button class='btn' onclick='openHistoryRun(" + Number(runId) + ")'>Cancel</button></div><div id='comparable-meta-error' class='metric-sub' style='color:var(--bad);margin-top:8px'></div></div>";
      const snapshotRows = arr(report.snapshots).map((snapshot) =>
        "<tr><td>" + esc(snapshot.snapshot_window || "current") + "</td><td>" + metric(snapshot.views) + "</td><td>" + metric(snapshot.likes) + "</td><td>" + metric(snapshot.avg_view_percentage, "%") + "</td><td>" + historyDate(snapshot.captured_at) + "</td></tr>"
      ).join("") || "<tr><td colspan='5' class='metric-sub'>No performance snapshot has been captured yet.</td></tr>";
      return "<div class='bento-card' style='margin-top:18px;border-top:3px solid var(--ok)'>" +
       "<div class='card-title'><span>Linked YouTube performance &amp; learning</span><div style='display:flex;gap:8px;flex-wrap:wrap'>" +
       "<span class='chip chip-ok'>" + esc(diagnosis.confidence || "LOW") + " confidence</span>" +
       "<a class='btn' target='_blank' rel='noopener' href='" + esc(report.video_url) + "'>Watch video</a>" +
        "<button class='btn' onclick='refreshHistoryPerformance(" + Number(report.link_id) + "," + Number(runId) + ",this)'>Refresh YouTube data</button></div></div>" +
        "<div style='font-size:18px;font-weight:800;margin-top:8px'>" + esc(diagnosis.verdict || "Collecting evidence") + "</div>" +
        "<div class='metric-sub' style='margin-top:6px'>Published " + historyDate(report.published_at) + " / Video ID " + esc(report.video_id) + " / Last data " + historyDate(report.metadata_synced_at || perf.captured_at) + "</div>" +
        "<div class='bento-grid' style='margin-top:16px'>" +
          "<div class='bento-card span-6'><div class='card-title'>Actual YouTube upload</div>" +
            (yt.thumbnail_url ? "<img src='" + esc(yt.thumbnail_url) + "' alt='' style='width:180px;max-width:100%;border-radius:10px;margin-bottom:12px'>" : "") +
            "<div style='font-weight:750;line-height:1.5'>" + esc(yt.title || usage.uploaded_title || "Metadata not refreshed yet") + "</div>" +
            "<div class='metric-sub' style='margin:8px 0'>" + esc(titleStatus) + " / Description adoption " + metric(usage.description_match_percent, "%") + "</div>" +
            "<details style='margin:12px 0'><summary style='cursor:pointer;font-weight:700'>Description currently on YouTube</summary><div style='white-space:pre-wrap;line-height:1.55;max-height:220px;overflow-y:auto;margin-top:10px'>" + esc(yt.description || "No description returned.") + "</div></details>" +
            "<div class='card-title' style='margin-top:14px'>Tags actually on YouTube</div>" + tagList(usage.uploaded_tags, "No uploaded tags were returned by YouTube.") +
            "<div class='card-title' style='margin-top:14px'>Generated tags used</div>" + tagList(usage.matching_tags, "None of the generated tags currently match the uploaded tags.") +
            "<div class='card-title' style='margin-top:14px'>Hashtags actually in description</div>" + tagList(usage.uploaded_hashtags, "No hashtags were detected in the uploaded description.") +
          "</div>" +
          "<div class='bento-card span-6'><div class='card-title'>Current real performance</div>" +
            "<div class='kv-list'>" +
              "<div class='kv-item'><span class='kv-key'>Views</span><span class='kv-val'>" + metric(perf.views) + "</span></div>" +
              "<div class='kv-item'><span class='kv-key'>Likes / like rate</span><span class='kv-val'>" + metric(perf.likes) + " / " + metric(perf.like_rate_percent, "%") + "</span></div>" +
              "<div class='kv-item'><span class='kv-key'>Comments</span><span class='kv-val'>" + metric(perf.comments) + "</span></div>" +
              "<div class='kv-item'><span class='kv-key'>Average viewed</span><span class='kv-val'>" + metric(perf.average_view_percentage, "%") + "</span></div>" +
              "<div class='kv-item'><span class='kv-key'>Average view duration</span><span class='kv-val'>" + metric(perf.average_view_duration_seconds, " sec") + "</span></div>" +
              "<div class='kv-item'><span class='kv-key'>Subscribers gained</span><span class='kv-val'>" + metric(perf.subscribers_gained) + "</span></div>" +
            "</div><div class='metric-sub' style='margin-top:10px'>Analytics retention can lag behind public view/like counts. Comparable baseline: " + num(baseline.sample_size || 0) + " other videos at " + esc(baseline.window || "no scheduled window") + ".</div>" +
          "</div>" +
          "<div class='bento-card span-6'><div class='card-title'>What worked / positive observations</div>" + list(diagnosis.what_worked, "No positive conclusion is supported yet.") + "</div>" +
          "<div class='bento-card span-6'><div class='card-title'>What to improve / still unknown</div>" + list(diagnosis.needs_improvement, "No issue has been detected from the available evidence.") + "</div>" +
          metadataEditor +
          "<div class='bento-card span-12'><div class='card-title'>Performance snapshots</div><div style='overflow-x:auto'><table><thead><tr><th>Window</th><th>Views</th><th>Likes</th><th>Average viewed</th><th>Captured</th></tr></thead><tbody>" + snapshotRows + "</tbody></table></div>" +
            "<div class='metric-sub' style='margin-top:10px'>" + esc(diagnosis.attribution_note || "") + "</div></div>" +
        "</div></div>";
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
      $("historyDetail").classList.add("hidden");
    }

    $("runDiagBtn").addEventListener("click", async () => {
      const out = $("settDiagOut");
      out.textContent = "Running diagnostics...";
      try {
        const data = await apiRequest("/diagnostics");
        out.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        renderApiError(out, e, "Diagnostics failed.");
      }
    });

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
        settStatus.textContent = `Connected to ${channelTitle}. (${statsStr})`;

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
            ? "Dry-run mode: no YouTube/Gemini calls or database writes."
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
    route();
    loadCollectorStatus();
    if ((window.location.hash || "#dashboard") !== "#analytics") loadChannelStatus();

    // History and shell markup still use these narrow compatibility handlers.
    // Creator actions are delegated inside pages/creator.js and expose no globals.
    Object.assign(window, {
      applyTemplate, switchPage, deleteHistoryRun,
      linkVideoPrompt, refreshLinkedVideo, openHistoryRun, closeHistoryDetail,
      saveComparableMetadata, refreshHistoryPerformance,
    });
