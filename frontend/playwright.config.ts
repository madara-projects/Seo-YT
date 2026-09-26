import { defineConfig, devices } from "@playwright/test";

/**
 * Browser checks for the React app served by the running Docker backend:
 * console errors, layout at three widths, and the flows unit tests can't
 * reach. These do not start a server: bring the stack up first with
 * `docker compose up -d` from the repository root. Every spec blocks writes
 * to the server (see `blockWrites` in e2e/helpers.ts).
 */
export default defineConfig({
  testDir: "./e2e",
  // One browser at a time. The backend allows each client 60 requests a
  // minute per route, and parallel workers are all the same client: together
  // they used up a route's budget and pages rendered their error state.
  workers: 1,
  // A first page load (bundle, lazy route chunk, then data) can outlast the
  // default 5s wait on a busy machine. The assertions are unchanged; only the
  // patience is.
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
