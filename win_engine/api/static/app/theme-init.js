// Applies the stored theme before first paint so a dark-mode reload never
// flashes a white screen. A file rather than an inline script, so the
// server's Content Security Policy can forbid inline scripts altogether.
// Keep the storage key in step with STORAGE_KEY in src/lib/theme.tsx.
try {
  var stored = localStorage.getItem("win-engine-theme");
  var dark =
    stored === "dark" ||
    ((!stored || stored === "system") &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (dark) document.documentElement.classList.add("dark");
} catch (e) {}
