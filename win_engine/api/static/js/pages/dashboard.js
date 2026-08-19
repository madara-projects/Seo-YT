/** Dashboard page seam. Rendering remains in app.js until the next extraction step. */
export function mountDashboardPage(root = document) {
  const view = root.getElementById("view-dashboard");
  if (view) view.dataset.pageModule = "dashboard";
}
