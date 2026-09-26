import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import HistoryPage from "./History";

const RUNS = [
  {
    id: 1,
    created_at: "2026-09-22T17:53:19Z",
    title: "Three Morning Habits",
    query: "waking at the same time daily",
    opportunity_score: 38.6,
    title_score: 7.5,
    selected_package_id: "package-a",
    linked_youtube_video_id: null,
  },
  {
    id: 2,
    created_at: "2026-09-21T10:00:00Z",
    title: "Top AI Tools",
    query: "productivity tools review",
    opportunity_score: 51.2,
    title_score: 8.1,
    selected_package_id: null,
    linked_youtube_video_id: "abc12345678",
  },
];

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;

function renderPage(route = "/history") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) => {
    if (String(url).includes("/api/history/runs?")) return jsonResponse({ runs: RUNS });
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("HistoryPage", () => {
  it("lists saved packages with their scores", async () => {
    renderPage();

    expect(await screen.findByText("Three Morning Habits")).toBeInTheDocument();
    expect(screen.getByText("Top AI Tools")).toBeInTheDocument();
    expect(screen.getByText("2 saved packages")).toBeInTheDocument();
    // Rounded as the Dashboard rounds it.
    expect(screen.getByText("39/100")).toBeInTheDocument();
    expect(screen.getByText("7.5/10")).toBeInTheDocument();
  });

  it("distinguishes a recorded selection from an unknown one", async () => {
    renderPage();
    await screen.findByText("Three Morning Habits");

    expect(screen.getByText("Selected package")).toBeInTheDocument();
    expect(screen.getByText("Selection unknown")).toBeInTheDocument();
  });

  it("marks a linked run and offers to change the link", async () => {
    renderPage();
    await screen.findByText("Top AI Tools");

    expect(screen.getByText("YouTube linked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Link video" })).toBeInTheDocument();
  });

  it("filters rows by search and reports the match count", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    await user.type(screen.getByLabelText("Search saved packages"), "morning");

    await waitFor(() => expect(screen.queryByText("Top AI Tools")).not.toBeInTheDocument());
    expect(screen.getByTestId("history-result-summary")).toHaveTextContent(
      "1 of 2 packages match",
    );
  });

  it("shows each package's content angle and finds packages by it", async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse({
        runs: [
          { ...RUNS[0], content_angle: "Story", intent: "SUGGESTED" },
          { ...RUNS[1], content_angle: "Review", intent: "SUGGESTED" },
        ],
      }),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");
    expect(screen.getByText("Story")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search saved packages"), "review");

    await waitFor(() => expect(screen.queryByText("Three Morning Habits")).not.toBeInTheDocument());
    expect(screen.getByText("Top AI Tools")).toBeInTheDocument();
  });

  it("shows a distinct empty state for a search with no matches", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    await user.type(screen.getByLabelText("Search saved packages"), "zzzzz");

    expect(await screen.findByText("No saved packages match your search.")).toBeInTheDocument();
  });

  it("enables bulk delete only once something is selected", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    const bulkDelete = screen.getByRole("button", { name: /Delete selected/ });
    expect(bulkDelete).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: "Select Three Morning Habits" }));

    expect(bulkDelete).toBeEnabled();
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("selects only the rows currently visible under a search", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    await user.type(screen.getByLabelText("Search saved packages"), "morning");
    await waitFor(() => expect(screen.queryByText("Top AI Tools")).not.toBeInTheDocument());

    await user.click(screen.getByRole("checkbox", { name: "Select visible packages" }));

    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("confirms before deleting and warns about synced devices", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    await user.click(screen.getByRole("button", { name: "Delete Three Morning Habits" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/marked deleted for your synced devices/)).toBeInTheDocument();
    // Not linked to a video, so there is no collected evidence to lose.
    expect(within(dialog).queryByText(/collected snapshots/)).not.toBeInTheDocument();

    // Nothing is deleted until the confirm button is pressed.
    expect(fetchMock.mock.calls.every(([, init]) => init?.method !== "DELETE")).toBe(true);
  });

  it("says a linked video's collected evidence is deleted with its package", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Top AI Tools");

    await user.click(screen.getByRole("button", { name: "Delete Top AI Tools" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/linked video's collected snapshots, audits and experiment assignments are deleted with it/),
    ).toBeInTheDocument();
  });

  it("returns focus to the button that opened a dialog when it closes", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");
    const opener = screen.getByRole("button", { name: "Delete Three Morning Habits" });

    await user.click(opener);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(opener).toHaveFocus();
  });

  // 101 rows, each with its own checkbox and actions, take ~6 s to render and
  // select even on an idle machine, so this test gets more than the default.
  it("caps a bulk deletion to the server limit", async () => {
    const manyRuns = Array.from({ length: 101 }, (_, index) => ({
      ...RUNS[0],
      id: index + 1,
      title: `Package ${index + 1}`,
    }));
    fetchMock.mockImplementation(async () => jsonResponse({ runs: manyRuns }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Package 1");

    await user.click(screen.getByRole("checkbox", { name: "Select visible packages" }));
    await user.click(screen.getByRole("button", { name: /Delete selected/ }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "Delete 100 packages" }),
    ).toBeInTheDocument();
  }, 60_000);

  it("requires a plausible video id before linking", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Three Morning Habits");

    await user.click(screen.getByRole("button", { name: "Link video" }));

    const dialog = await screen.findByRole("dialog");
    const submit = within(dialog).getByRole("button", { name: "Link video" });
    expect(submit).toBeDisabled();

    await user.type(within(dialog).getByLabelText(/YouTube video ID/), "short");
    expect(submit).toBeDisabled();
    expect(within(dialog).getByText(/11-character video ID/)).toBeInTheDocument();

    // A link from another site is refused as the server would refuse it.
    await user.clear(within(dialog).getByLabelText(/YouTube video ID/));
    await user.type(within(dialog).getByLabelText(/YouTube video ID/), "https://example.com/watch?v=dQw4w9WgXcQ");
    expect(submit).toBeDisabled();

    await user.clear(within(dialog).getByLabelText(/YouTube video ID/));
    await user.type(within(dialog).getByLabelText(/YouTube video ID/), "dQw4w9WgXcQ");
    expect(submit).toBeEnabled();
  });

  it("reports an empty library without inventing rows", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ runs: [] }));
    renderPage();

    expect(
      await screen.findByText(
        "No saved packages yet. Generate an SEO package and it will appear here.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the library's counts as unavailable when the list can't be read", async () => {
    fetchMock.mockImplementation(async () => ({
      ok: false,
      status: 503,
      text: async () => JSON.stringify({ error: { code: "database_unavailable", message: "The database is unavailable." } }),
    }));
    renderPage();

    expect(await screen.findByText("Could not load saved packages.")).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Library summary" });
    expect(within(summary).getAllByText("Unavailable")).toHaveLength(4);
    expect(within(summary).queryByText("0")).not.toBeInTheDocument();
  });

  it("opens a package straight from a ?run= link", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (String(url).includes("/api/history/runs?")) return jsonResponse({ runs: RUNS });
      if (String(url).endsWith("/api/history/runs/2")) {
        return jsonResponse({
          id: 2,
          title: "Top AI Tools",
          created_at: "2026-09-21T10:00:00Z",
          package: { title: "Top AI Tools", description: "A tour of five tools.", tags: ["ai tools"], hashtags: ["#ai"] },
        });
      }
      return jsonResponse({});
    });
    renderPage("/history?run=2");

    const detail = await screen.findByTestId("history-detail");
    expect(await within(detail).findByText("A tour of five tools.")).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "Copy upload package" })).toBeEnabled();
  });

  it("counts every saved package, not just the first page", async () => {
    const page = (offset: number, count: number) =>
      Array.from({ length: count }, (_, index) => ({ ...RUNS[0], id: offset + index + 1, title: `Package ${offset + index + 1}` }));
    fetchMock.mockImplementation(async (url: string) => {
      const query = new URLSearchParams(String(url).split("?")[1]);
      const offset = Number(query.get("offset"));
      return jsonResponse({ runs: offset === 0 ? page(0, 100) : page(100, 30), total: 130 });
    });
    renderPage();

    expect(await screen.findByText("130 saved packages")).toBeInTheDocument();
    expect(await screen.findByText("Package 130")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual(
      expect.arrayContaining(["/api/history/runs?limit=100&offset=0", "/api/history/runs?limit=100&offset=100"]),
    );
  });

  it("shows an unmeasured opportunity as unavailable, not 0", async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse({ runs: [{ ...RUNS[0], opportunity_score: null, opportunity_label: "UNMEASURED" }] }),
    );
    renderPage();

    const scores = await screen.findByRole("group", { name: "Package scores" });
    expect(within(scores).getByText("Unavailable")).toBeInTheDocument();
    expect(within(scores).queryByText(/^0/)).not.toBeInTheDocument();
    // The library average leaves unmeasured runs out rather than counting them as 0.
    expect(screen.getByText("Avg opportunity").previousElementSibling).toHaveTextContent("Unavailable");
  });

  it("shows the linked video's own id and measured numbers", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (String(url).includes("/api/history/runs?")) return jsonResponse({ runs: RUNS });
      if (String(url).endsWith("/api/history/runs/2")) {
        return jsonResponse({
          id: 2,
          title: "Top AI Tools",
          package: { title: "Top AI Tools", description: "Tools.", tags: ["ai tools"], hashtags: [] },
          linked_video_report: {
            linked: true,
            video_id: "z4HKMfQ3nJc",
            ownership_verified: true,
            youtube: { title: null },
            performance: { views: 121, likes: 2, comments: null, captured_at: "2026-09-20T10:00:00Z", snapshot_window: "current" },
            package_usage: { generated_tags: ["ai tools"], matching_tags: [], title_match: true },
            diagnosis: { verdict: "OBSERVATION ONLY — more comparable linked videos are needed" },
          },
        });
      }
      return jsonResponse({});
    });
    renderPage("/history?run=2");

    const published = await screen.findByTestId("published-video");
    expect(within(published).getByText("z4HKMfQ3nJc")).toBeInTheDocument();
    expect(within(published).getByText("121")).toBeInTheDocument();
    // A comment count YouTube didn't report is unavailable, not 0.
    expect(within(published).getAllByText("Unavailable").length).toBeGreaterThan(0);
    // With only partial metadata the package's title stands in, never "undefined".
    expect(within(published).getByText("Top AI Tools")).toBeInTheDocument();
    expect(within(published).getByText(/OBSERVATION ONLY/)).toBeInTheDocument();
    expect(screen.queryByText(/Linked to YouTube video Unavailable/)).not.toBeInTheDocument();
  });

  it("asks before a relink deletes the old video's evidence, and resends only when confirmed", async () => {
    const linkCalls: unknown[] = [];
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/api/history/runs?")) return jsonResponse({ runs: RUNS });
      if (String(url) === "/api/history/runs/2/link-video" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        linkCalls.push(body);
        if (!body.replace_existing_evidence) {
          return {
            ok: false,
            status: 409,
            text: async () =>
              JSON.stringify({
                error: {
                  code: "relink_would_delete_evidence",
                  message: "This package is linked to abc12345678, which has collected evidence.",
                  request_id: "req-7",
                  details: { youtube_video_id: "abc12345678", evidence: { snapshots: 3, audits: 1, experiments: 0 } },
                },
              }),
          };
        }
        return jsonResponse({ status: "linked", ownership_message: "Linked.", refresh_warning: null });
      }
      return jsonResponse({});
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Change link" }));
    const linkDialog = await screen.findByRole("dialog");
    await user.type(within(linkDialog).getByLabelText(/YouTube video ID/), "dQw4w9WgXcQ");
    await user.click(within(linkDialog).getByRole("button", { name: "Update link" }));

    const confirm = await screen.findByRole("dialog", { name: "Replace the linked video?" });
    expect(within(confirm).getByText("3 snapshots")).toBeInTheDocument();
    expect(within(confirm).getByText("1 audit")).toBeInTheDocument();
    // Cancel has focus first, so pressing Enter can't delete evidence by accident.
    expect(within(confirm).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(linkCalls).toEqual([{ youtube_video_id: "dQw4w9WgXcQ" }]);

    await user.click(within(confirm).getByRole("button", { name: "Delete evidence and relink" }));
    await waitFor(() => expect(linkCalls).toHaveLength(2));
    expect(linkCalls[1]).toEqual({ youtube_video_id: "dQw4w9WgXcQ", replace_existing_evidence: true });
  });

  it("surfaces a load failure with its request id", async () => {
    fetchMock.mockImplementation(async () => ({
      ok: false,
      status: 500,
      text: async () =>
        JSON.stringify({ error: { message: "Database unavailable.", request_id: "req-42" } }),
    }));
    renderPage();

    expect(await screen.findByText("Database unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-42")).toBeInTheDocument();
  });
});
