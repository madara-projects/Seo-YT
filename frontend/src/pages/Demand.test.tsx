import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { toast } from "sonner";
import DemandPage from "./Demand";

// Produced by the real `analyze_demand` from public results of a saved
// analysis. View counts stay strings, exactly as YouTube returns them.
const EVIDENCE = {
  classification: "emerging_signal",
  reasons: [
    "5 relevant public results were observed in the sampled API result set.",
    "Coverage was observed across 5 independent channels.",
    "Median captured public views across 5 result(s): 20419.",
  ],
  captured_at: "2026-09-24T13:25:13+00:00",
  signals: [
    { name: "sampled_relevant_results", observed: 5, source: "public_observation", limitation: "Sampled API results, not monthly search volume." },
    { name: "recent_publications_90d", observed: 0, source: "public_observation", limitation: "Publication activity does not prove audience demand." },
    { name: "independent_channels", observed: 5, source: "public_observation", limitation: "Channel coverage is observational." },
    { name: "median_captured_views", observed: 20419, source: "public_observation", limitation: "Views at capture time are not search volume or causal evidence." },
    { name: "watchlist_possible_outliers", observed: 0, source: "heuristic", limitation: "Outlier association does not establish causation." },
  ],
  public_results: [
    { video_id: "ZtFnSqTOpwc", title: "She was so sad here it breaks my heart", channel_title: "Brittikitty", published_at: "2024-07-17T22:24:38Z", view_count: "180809850" },
    { video_id: "KhtCgbdlZgI", title: "Syllogism can never be concept", channel_title: "Crack with Jack", published_at: "2025-11-02T10:36:52Z", view_count: "20419" },
  ],
  watchlist_evidence: [],
  personal_evidence: { status: "insufficient_evidence", learning_allowed: false, sample_size: 0, confidence_label: "Collecting evidence", source: "unavailable" },
  limitations: [
    "No official monthly search-volume data is available.",
    "No CPC, market size, guaranteed demand, CTR, views, or growth is inferred.",
  ],
};

const SNAPSHOT = {
  id: 7,
  idea_id: null,
  topic: "painful love quotes",
  language: "english",
  format: "youtube_shorts",
  region: "india",
  audience_context: "",
  classification: "emerging_signal",
  evidence: EVIDENCE,
  captured_at: "2026-09-24T13:25:13+00:00",
};

