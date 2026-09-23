import { defineConfig, devices } from "@playwright/test";

/**
 * Visual and accessibility checks for the React app served by the running
 * Docker backend. These do not start a server: bring the stack up first with
 * `docker compose up -d` from the repository root.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
