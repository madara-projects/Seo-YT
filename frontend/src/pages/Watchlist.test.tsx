import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import WatchlistPage from "./Watchlist";

// Shaped like `IntelligenceStore.channel` / `video` output.
const CHANNEL = {
  id: 3,
  channel_id: "UCzU9GK79bxzBfBYrc_D9jjg",
  title: "Kavithai Corner",
  subscriber_count: 48200,
  video_count: 312,
  notes: "Tamil quote Shorts; strong hooks.",
  state: "active",
  source: "public_observation",
  last_researched_at: "2026-09-24T09:00:00+00:00",
  created_at: "2026-09-20T09:00:00+00:00",
  updated_at: "2026-09-24T09:00:00+00:00",
  snapshots: [
    { id: 11, captured_at: "2026-09-24T09:00:00+00:00", subscriber_count: 48200, video_count: 312, view_count: 9120000, source: "public_observation" },
  ],
};

const OUTLIER_VIDEO = {
  id: 21,
  video_id: "ZtFnSqTOpwc",
  watchlist_channel_id: 3,
  channel_id: CHANNEL.channel_id,
  channel_title: "Kavithai Corner",
  title: "Silence is the loudest answer",
  published_at: "2026-09-19T14:03:11Z",
  duration_seconds: 21,
  language: "ta",
  format: "youtube_shorts",
  notes: "",
  state: "active",
  last_researched_at: "2026-09-24T09:00:00+00:00",
  created_at: "2026-09-24T09:00:00+00:00",
  snapshots: [
    { id: 31, captured_at: "2026-09-24T09:00:00+00:00", view_count: 184233, like_count: 9100, comment_count: 212 },
    { id: 30, captured_at: "2026-09-22T09:00:00+00:00", view_count: 120450, like_count: 6400, comment_count: 150 },
  ],
  latest_snapshot: { id: 31, captured_at: "2026-09-24T09:00:00+00:00", view_count: 184233, like_count: 9100, comment_count: 212 },
  outlier: {
    id: 5,
    analyzed_at: "2026-09-24T09:05:00+00:00",
    status: "possible_outlier",
    observed_views: 184233,
    baseline_median_views: 41250,
    relative_multiplier: 4.47,
    sample_size: 6,
    explanation: "Observed views are 4.47x the median of 6 comparable recent videos from this channel. This is an observational outlier signal, not a viral prediction.",
    provenance: "heuristic_public_observation",
  },
};

type Video = typeof OUTLIER_VIDEO;