let snapshots: typeof SNAPSHOT[];
let fetchMock: ReturnType<typeof vi.fn>;
let generateFails = false;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function posts(path: string) {
  return fetchMock.mock.calls.filter(([url, init]) => String(url) === path && init?.method === "POST");
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderPage(route = "/demand") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route
            path="/demand"
            element={
              <>
                <DemandPage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Demand and one other page, with links between them, as in the app. */
function renderWithElsewhere() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/demand"]}>
        <Routes>
          <Route
            path="/demand"
            element={
              <>
                <DemandPage />
                <Link to="/ideas">Go to Ideas</Link>
              </>
            }
          />
          <Route path="/ideas" element={<Link to="/demand">Back to Demand</Link>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Holds the research POST open until the test calls the returned function. */
function holdResearch() {
  const release: Array<() => void> = [];
  const route = fetchMock.getMockImplementation() as (url: string, init?: RequestInit) => Promise<unknown>;
  fetchMock.mockImplementation((url: string, init?: RequestInit) =>
    String(url) === "/api/demand/research" && init?.method === "POST"
      ? new Promise((resolve) => {
          release.push(() => resolve(route(url, init)));
        })
      : route(url, init),
  );
  return () => release.shift()?.();
}

beforeEach(() => {
  snapshots = [SNAPSHOT];
  generateFails = false;
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path === "/api/demand/research?limit=50&offset=0") {
      return json({ research: snapshots, total: snapshots.length });
    }
    if (path === "/api/demand/research" && method === "POST") {
      const body = JSON.parse(String(init?.body));
      const created = { ...SNAPSHOT, id: 8, topic: body.topic, format: body.format, region: body.region };
      snapshots = [created, ...snapshots];
      return json({ status: "researched", research: created }, 201);
    }
    const detail = path.match(/^\/api\/demand\/research\/(\d+)$/);
    if (detail) {
      const found = snapshots.find((item) => item.id === Number(detail[1]));
      return found ? json({ research: found }) : json({ detail: "Demand research snapshot not found." }, 404);
    }
    if (/^\/api\/demand\/research\/\d+\/generate$/.test(path) && method === "POST") {
      return generateFails
        ? json({ error: { message: "Gemini is cooling down.", request_id: "req-9" } }, 503)
        : json({ status: "package_generated", analysis: { history_run_id: 42 } });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("DemandPage", () => {
  it("starts with an honest empty state", async () => {
    snapshots = [];
    renderPage();

    expect(await screen.findByRole("heading", { name: "Demand", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText(/No demand snapshots yet/)).toBeInTheDocument();
    expect(screen.getByText("Choose a snapshot to inspect")).toBeInTheDocument();
  });

  it("asks for a topic before spending any quota", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Research demand" }));

    expect(await screen.findByText("Enter a topic or phrase to research.")).toBeInTheDocument();
    expect(posts("/api/demand/research")).toHaveLength(0);
  });

  it("researches a topic and opens the new snapshot", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Topic or phrase"), "  heartbreak quotes  ");
    await user.click(screen.getByRole("button", { name: "Research demand" }));

    await waitFor(() => expect(posts("/api/demand/research")).toHaveLength(1));
    expect(JSON.parse(String(posts("/api/demand/research")[0]![1]?.body))).toEqual({
      topic: "heartbreak quotes",
      language: "",
      format: "",
      region: "",
      audience_context: "",
    });
    const detail = await screen.findByTestId("demand-detail");
    expect(within(detail).getByRole("heading", { name: "heartbreak quotes" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/demand?snapshot=8"));
  });

  it("shows the evidence behind a linked snapshot", async () => {
    renderPage("/demand?snapshot=7");

    const detail = await screen.findByTestId("demand-detail");
    expect(within(detail).getByRole("heading", { name: "painful love quotes" })).toBeInTheDocument();
    expect(within(detail).getByText(/3 or more sampled results/)).toBeInTheDocument();
    expect(within(detail).getByText(EVIDENCE.reasons[1]!)).toBeInTheDocument();
    expect(within(detail).getByText("Published in the last 90 days")).toBeInTheDocument();
    // String counts from YouTube are formatted like numbers, in the viewer's locale.
    expect(within(detail).getByText((180809850).toLocaleString())).toBeInTheDocument();
    expect(within(detail).getByText("Syllogism can never be concept")).toBeInTheDocument();
    expect(within(detail).getByText(EVIDENCE.limitations[0]!)).toBeInTheDocument();
    expect(within(detail).getByText(/Not enough mature, comparable history/)).toBeInTheDocument();
  });

  it("generates a package and links to it in History", async () => {
    const user = userEvent.setup();
    renderPage("/demand?snapshot=7");

    await user.click(await screen.findByRole("button", { name: "Generate package" }));

    expect(await screen.findByText("Package saved to History as run #42.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in History/ })).toHaveAttribute("href", "/history?run=42");
    expect(posts("/api/demand/research/7/generate")).toHaveLength(1);
  });

  it("reports a generation failure with its request ID", async () => {
    generateFails = true;
    const user = userEvent.setup();
    renderPage("/demand?snapshot=7");

    await user.click(await screen.findByRole("button", { name: "Generate package" }));

    expect(await screen.findByText("Gemini is cooling down.")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-9")).toBeInTheDocument();
  });

  it("pages through snapshots beyond the first fifty", async () => {
    const route = fetchMock.getMockImplementation() as (url: string, init?: RequestInit) => Promise<unknown>;
    fetchMock.mockImplementation((url: string, init?: RequestInit) =>
      String(url).startsWith("/api/demand/research?")
        ? Promise.resolve(json({ research: snapshots, total: 73 }))
        : route(url, init),
    );
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("1–1 of 73")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/demand?offset=50"));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/demand/research?limit=50&offset=50")).toBe(true),
    );
  });

  it("steps back to the last page when the URL's offset is past the end", async () => {
    const route = fetchMock.getMockImplementation() as (url: string, init?: RequestInit) => Promise<unknown>;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const path = String(url);
      if (path === "/api/demand/research?limit=50&offset=500") return Promise.resolve(json({ research: [], total: 73 }));
      if (path === "/api/demand/research?limit=50&offset=50") return Promise.resolve(json({ research: snapshots, total: 73 }));
      return route(url, init);
    });
    renderPage("/demand?offset=500");

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^\/demand\?offset=50$/));
    expect(await screen.findByText("painful love quotes")).toBeInTheDocument();
  });

  it("stays on the page the creator moved to when research finishes", async () => {
    const saved = vi.spyOn(toast, "success");
    const finish = holdResearch();
    const user = userEvent.setup();
    renderWithElsewhere();

    await user.type(await screen.findByLabelText("Topic or phrase"), "heartbreak quotes");
    await user.click(screen.getByRole("button", { name: "Research demand" }));
    await waitFor(() => expect(posts("/api/demand/research")).toHaveLength(1));
    await user.click(screen.getByRole("link", { name: "Go to Ideas" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/ideas"));

    finish();
    // Still announced, but the creator isn't pulled back to /demand?snapshot=8.
    await waitFor(() => expect(saved).toHaveBeenCalledWith("Demand snapshot saved."));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/ideas$/);
    saved.mockRestore();
  });

  it("keeps research in flight across leaving and coming back, so it isn't paid for twice", async () => {
    const finish = holdResearch();
    const user = userEvent.setup();
    renderWithElsewhere();

    await user.type(await screen.findByLabelText("Topic or phrase"), "heartbreak quotes");
    await user.click(screen.getByRole("button", { name: "Research demand" }));
    await user.click(screen.getByRole("link", { name: "Go to Ideas" }));
    await user.click(await screen.findByRole("link", { name: "Back to Demand" }));

    expect(await screen.findByRole("button", { name: /Researching/ })).toBeDisabled();
    expect(posts("/api/demand/research")).toHaveLength(1);
    finish();
    expect(await screen.findByRole("button", { name: "Research demand" })).toBeEnabled();
  });

  it("says how an idea's snapshot is turned into a package", async () => {
    snapshots = [{ ...SNAPSHOT, idea_id: 3 } as unknown as typeof SNAPSHOT];
    renderPage("/demand?snapshot=7");

    expect(await screen.findByText(/This snapshot belongs to an idea/)).toBeInTheDocument();
  });
});
