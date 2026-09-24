import { defineConfig, devices } from "@playwright/test";

/**
 * Visual and accessibility checks for the React app served by the running
 * Docker backend. These do not start a server: bring the stack up first with
 * `docker compose up -d` from the repository root.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // Parallel browsers share one single-process backend, so a first page load
  // (bundle, lazy route chunk, then data) can outlast the default 5s wait on a
  // busy machine. The assertions are unchanged; only the patience is.
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
