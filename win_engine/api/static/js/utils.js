/** Small, DOM-safe helpers shared by page modules. */
export const $ = (id) => document.getElementById(id);
// `??` keeps 0 and false; the apostrophe is escaped so values are safe in any quoted attribute.
export const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
// Numbers are formatted; anything else (a count that arrived as text) is escaped for innerHTML.
export const num = (v) => typeof v === "number" ? v.toLocaleString() : (v === null || v === undefined || v === "" ? "Not available" : esc(v));
export const arr = (v) => Array.isArray(v) ? v : [];

export function chip(text, tone) {
  const cls = tone === "ok" ? "chip-ok" : tone === "warn" ? "chip-warn" : tone === "bad" ? "chip-bad" : tone === "accent" ? "chip-accent" : tone === "cyan" ? "chip-cyan" : "";
  return `<span class="chip ${cls}">${esc(text)}</span>`;
}
