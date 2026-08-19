/** Settings page seam. Rendering remains in app.js until the next extraction step. */
export function mountSettingsPage(root = document) {
  const view = root.getElementById("view-settings");
  if (view) view.dataset.pageModule = "settings";
}
