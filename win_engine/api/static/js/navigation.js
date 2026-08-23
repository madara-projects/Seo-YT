/** Hash-navigation metadata shared by the app shell and page modules. */
export const pages = {
  dashboard: { title: "Dashboard Overview", sub: "Welcome back! Track performance and launch new analyses.", navId: "nav-dashboard", viewId: "view-dashboard" },
  creator: { title: "SEO Creator Studio", sub: "Build, compare, and review one selected-language SEO package before manual publishing.", navId: "nav-creator", viewId: "view-creator" },
  ideas: { title: "Ideas Workspace", sub: "Save, research, package, and trace original video ideas without guessed demand data.", navId: "nav-ideas", viewId: "view-ideas" },
  demand: { title: "Honest Topic-Demand Explorer", sub: "Inspect dated public, watchlist, and eligible personal evidence without invented search volume.", navId: "nav-demand", viewId: "view-demand" },
  watchlist: { title: "Public Research Watchlist", sub: "Observe saved public channels and videos with immutable snapshots and local outlier analysis.", navId: "nav-watchlist", viewId: "view-watchlist" },
  audits: { title: "Published Video Audits", sub: "Separate generated intent, creator selection, published reality, and evidence without causal claims.", navId: "nav-audits", viewId: "view-audits" },
  experiments: { title: "Experiment / Comparison Center", sub: "Record explicit hypotheses and compare controlled or observational groups with honest evidence states.", navId: "nav-experiments", viewId: "view-experiments" },
  analytics: { title: "Channel Analytics & History", sub: "YouTube channel metrics, current uploads, and evidence-based learning history.", navId: "nav-analytics", viewId: "view-analytics" },
  history: { title: "Saved SEO Packages", sub: "Open any past package to reuse its complete upload-ready content.", navId: "nav-history", viewId: "view-history" },
  settings: { title: "Settings & Integrations", sub: "Inspect YouTube OAuth, AI configuration, and live API diagnostics.", navId: "nav-settings", viewId: "view-settings" },
};

export function normalizePageKey(hash = "") {
  const key = String(hash || "").replace(/^#/, "");
  return pages[key] ? key : "dashboard";
}
