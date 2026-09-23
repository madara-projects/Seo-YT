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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
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
    expect(screen.getByText("38.6/100")).toBeInTheDocument();
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

    // Nothing is deleted until the confirm button is pressed.
    expect(fetchMock.mock.calls.every(([, init]) => init?.method !== "DELETE")).toBe(true);
  });

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
  });

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
    expect(within(dialog).getByText(/at least 11 characters/)).toBeInTheDocument();

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
