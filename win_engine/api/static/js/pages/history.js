/** History page seam. Rendering remains in app.js until the next extraction step. */
export function mountHistoryPage(root = document) {
  const view = root.getElementById("view-history");
  if (view) view.dataset.pageModule = "history";
}