let channels: (typeof CHANNEL)[];
let videos: Video[];
let fetchMock: ReturnType<typeof vi.fn>;
let refreshFails = false;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function calls(method: string, pattern: RegExp | string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === method &&
      (typeof pattern === "string" ? String(url) === pattern : pattern.test(String(url))),
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderPage(route = "/watchlist") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route
            path="/watchlist"
            element={
              <>
                <WatchlistPage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  channels = [structuredClone(CHANNEL)];
  videos = [structuredClone(OUTLIER_VIDEO)];
  refreshFails = false;
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const [path = "", search = ""] = String(url).split("?");
    const params = new URLSearchParams(search);
    const method = init?.method ?? "GET";
    const state = params.get("state");
    if (path === "/api/watchlist/channels" && method === "GET") {
      const rows = channels.filter((item) => !state || item.state === state);
      return json({ channels: rows, total: rows.length });
    }
    if (path === "/api/watchlist/videos" && method === "GET") {
      const q = (params.get("q") ?? "").toLowerCase();
      const rows = videos.filter(
        (item) => (!state || item.state === state) && (!q || item.title.toLowerCase().includes(q)),
      );
      return json({ videos: rows, total: rows.length });
    }
    if (path === "/api/watchlist/videos" && method === "POST") {
      const body = JSON.parse(String(init?.body));
      const created = {
        ...structuredClone(OUTLIER_VIDEO),
        id: 22,
        video_id: body.video_id,
        title: "Letters I never sent",
        watchlist_channel_id: null,
        snapshots: [],
        latest_snapshot: null,
        outlier: null,
        last_researched_at: null,
      } as unknown as Video;
      videos = [created, ...videos];
      return json({ status: "created", video: created }, 201);
    }
    const item = path.match(/^\/api\/watchlist\/(channels|videos)\/(\d+)(\/[a-z-]+)?$/);
    if (item) {
      const [, kind, id, action] = item;
      const record =
        kind === "channels" ? channels.find((c) => c.id === Number(id)) : videos.find((v) => v.id === Number(id));
      if (!record) return json({ detail: "Watched item not found." }, 404);
      const key = kind === "channels" ? "channel" : "video";
      if (!action && method === "GET") return json({ [key]: record });
      if (!action && method === "PATCH") {
        Object.assign(record, JSON.parse(String(init?.body)));
        return json({ status: "updated", [key]: record });
      }
      if (action === "/research") {
        return refreshFails
          ? json({ detail: "Public video research is unavailable; no snapshot was created." }, 400)
          : json({ status: "researched", [key]: record, observed_videos: 20 });
      }
      if (action === "/analyze-outlier") {
        return json({ status: "analyzed", analysis: OUTLIER_VIDEO.outlier, video: record });
      }
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("WatchlistPage", () => {
  it("starts with honest empty lists", async () => {
    channels = [];
    videos = [];
    renderPage();

    expect(await screen.findByText("You aren't watching any videos yet. Add one above.")).toBeInTheDocument();
    expect(screen.getByText("Choose a channel or video")).toBeInTheDocument();
  });

  it("adds a video from a link and opens it", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Video ID or link"), "https://youtu.be/z4HKMfQ3nJc?t=3");
    await user.click(screen.getByRole("button", { name: "Add video" }));

    await waitFor(() => expect(calls("POST", "/api/watchlist/videos")).toHaveLength(1));
    expect(JSON.parse(String(calls("POST", "/api/watchlist/videos")[0]![1]?.body))).toEqual({
      video_id: "z4HKMfQ3nJc",
      notes: "",
    });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/watchlist?video=22"));
    const detail = await screen.findByTestId("watch-detail");
    expect(within(detail).getByRole("heading", { name: "Letters I never sent" })).toBeInTheDocument();
    expect(within(detail).getByText("No snapshot yet. Refresh to capture its public counts.")).toBeInTheDocument();
  });

  it("explains that a handle can't be looked up, without spending quota", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Channel ID or link"), "@kavithaicorner");
    await user.click(screen.getByRole("button", { name: "Add channel" }));

    expect(await screen.findByText(/Handles can't be looked up/)).toBeInTheDocument();
    expect(calls("POST", "/api/watchlist/channels")).toHaveLength(0);
  });

  it("shows a video's snapshots and outlier check", async () => {
    const user = userEvent.setup();
    renderPage("/watchlist?video=21");

    const detail = await screen.findByTestId("watch-detail");
    expect(within(detail).getByRole("heading", { name: OUTLIER_VIDEO.title })).toBeInTheDocument();
    expect(within(detail).getByText("Possible outlier")).toBeInTheDocument();
    expect(within(detail).getByText("4.5×")).toBeInTheDocument();
    expect(within(detail).getByText(/4\.47x the median of 6 comparable recent videos/)).toBeInTheDocument();
    expect(within(detail).getByText("Tamil")).toBeInTheDocument();
    expect(within(detail).getByText("Dated snapshots (2)")).toBeInTheDocument();
    // Counts use the viewer's locale, like everywhere else.
    expect(
      within(detail).getByText(
        `${(184233).toLocaleString()} views · ${(9100).toLocaleString()} likes · 212 comments`,
      ),
    ).toBeInTheDocument();

    await user.click(within(detail).getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(calls("POST", "/api/watchlist/videos/21/analyze-outlier")).toHaveLength(1));
  });

  it("opens a channel's watched upload from the channel", async () => {
    const user = userEvent.setup();
    renderPage("/watchlist?channel=3");

    const detail = await screen.findByTestId("watch-detail");
    expect(within(detail).getByRole("heading", { name: "Kavithai Corner" })).toBeInTheDocument();
    expect(within(detail).getByText("Tamil quote Shorts; strong hooks.")).toBeInTheDocument();
    expect(within(detail).getByText(/about 100 YouTube quota units/)).toBeInTheDocument();

    await user.click(await within(detail).findByRole("button", { name: /Silence is the loudest answer/ }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/watchlist?video=21"));
    expect(
      await within(screen.getByTestId("watch-detail")).findByRole("heading", { name: OUTLIER_VIDEO.title }),
    ).toBeInTheDocument();
    // The list follows the open record onto the Videos tab.
    expect(screen.getByRole("tab", { name: /Videos/ })).toHaveAttribute("aria-selected", "true");
  });

  it("archives a video", async () => {
    const user = userEvent.setup();
    renderPage("/watchlist?video=21");

    await user.click(await screen.findByRole("button", { name: "Archive" }));

    await waitFor(() => expect(calls("PATCH", "/api/watchlist/videos/21")).toHaveLength(1));
    expect(JSON.parse(String(calls("PATCH", "/api/watchlist/videos/21")[0]![1]?.body))).toEqual({ state: "archived" });
    expect(await screen.findByRole("button", { name: "Restore" })).toBeInTheDocument();
  });

  it("reports a failed refresh", async () => {
    refreshFails = true;
    const user = userEvent.setup();
    renderPage("/watchlist?video=21");

    await user.click(await screen.findByRole("button", { name: "Refresh snapshot" }));

    expect(await screen.findByText("Public video research is unavailable; no snapshot was created.")).toBeInTheDocument();
  });

  it("searches watched videos once typing pauses", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Search watched videos"), "silence");

    await waitFor(() => expect(calls("GET", "/api/watchlist/videos?state=active&q=silence")).toHaveLength(1));
    // One request for the pause, not one per keystroke.
    expect(calls("GET", /\/api\/watchlist\/videos\?state=active&q=/)).toHaveLength(1);
  });
});
