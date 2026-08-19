/** Small, DOM-safe helpers shared by page modules. */
export const $ = (id) => document.getElementById(id);
export const esc = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
export const num = (v) => typeof v === "number" ? v.toLocaleString() : (v === null || v === undefined || v === "" ? "Not available" : v);
export const arr = (v) => Array.isArray(v) ? v : [];

export function meter(val, max, tone) {
  const safeVal = Number(val);
  const safeMax = Number(max) || 1;
  const pct = Number.isFinite(safeVal) ? Math.max(0, Math.min(100, safeVal / safeMax * 100)) : 0;
  return `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>`;
}

export function chip(text, tone) {
  const cls = tone === "ok" ? "chip-ok" : tone === "warn" ? "chip-warn" : tone === "bad" ? "chip-bad" : tone === "accent" ? "chip-accent" : "";
  return `<span class="chip ${cls}">${esc(text)}</span>`;
}
