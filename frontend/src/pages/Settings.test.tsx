import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import SettingsPage from "./Settings";

const SETTINGS = {
  app: { name: "YouTube Win-Engine", version: "0.13.0", environment: "production" },
  database: {
    healthy: true,
    name: "win_engine.db",
    schema_version: 9,
    size_bytes: 839_680,
    counts: { packages: 3, ideas: 0, published_links: 0, performance_snapshots: 0 },
    last_backup_at: null,
  },
  providers: {
    gemini: {
      configured: true,
      model: "gemini-3.5-flash-lite",
      provider_health: { transient_failure_count: 0, cooldown_active: false, cooldown_remaining_seconds: 0 },
    },
    youtube_data_api: { configured: true, key_count: 1 },
    local_fallback: { available: true },
    redis: { configured: true },
  },
  collector: { state: "dry-run", enabled: true, dry_run: true, last_counts: { links: 0, windows: 0 } },
};

const CLOUD = {
  state: "offline/pending",
  enabled: true,
  configured: true,
  device_id: "test-device",
  last_finished_at: "2026-09-24T08:12:22Z",
  next_run_at: "2026-09-24T08:13:22Z",
  last_error: "RuntimeError",
  last_counts: { pushed: 0, pulled: 0, failed: 1 },
  local_packages: 3,
  synced_packages: 0,
  pending_uploads: 3,
  conflicts_detected: 0,
  remote_packages: null,
};

let channel: Record<string, unknown>;
let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function calls(method: string, path: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => String(url) === path && (init?.method ?? "GET") === method,
  ).length;
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderSettings(route = "/settings") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route
              path="/settings"
              element={
                <>
                  <SettingsPage />
                  <LocationProbe />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  channel = { configured: true, connected: false, channel: null, latest_sync: null, setup_message: null };
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path === "/youtube/channel/status") return json(channel);
    if (path === "/api/settings/status") return json(SETTINGS);
    if (path === "/api/cloud-sync/status") return json(CLOUD);
    if (path === "/health") return json({ status: "ok", version: "0.13.0", uptime_seconds: 3720, cache_ok: true });
    if (path === "/api/cloud-sync/run" && method === "POST") return json({ state: "healthy/idle" });
    if (path === "/youtube/channel/disconnect" && method === "POST") return json({ disconnected: true });
    if (path === "/diagnostics") {
      return json({ youtube: { status: "ok", available_key_count: 1, active_key_index: 1, quota_date: "2026-09-24" } });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});

describe("SettingsPage", () => {
  it("shows every section and never runs the live YouTube check on its own", async () => {
    const user = userEvent.setup();
    renderSettings();

    expect(await screen.findByRole("heading", { name: "Settings", level: 1 })).toBeInTheDocument();
    for (const name of [
      "YouTube channel",
      "Cloud sync",
      "AI & data providers",
      "Local database",
      "Snapshot collector",
      "Appearance",
      "About",
    ]) {
      expect(screen.getByRole("heading", { name, level: 2 })).toBeInTheDocument();
    }
    expect(await screen.findByText("gemini-3.5-flash-lite")).toBeInTheDocument();
    // The live check spends ~100 quota units, so it must wait for a click.
    expect(calls("GET", "/diagnostics")).toBe(0);

    await user.click(screen.getByRole("button", { name: "Run live check" }));

    expect(await screen.findByText("YouTube reachable")).toBeInTheDocument();
    expect(calls("GET", "/diagnostics")).toBe(1);
  });

  it("offers to connect a channel and return to Settings afterwards", async () => {
    renderSettings();

    const connect = await screen.findByRole("link", { name: /Connect YouTube channel/ });
    expect(connect).toHaveAttribute(
      "href",
      "/youtube/channel/connect?return_to=%2Fnext%2Fsettings",
    );
    expect(screen.getByText("youtube.readonly")).toBeInTheDocument();
    expect(screen.getByText("yt-analytics.readonly")).toBeInTheDocument();
  });

  it("names the setup variables when OAuth is not configured", async () => {
    channel = {
      configured: false,
      connected: false,
      channel: null,
      latest_sync: null,
      setup_message: "Add YouTube OAuth client credentials and an encryption key to .env to connect your channel.",
    };
    renderSettings();

    expect(await screen.findByText("YouTube OAuth is not set up")).toBeInTheDocument();
    expect(screen.getByText("WIN_ENGINE_YOUTUBE_OAUTH_CLIENT_ID")).toBeInTheDocument();
    expect(screen.getByText("WIN_ENGINE_OAUTH_TOKEN_ENCRYPTION_KEY")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Connect YouTube channel/ })).not.toBeInTheDocument();
  });

  it("asks for confirmation before disconnecting, and only then calls the API", async () => {
    channel = {
      configured: true,
      connected: true,
      channel: { id: "UCfixture00000000000001", title: "Studio Fixture Channel", connected_at: "2026-09-01T00:00:00Z" },
      latest_sync: { synced_at: "2026-09-24T08:00:00Z", data: {} },
      setup_message: null,
    };
    const user = userEvent.setup();
    renderSettings();

    await user.click(await screen.findByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Saved packages, video links and past syncs are kept/)).toBeInTheDocument();
    expect(calls("POST", "/youtube/channel/disconnect")).toBe(0);

    await user.click(within(dialog).getByRole("button", { name: "Disconnect" }));

    await waitFor(() => expect(calls("POST", "/youtube/channel/disconnect")).toBe(1));
  });

  it("reports a failed cloud attempt honestly and syncs on request", async () => {
    const user = userEvent.setup();
    renderSettings();

    // A driver error arrives as a bare class name; its message stays on the server.
    expect(await screen.findByText(/The last attempt failed/)).toBeInTheDocument();
    expect(screen.getByText("RuntimeError")).toBeInTheDocument();
    expect(screen.getByText("Offline · changes queued")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sync now" }));

    await waitFor(() => expect(calls("POST", "/api/cloud-sync/run")).toBe(1));
  });

  it("shows a configuration fault in plain words and explains the backoff", async () => {
    Object.assign(CLOUD, {
      last_error:
        "CA certificate not found at /runtime/secrets/aiven-ca.pem inside the container; check WIN_ENGINE_CLOUD_SYNC_SSL_CA_PATH against the volume mount.",
      consecutive_failures: 4,
    });
    try {
      renderSettings();

      expect(await screen.findByText(/CA certificate not found at \/runtime\/secrets/)).toBeInTheDocument();
      expect(screen.getByText(/4 attempts in a row have failed/)).toBeInTheDocument();
    } finally {
      Object.assign(CLOUD, { last_error: "RuntimeError", consecutive_failures: undefined });
    }
  });

  it("announces an OAuth return once and removes it from the URL", async () => {
    renderSettings("/settings?youtube=error&reason=access_denied");

    expect(
      await screen.findByText(
        "Access was declined on the Google consent screen, so nothing was connected.",
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^\/settings$/));
  });

  it("switches the theme from the appearance picker", async () => {
    const user = userEvent.setup();
    renderSettings();

    const dark = await screen.findByRole("radio", { name: "Dark" });
    await user.click(dark);

    expect(dark).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await user.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
