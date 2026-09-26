import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import IdeasPage from "./Ideas";

// Shaped like `build_idea_evidence` output, with YouTube's string view counts.
const EVIDENCE = {
  captured_at: "2026-09-21T10:00:00+00:00",
  source: "approved_youtube_data_api_research",
  opportunity_explanation:
    "Observed 2 relevant public YouTube API result(s) across 3 approved research query angle(s); 1 carried a possible-outlier signal. These are dated public observations, not monthly search volume or predicted demand.",
  signals: { relevant_result_count: 2, research_query_count: 3, possible_outlier_count: 1, publication_dates: [] },
  personal_evidence: {
    status: "insufficient_evidence",
    learning_allowed: false,
    sample_size: 0,
    confidence_label: "Collecting evidence",
    snapshot_window: "24h",
    message: "Not enough personal evidence.",
  },
  youtube_results: [
    { video_id: "ZtFnSqTOpwc", title: "Silence speaks louder", channel_title: "Quiet Words", published_at: "2026-09-01T08:00:00Z", view_count: "5400" },
    { video_id: "KhtCgbdlZgI", title: "When they stop talking", channel_title: "Tamil Feels", published_at: "2026-08-12T08:00:00Z", view_count: "91000" },
  ],
};

const IDEA = {
  id: 7,
  topic: "Why silence hurts more than words",
  status: "scripted",
  notes: "Open on the quiet room.",
  format: "youtube_shorts",
  language: "tamil",
  region: "in",
  visual_or_background: "Rain on a window",
  on_screen_text: "Silence says everything",
  target_duration_seconds: 45,
  emotion_or_intent: "Quiet heartbreak",
  search_angle: "silence quotes tamil",
  browse_angle: "",
  audience_angle: "Viewers of the heartbreak series",
  analysis_run_id: null as number | null,
  published_video_link_id: null as number | null,
  created_at: "2026-09-20T10:00:00+00:00",
  updated_at: "2026-09-21T10:00:00+00:00",
  research_snapshots: [{ id: 3, captured_at: EVIDENCE.captured_at, evidence: EVIDENCE }],
  latest_research: { id: 3, captured_at: EVIDENCE.captured_at, evidence: EVIDENCE } as unknown,
  research_is_stale: false,
  latest_demand_research: { id: 12, classification: "active_topic", captured_at: "2026-09-22T10:00:00+00:00", stale: false } as unknown,
};

type IdeaRecord = typeof IDEA;

let ideas: IdeaRecord[];
let listTotal: number | null;
let fetchMock: ReturnType<typeof vi.fn>;
let researchFails = false;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function summary(idea: IdeaRecord) {
  return {
    id: idea.id,
    topic: idea.topic,
    status: idea.status,
    format: idea.format,
    language: idea.language,
    region: idea.region,
    created_at: idea.created_at,
    analysis_run_id: idea.analysis_run_id,
    published_video_link_id: idea.published_video_link_id,
    last_researched_at: idea.latest_research ? EVIDENCE.captured_at : null,
  };
}

