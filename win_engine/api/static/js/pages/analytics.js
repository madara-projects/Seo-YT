/** Analytics page seam. Rendering remains in app.js until the next extraction step. */
export function mountAnalyticsPage(root = document) {
  const view = root.getElementById("view-analytics");
  if (view) view.dataset.pageModule = "analytics";
}
