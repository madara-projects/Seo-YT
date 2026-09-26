import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ChannelPage from "./Channel";

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

const SYNC = {
  channel: {
    id: "UCfixturechannel0000001",
    title: "Studio Fixture Channel",
    subscribers: 18_432,
    video_count: 212,
    real_total_views: 4_829_331,
  },
  period: { start: "2026-08-27", end: "2026-09-23" },
  current_28_days: {
    views: 184_233,
    estimatedMinutesWatched: 51_230,
    averageViewDuration: 17,
    subscribersGained: 912,
    likes: 9_120,
    comments: 812,
  },
  previous_28_days: {
    views: 151_020,
    estimatedMinutesWatched: 48_110,
    averageViewDuration: 19,
    subscribersGained: 1_034,
    likes: 8_800,
    comments: 640,
  },
  recent_videos: {
    rows: [
      { video_id: "aaaaaaaaaa1", title: "Quiet upload", published_at: "2026-09-20T10:00:00Z", views: 1_200, likes: 40, comments: 4 },
      { video_id: "aaaaaaaaaa2", title: "Breakout upload", published_at: "2026-09-10T10:00:00Z", views: 48_210, likes: 2_100, comments: 188 },
      { video_id: "aaaaaaaaaa3", title: "Steady upload", published_at: "2026-09-01T10:00:00Z", views: 9_000, likes: 300, comments: 20 },
    ],
  },
};

let status: Record<string, unknown>;
let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function refreshCalls() {
  return fetchMock.mock.calls.filter(
    ([url, init]) => String(url) === "/youtube/channel/refresh" && init?.method === "POST",
  ).length;
}

