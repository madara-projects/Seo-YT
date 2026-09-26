import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { ThemeProvider } from "@/lib/theme";
import SettingsPage from "./Settings";

const SETTINGS = {
  app: { name: "YouTube Win-Engine", version: "0.13.0", environment: "production" },
  database: {
    healthy: true as boolean,
    error: undefined as string | undefined,
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
  // As `SnapshotCollector` reports it before its first run: zero counts, no finish time.
  collector: {
    state: "waiting",
    enabled: true,
    dry_run: true,
    last_finished_at: null as string | null,
    next_run_at: null as string | null,
    last_counts: { links: 0, windows: 0, captured: 0, failed: 0 },
  },
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
    if (path === "/diagnostics" && method === "POST") {
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
    // The live check spends real quota (1 unit), so it must wait for a click.
    expect(calls("POST", "/diagnostics")).toBe(0);

    await user.click(screen.getByRole("button", { name: "Run live check" }));

    expect(await screen.findByText("YouTube reachable")).toBeInTheDocument();
    // POST, so the server applies its cross-site guard and costly-request budget.
    expect(calls("POST", "/diagnostics")).toBe(1);
    expect(calls("GET", "/diagnostics")).toBe(0);
  });

  it("shows the collector's counts only once a check has finished", async () => {
    const { unmount } = renderSettings();

    const panel = (await screen.findByRole("heading", { name: "Snapshot collector", level: 2 })).closest(
      "#settings-collector",
    ) as HTMLElement;
    // The backend's zero counts before the first run are not results.
    expect(await within(panel).findByText("Linked videos due")).toBeInTheDocument();
    expect(within(panel).getAllByText("Not run yet").length).toBeGreaterThanOrEqual(3);
    expect(within(panel).queryByText("0")).not.toBeInTheDocument();
    unmount();

    fetchMock.mockImplementation(async (url: string) =>
      String(url) === "/api/settings/status"
        ? json({
            ...SETTINGS,
            collector: {
              ...SETTINGS.collector,
              state: "healthy/idle",
              last_finished_at: "2026-09-24T08:00:00Z",
              last_counts: { links: 2, windows: 3, captured: 0, failed: 0 },
            },
          })
        : json({}),
    );
    renderSettings();

    const after = (await screen.findByRole("heading", { name: "Snapshot collector", level: 2 })).closest(
      "#settings-collector",
    ) as HTMLElement;
    expect(await within(after).findByText("2")).toBeInTheDocument();
    // A finished run's zero is a real zero.
    expect(within(after).getByText("0 · 0")).toBeInTheDocument();
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

  it("explains why the server could not finish a connection", async () => {
    renderSettings("/settings?youtube=error&reason=missing_scopes");

    expect(await screen.findByText(/Both permissions are needed/)).toBeInTheDocument();
  });

  it("reports a sync that couldn't reach the cloud as a warning, not a success", async () => {
    const warning = vi.spyOn(toast, "warning");
    const success = vi.spyOn(toast, "success");
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url);
      if (path === "/api/cloud-sync/run" && init?.method === "POST") return json({ state: "offline/pending" });
      if (path === "/api/cloud-sync/status") return json(CLOUD);
      if (path === "/api/settings/status") return json(SETTINGS);
      if (path === "/youtube/channel/status") return json(channel);
      return json({});
    });
    const user = userEvent.setup();
    renderSettings();

    await user.click(await screen.findByRole("button", { name: "Sync now" }));

    await waitFor(() => expect(warning).toHaveBeenCalledWith(expect.stringMatching(/couldn't finish/)));
    expect(success).not.toHaveBeenCalled();
    warning.mockRestore();
    success.mockRestore();
  });

  it("shows the database's real state and never a count it couldn't read", async () => {
    Object.assign(SETTINGS.database, { healthy: false, error: "OperationalError", schema_version: null, counts: null });
    try {
      renderSettings();

      expect(await screen.findByText("Error")).toBeInTheDocument();
      expect(screen.getByText("OperationalError")).toBeInTheDocument();
      expect(screen.getByText(/Schema unavailable/)).toBeInTheDocument();
      expect(screen.queryByText(/^v0/)).not.toBeInTheDocument();
    } finally {
      Object.assign(SETTINGS.database, {
        healthy: true,
        error: undefined,
        schema_version: 9,
        counts: { packages: 3, ideas: 0, published_links: 0, performance_snapshots: 0 },
      });
    }
  });

  it("confirms a claimed connection with the server before announcing it", async () => {
    channel = {
      configured: true,
      connected: true,
      channel: { id: "UCfixture00000000000001", title: "Studio Fixture Channel" },
      latest_sync: null,
      setup_message: null,
    };
    renderSettings("/settings?youtube=connected");

    expect(await screen.findByText("YouTube channel connected with read-only access.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^\/settings$/));
  });

  it("does not believe a link that claims a connection the server doesn't have", async () => {
    renderSettings("/settings?youtube=connected");

    expect(await screen.findByText(/no connected channel/)).toBeInTheDocument();
    expect(screen.queryByText("YouTube channel connected with read-only access.")).not.toBeInTheDocument();
  });

  it("never repeats text from the link as the reason", async () => {
    renderSettings("/settings?youtube=error&reason=Your%20account%20was%20suspended");

    expect(
      await screen.findByText("YouTube connection failed. Nothing was changed; try connecting again."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/suspended/)).not.toBeInTheDocument();
  });

  it("moves through the themes with the arrow keys, as one tab stop", async () => {
    const user = userEvent.setup();
    renderSettings();

    const system = await screen.findByRole("radio", { name: "System" });
    expect(system).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("tabindex", "-1");

    system.focus();
    await user.keyboard("{ArrowRight}");
    const light = screen.getByRole("radio", { name: "Light" });
    expect(light).toHaveAttribute("aria-checked", "true");
    expect(light).toHaveFocus();
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
