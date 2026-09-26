import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  // The production bundle is served by FastAPI from `win_engine/api/static/app/`,
  // so every built asset is requested under `/app-assets/`, apart from the page
  // paths the app itself uses. The dev server has no FastAPI in front of it, so
  // it serves the app at the root, where the router expects it.
  base: command === "build" ? "/app-assets/" : "/",
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    outDir: path.resolve(__dirname, "../win_engine/api/static/app"),
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          forms: ["react-hook-form", "zod", "@hookform/resolvers"],
        },
      },
    },
  },
  server: {
    port: 5173,
    // Dev server talks to the Dockerised backend. Same-origin in production,
    // proxied in development, so the API client never needs a base URL.
    proxy: Object.fromEntries(
      [
        "/analyze",
        "/api",
        "/health",
        "/meta",
        "/diagnostics",
        "/ready",
        "/youtube",
        "/oauth",
      ].map((route) => [route, { target: "http://127.0.0.1:8000", changeOrigin: true }]),
    ),
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // `e2e/` holds Playwright specs, which share the *.spec.ts suffix but
    // need a real browser. Vitest would otherwise try to collect them.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e"],
    // The Dashboard tree pulls in Recharts; under parallel file execution its
    // first render can exceed the 5s default on a loaded machine.
    testTimeout: 20_000,
  },
}));