function connected(syncedAt: string, data: Record<string, unknown> = SYNC) {
  return {
    configured: true,
    connected: true,
    channel: { id: SYNC.channel.id, title: SYNC.channel.title, connected_at: "2026-09-01T00:00:00Z" },
    latest_sync: { synced_at: syncedAt, data },
    setup_message: null,
  };
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

function renderChannel(queryClient: QueryClient = newClient()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/channel"]}>
        <ChannelPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  status = { configured: true, connected: false, channel: null, latest_sync: null, setup_message: null };
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (path === "/youtube/channel/status") return json(status);
    if (path === "/youtube/channel/refresh" && init?.method === "POST") return json(SYNC);
    if (path === "/api/learning/cohorts") {
      return json({ sample_size: 0, next_threshold: 5, confidence_label: "Collecting evidence", learning_allowed: false });
    }
    if (path === "/api/published-videos") return json({ links: [], total: 0 });
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("ChannelPage", () => {
  it("invites a connection that returns to this page, without spending quota", async () => {
    renderChannel();

    const connect = await screen.findByRole("link", { name: /Connect YouTube channel/ });
    expect(connect).toHaveAttribute("href", "/youtube/channel/connect?return_to=%2Fnext%2Fchannel");
    expect(screen.getByText("Appears after you connect")).toBeInTheDocument();
    expect(refreshCalls()).toBe(0);
  });

  it("explains missing OAuth setup instead of offering a broken connect button", async () => {
    status = { configured: false, connected: false, channel: null, latest_sync: null, setup_message: null };
    renderChannel();

    expect(await screen.findByText("YouTube OAuth is not set up")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Connect YouTube channel/ })).not.toBeInTheDocument();
  });

  it("shows 28-day numbers with their change against the previous period", async () => {
    status = connected(minutesAgo(1));
    renderChannel();

    expect(await screen.findByRole("heading", { name: "Studio Fixture Channel" })).toBeInTheDocument();

    const views = document.querySelector('[data-stat="Views (28 days)"]') as HTMLElement;
    // Grouping follows the viewer's locale, as it does everywhere else in the app.
    expect(within(views).getByText((184_233).toLocaleString())).toBeInTheDocument();
    expect(within(views).getByText("+22.0%")).toBeInTheDocument();

    const watch = document.querySelector('[data-stat="Watch time (28 days)"]') as HTMLElement;
    expect(within(watch).getByText("853.8 hrs")).toBeInTheDocument();

    const duration = document.querySelector('[data-stat="Avg view duration (28 days)"]') as HTMLElement;
    expect(within(duration).getByText("0:17")).toBeInTheDocument();
    expect(within(duration).getByText("−10.5%")).toBeInTheDocument();

    // A fresh sync is not refreshed again.
    expect(refreshCalls()).toBe(0);
  });

  it("sorts uploads by views on request", async () => {
    status = connected(minutesAgo(1));
    const user = userEvent.setup();
    renderChannel();

    const table = await screen.findByRole("table");
    const firstTitle = () => within(within(table).getAllByRole("row")[1]!).getByText(/upload$/);
    expect(firstTitle()).toHaveTextContent("Quiet upload");

    await user.click(screen.getByRole("tab", { name: "Most viewed" }));

    expect(firstTitle()).toHaveTextContent("Breakout upload");
  });

  it("treats an empty Analytics window as unavailable rather than zero", async () => {
    status = connected(minutesAgo(1), { ...SYNC, current_28_days: {}, previous_28_days: {} });
    renderChannel();

    expect(await screen.findByText(/YouTube Analytics returned no totals/)).toBeInTheDocument();
    expect(document.querySelector('[data-stat="Views (28 days)"]')).toBeNull();
    // Data API counts are still current and still shown.
    expect(screen.getByText("18.4K")).toBeInTheDocument();
  });

  it("says which parts of a sync failed instead of showing them as empty", async () => {
    status = connected(minutesAgo(1), {
      ...SYNC,
      channel: { ...SYNC.channel, subscribers: null },
      current_28_days: {},
      previous_28_days: {},
      recent_videos: { rows: [] },
      partial_failures: ["uploads", "analytics"],
    });
    renderChannel();

    expect(await screen.findByText(/YouTube Analytics could not be read during the last sync/)).toBeInTheDocument();
    expect(screen.getAllByText(/Uploads could not be read from YouTube/)).toHaveLength(2);
    expect(screen.queryByText(/No uploads were returned/)).not.toBeInTheDocument();
    // A hidden subscriber count is unavailable, not zero.
    const banner = screen.getByRole("heading", { name: "Studio Fixture Channel" }).closest("section") as HTMLElement;
    expect(within(banner).getByText("Unavailable")).toBeInTheDocument();
  });

  it("never starts a second refresh while one is already running", async () => {
    status = connected(minutesAgo(120));
    const session = newClient();
    // A refresh started from Settings that hasn't answered yet: both pages share its key.
    void session
      .getMutationCache()
      .build(session, { mutationKey: ["channel-refresh"], mutationFn: () => new Promise(() => {}) })
      .execute(undefined);
    renderChannel(session);

    await screen.findByRole("heading", { name: "Studio Fixture Channel" });
    expect(refreshCalls()).toBe(0);
    expect(screen.getAllByRole("button", { name: "Refreshing…" })[0]).toBeDisabled();
  });

  it("says when learning has reached its top level instead of an unavailable next step", async () => {
    status = connected(minutesAgo(1));
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url);
      if (path === "/youtube/channel/status") return json(status);
      if (path === "/youtube/channel/refresh" && init?.method === "POST") return json(SYNC);
      if (path === "/api/learning/cohorts") {
        return json({ sample_size: 40, next_threshold: null, confidence_label: "Strong evidence", learning_allowed: true });
      }
      if (path === "/api/published-videos") return json({ links: [], total: 0 });
      return json({});
    });
    renderChannel();

    expect(await screen.findByText("Top evidence level reached")).toBeInTheDocument();
    expect(screen.queryByText(/Unavailable\s*needed/)).not.toBeInTheDocument();
  });

  it("refreshes a stale sync once per session", async () => {
    status = connected(minutesAgo(120));
    const session = newClient();
    const first = renderChannel(session);

    await waitFor(() => expect(refreshCalls()).toBe(1));

    first.unmount();
    renderChannel(session);
    await screen.findByRole("heading", { name: "Studio Fixture Channel" });
    expect(refreshCalls()).toBe(1);
  });
});