function calls(method: string, path: string) {
  return fetchMock.mock.calls.filter(([url, init]) => String(url) === path && (init?.method ?? "GET") === method);
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderPage(route = "/ideas") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route
            path="/ideas"
            element={
              <>
                <IdeasPage />
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
  ideas = [structuredClone(IDEA)];
  listTotal = null;
  researchFails = false;
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    const list = path.match(/^\/api\/ideas\?(.*)$/);
    if (list && method === "GET") {
      const query = new URLSearchParams(list[1]);
      const status = query.get("status");
      const rows = ideas.filter((idea) => !status || idea.status === status).map(summary);
      return json({ ideas: rows, total: listTotal ?? rows.length, limit: 20, offset: Number(query.get("offset")) });
    }
    if (path === "/api/ideas" && method === "POST") {
      const body = JSON.parse(String(init?.body));
      const created = {
        ...structuredClone(IDEA),
        ...body,
        id: 8,
        research_snapshots: [],
        latest_research: null,
        latest_demand_research: null,
      };
      ideas = [created, ...ideas];
      return json({ status: "created", idea: created }, 201);
    }
    const detail = path.match(/^\/api\/ideas\/(\d+)(\/[a-z-]+)?$/);
    if (detail) {
      const idea = ideas.find((item) => item.id === Number(detail[1]));
      if (!idea) return json({ detail: "Idea not found." }, 404);
      const action = detail[2];
      if (!action && method === "GET") return json({ idea });
      if (!action && method === "PATCH") {
        Object.assign(idea, JSON.parse(String(init?.body)));
        return json({ status: "updated", idea });
      }
      if (action === "/research") {
        return researchFails
          ? json({ error: { message: "YouTube quota is exhausted for today.", request_id: "req-3" } }, 503)
          : json({ status: "researched", idea });
      }
      if (action === "/generate") {
        Object.assign(idea, { status: "package_generated", analysis_run_id: 42 });
        return json({ status: "package_generated", idea, analysis: { history_run_id: 42 } });
      }
      if (action === "/demand-research") {
        return json({ status: "researched", research: { id: 13, idea_id: idea.id, topic: idea.topic, classification: "emerging_signal" } }, 201);
      }
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("IdeasPage", () => {
  it("invites a first idea when the backlog is empty", async () => {
    ideas = [];
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Start your backlog")).toBeInTheDocument();
    expect(screen.getByText(/No ideas yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add your first idea" }));
    expect(await screen.findByRole("dialog", { name: "Add an original idea" })).toBeInTheDocument();
  });

  it("asks for a topic before saving anything", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "New idea" }));
    const form = await screen.findByTestId("idea-form");
    await user.click(within(form).getByRole("button", { name: "Save idea" }));

    expect(await within(form).findByText("Enter what the video is about.")).toBeInTheDocument();
    expect(calls("POST", "/api/ideas")).toHaveLength(0);
  });

  it("saves a new idea and opens it", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "New idea" }));
    const form = await screen.findByTestId("idea-form");
    await user.type(within(form).getByLabelText("Topic"), "  Letters I never sent  ");
    await user.type(within(form).getByLabelText(/Target duration/), "45");
    await user.type(within(form).getByLabelText("Search angle"), "unsent letters");
    await user.click(within(form).getByRole("button", { name: "Save idea" }));

    await waitFor(() => expect(calls("POST", "/api/ideas")).toHaveLength(1));
    expect(JSON.parse(String(calls("POST", "/api/ideas")[0]![1]?.body))).toEqual({
      topic: "Letters I never sent",
      notes: "",
      format: "youtube_shorts",
      language: "english",
      region: "global",
      visual_or_background: "",
      on_screen_text: "",
      target_duration_seconds: 45,
      emotion_or_intent: "",
      search_angle: "unsent letters",
      browse_angle: "",
      audience_angle: "",
      status: "idea",
    });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/ideas?idea=8"));
    await waitFor(() => expect(screen.queryByTestId("idea-form")).not.toBeInTheDocument());
    const detail = await screen.findByTestId("idea-detail");
    expect(within(detail).getByRole("heading", { name: "Letters I never sent" })).toBeInTheDocument();
    expect(within(detail).getByText(/Not researched yet/)).toBeInTheDocument();
  });

  it("shows an idea's plan, dated research and demand check", async () => {
    renderPage("/ideas?idea=7");

    const detail = await screen.findByTestId("idea-detail");
    expect(within(detail).getByRole("heading", { name: IDEA.topic })).toBeInTheDocument();
    // The legacy form stored India as `in`.
    expect(within(detail).getByText("India")).toBeInTheDocument();
    expect(within(detail).getByText("45 sec")).toBeInTheDocument();
    expect(within(detail).getByText("silence quotes tamil")).toBeInTheDocument();
    expect(within(detail).getAllByText("Not supplied").length).toBeGreaterThan(0);
    expect(within(detail).getByText(/Observed 2 relevant public YouTube API result/)).toBeInTheDocument();
    expect(within(detail).getByText("When they stop talking")).toBeInTheDocument();
    expect(within(detail).getByText((91000).toLocaleString())).toBeInTheDocument();
    expect(within(detail).getByText("Not enough personal evidence.")).toBeInTheDocument();
    expect(within(detail).getByRole("link", { name: /Open in Demand/ })).toHaveAttribute("href", "/demand?snapshot=12");
  });

  it("warns when research no longer matches the idea", async () => {
    ideas[0]!.latest_research = null;
    ideas[0]!.research_is_stale = true;
    renderPage("/ideas?idea=7");

    expect(await screen.findByText(/This idea changed after its last research/)).toBeInTheDocument();
    // Generating would research again first, and the page says so before it spends quota.
    expect(screen.getByText(/researches first because this idea has no current research/)).toBeInTheDocument();
  });

  it("generates a package and links to it in History", async () => {
    const user = userEvent.setup();
    renderPage("/ideas?idea=7");

    await user.click(await screen.findByRole("button", { name: "Generate package" }));

    expect(await screen.findByText("Package saved to History as run #42.")).toBeInTheDocument();
    expect(calls("POST", "/api/ideas/7/generate")).toHaveLength(1);
    expect(JSON.parse(String(calls("POST", "/api/ideas/7/generate")[0]![1]?.body))).toEqual({});
    const detail = screen.getByTestId("idea-detail");
    expect(within(detail).getAllByRole("link", { name: /Open (package )?in History/ })[0]).toHaveAttribute(
      "href",
      "/history?run=42",
    );
    expect(within(detail).getByRole("button", { name: "Generate again" })).toBeInTheDocument();
  });

  it("reports a failed research run with its request ID", async () => {
    researchFails = true;
    const user = userEvent.setup();
    renderPage("/ideas?idea=7");

    await user.click(await screen.findByRole("button", { name: "Research now" }));

    expect(await screen.findByText("YouTube quota is exhausted for today.")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-3")).toBeInTheDocument();
  });

  it("keeps Mark published locked until a video is linked", async () => {
    const user = userEvent.setup();
    renderPage("/ideas?idea=7");

    const publish = await screen.findByRole("button", { name: "Mark published" });
    expect(publish).toBeDisabled();
    expect(screen.getByText(/Mark published unlocks once/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(calls("PATCH", "/api/ideas/7")).toHaveLength(1));
    expect(JSON.parse(String(calls("PATCH", "/api/ideas/7")[0]![1]?.body))).toEqual({ status: "archived" });
    expect(await screen.findByRole("button", { name: "Restore" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate package" })).toBeDisabled();
  });

  it("restores an archived idea to its generated package", async () => {
    Object.assign(ideas[0]!, { status: "archived", analysis_run_id: 42 });
    const user = userEvent.setup();
    renderPage("/ideas?idea=7");

    await user.click(await screen.findByRole("button", { name: "Restore" }));

    await waitFor(() => expect(calls("PATCH", "/api/ideas/7")).toHaveLength(1));
    expect(JSON.parse(String(calls("PATCH", "/api/ideas/7")[0]![1]?.body))).toEqual({ status: "package_generated" });
  });

  it("keeps a request in flight across switching ideas, so it can't be sent twice", async () => {
    ideas = [structuredClone(IDEA), { ...structuredClone(IDEA), id: 9, topic: "Letters I never sent" }];
    const route = fetchMock.getMockImplementation() as (url: string, init?: RequestInit) => Promise<unknown>;
    fetchMock.mockImplementation((url: string, init?: RequestInit) =>
      // Generating never answers in this test: it is still running when the creator comes back.
      String(url) === "/api/ideas/7/generate" ? new Promise(() => {}) : route(url, init),
    );
    const user = userEvent.setup();
    renderPage("/ideas?idea=7");

    await user.click(await screen.findByRole("button", { name: "Generate package" }));
    expect(await screen.findByRole("button", { name: "Generating…" })).toBeDisabled();

    const items = await screen.findAllByTestId("idea-item");
    await user.click(items.find((item) => item.textContent?.includes("Letters I never sent"))!);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/ideas?idea=9"));
    expect(await screen.findByRole("button", { name: "Generate package" })).toBeEnabled();

    await user.click(items.find((item) => item.textContent?.includes(IDEA.topic))!);
    expect(await screen.findByRole("button", { name: "Generating…" })).toBeDisabled();
    expect(calls("POST", "/api/ideas/7/generate")).toHaveLength(1);
  });

  it("keeps the status filter and page in the URL", async () => {
    listTotal = 45;
    const user = userEvent.setup();
    renderPage("/ideas?status=scripted");

    expect(await screen.findByText("1–1 of 45")).toBeInTheDocument();
    expect(calls("GET", "/api/ideas?limit=20&offset=0&status=scripted")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/ideas?status=scripted&offset=20"));
    await waitFor(() => expect(calls("GET", "/api/ideas?limit=20&offset=20&status=scripted")).toHaveLength(1));
  });

  it("pages through a long backlog", async () => {
    listTotal = 45;
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("1–1 of 45")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => expect(calls("GET", "/api/ideas?limit=20&offset=20")).toHaveLength(1));
  });
});
