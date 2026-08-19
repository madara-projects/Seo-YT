/** Hash-navigation metadata shared by the app shell and page modules. */
export const pages = {
  dashboard: { title: "Dashboard Overview", sub: "Welcome back! Track performance and launch new analyses.", navId: "nav-dashboard", viewId: "view-dashboard" },
  creator: { title: "SEO Creator Studio", sub: "Build, compare, and review one selected-language SEO package before manual publishing.", navId: "nav-creator", viewId: "view-creator" },
  analytics: { title: "Channel Analytics &amp; History", sub: "YouTube channel metrics, current uploads, and evidence-based learning history.", navId: "nav-analytics", viewId: "view-analytics" },
  history: { title: "Saved SEO Packages", sub: "Open any past package to reuse its complete upload-ready content.", navId: "nav-history", viewId: "view-history" },
  settings: { title: "Settings &amp; Integrations", sub: "Inspect YouTube OAuth, AI configuration, and live API diagnostics.", navId: "nav-settings", viewId: "view-settings" },
};

export function normalizePageKey(hash = "") {
  const key = String(hash || "").replace(/^#/, "");
  return pages[key] ? key : "dashboard";
}
