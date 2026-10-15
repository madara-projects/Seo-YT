import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { HistoryDetail } from "./HistoryDetail";
import { AI_SHORTS_PLAN } from "@/test/fixtures/aiShorts";
import type { HistoryRunDetail } from "@/api/historyTypes";

const MARKER = { plan_id: 31, parts: 2, total_seconds: 16, language: "english", generation_source: "gemini" };

/** A package the AI Shorts page saved, as `GET /api/history/runs/66` returns it. */
const SHORT_RUN = {
  id: 66,
  created_at: "2026-10-14T17:24:31Z",
  query: "Your future needs you. Your past doesn't.",
  content_angle: "Story",
  title: "Your future needs you #shorts",
  title_score: 9,
  retention_risk: "LOW",
  opportunity_label: "UNMEASURED",
  opportunity_score: null,
  source_page: "ai_shorts",
  ai_shorts: MARKER,
  package: {
    title: "Your future needs you #shorts",
    description: "What are you carrying from yesterday?",
    tags: ["motivation quotes", "future quotes,"],
    hashtags: ["#shorts", "#quotes"],
    title_variants: ["Your future needs you #shorts", "Does your past decide your future? #shorts"],
    creator_brief: { content: "Your future needs you. Your past doesn't." },
    chapters: [],
    retention_assistant: { status: "available", rule_version: "phase5-v1", risk_level: "none", risk_map: [] },
    source_page: "ai_shorts",
    ai_shorts: MARKER,
  },
  selected_package: null,
  linked_video_report: { linked: false },
} as HistoryRunDetail;

/** The run's own plan: the fixture, saved under run 66. */
const PLAN = { ...AI_SHORTS_PLAN, analysis_run_id: 66 };

const CREATOR_RUN = {
  id: 9,
  created_at: "2026-09-01T10:00:00Z",
  query: "how I fixed my sleep",
  content_angle: "Story",
  title: "How I fixed my sleep",
  title_score: 7.5,
  retention_risk: "MEDIUM",
  opportunity_label: "WORKABLE",
  opportunity_score: 48.3,
  package: {
    title: "How I fixed my sleep",
    description: "Three changes that worked.",
    tags: ["sleep"],
    hashtags: ["#sleep"],
    chapters: [{ timestamp: "0:00", title: "Intro" }],
    creator_brief: { content: "I used to sleep at 3am." },
  },
  selected_package: null,
  linked_video_report: { linked: false },
} as HistoryRunDetail;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

type Responder = () => unknown;
let planResponse: Responder;
let fetchMock: ReturnType<typeof vi.fn>;

function requested(path: string) {
  return fetchMock.mock.calls.some(([url]) => String(url) === path);
}

function renderDetail(run: HistoryRunDetail, onLink = () => undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HistoryDetail open run={run} isLoading={false} error={null} onClose={() => undefined} onLink={onLink} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  planResponse = () => json(PLAN);
  fetchMock = vi.fn(async (url: string) => {
    if (String(url) === "/api/ai-shorts/plans/31") return planResponse();
    if (String(url).endsWith("/studio-tests")) {
      return json({ eligible: true, candidates: [], similar_pairs: [], tests: [], max_variants: 3, min_variants: 2, note: "" });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("HistoryDetail for an AI Shorts package", () => {
  it("opens with the plan's Flow prompts and none of the Creator-only blocks", async () => {
    renderDetail(SHORT_RUN);
    const detail = screen.getByTestId("history-detail");

    const cards = await within(detail).findAllByTestId("shot-card");
    expect(cards).toHaveLength(2);
    expect(within(detail).getByRole("button", { name: "Copy prompt for Part 1" })).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "Copy prompt for Part 2" })).toBeInTheDocument();
    expect(requested("/api/ai-shorts/plans/31")).toBe(true);

    expect(within(detail).getByText("Saved AI Short")).toBeInTheDocument();
    expect(within(detail).getByText("AI Shorts · 2 parts · 16 s")).toBeInTheDocument();
    const actions = within(detail).getByRole("group", { name: "Package actions" });
    expect(within(actions).getByRole("button", { name: "Copy upload package" })).toBeEnabled();
    expect(within(actions).getByRole("link", { name: "Open in AI Shorts" })).toHaveAttribute("href", "/ai-shorts?plan=31");

    // Test & Compare is for long videos, and a Short's opportunity is never measured.
    expect(within(detail).queryByTestId("studio-test-panel")).not.toBeInTheDocument();
    expect(requested("/api/history/runs/66/studio-tests")).toBe(false);
    expect(within(detail).queryByText("Not measured: no competitor results")).not.toBeInTheDocument();
    expect(within(detail).queryByText(/Retention guidance/)).not.toBeInTheDocument();
    expect(within(detail).queryByText("Creator-selected package")).not.toBeInTheDocument();

    // The plan holds the package, so the saved copy isn't shown a second time.
    expect(within(detail).queryByRole("heading", { name: "Tags" })).not.toBeInTheDocument();

    const performance = within(detail).getByRole("button", { name: /Performance/ });
    expect(performance).toHaveAttribute("aria-expanded", "false");
    expect(performance).toHaveTextContent("No YouTube video linked yet");
  });

  it("says while the prompts load", async () => {
    let release: (value: unknown) => void = () => undefined;
    planResponse = () => new Promise((resolve) => (release = resolve));
    renderDetail(SHORT_RUN);

    expect(await screen.findByText("Loading the Flow prompts…")).toBeInTheDocument();
    release(json(PLAN));
    expect(await screen.findAllByTestId("shot-card")).toHaveLength(2);
    expect(screen.queryByText("Loading the Flow prompts…")).not.toBeInTheDocument();
  });

  it("says the prompts were deleted and keeps the saved package", async () => {
    planResponse = () => json({ error: { code: "http_error", message: "AI Shorts plan not found." } }, 404);
    renderDetail(SHORT_RUN);
    const detail = screen.getByTestId("history-detail");

    expect(await within(detail).findByText("The Flow prompts for this Short were deleted")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { level: 2, name: "Your future needs you #shorts" })).toBeInTheDocument();
    expect(within(detail).getByText("What are you carrying from yesterday?")).toBeInTheDocument();
    const tags = within(detail).getByRole("heading", { name: "Tags" }).closest("section")!;
    expect(within(tags).getByText("future quotes")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { name: "Quote" })).toBeInTheDocument();
    // A Short has no chapters to report missing.
    expect(within(detail).queryByRole("heading", { name: "Chapters" })).not.toBeInTheDocument();
    // The AI Shorts page has nothing to open either.
    expect(within(detail).queryByRole("link", { name: "Open in AI Shorts" })).not.toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "Copy upload package" })).toBeEnabled();
    expect(within(detail).queryByTestId("shot-card")).not.toBeInTheDocument();
  });

  it("reports a plan that could not be loaded, and loads it on retry", async () => {
    planResponse = () =>
      json({ error: { code: "database_unavailable", message: "The database is unavailable.", request_id: "req-9" } }, 503);
    const user = userEvent.setup();
    renderDetail(SHORT_RUN);
    const detail = screen.getByTestId("history-detail");

    const alert = await within(detail).findByRole("alert");
    expect(alert).toHaveTextContent("Could not load the Flow prompts. The database is unavailable.");
    expect(alert).toHaveTextContent("Request ID: req-9");
    // The saved package is still there to copy from.
    expect(within(detail).getByText("What are you carrying from yesterday?")).toBeInTheDocument();

    planResponse = () => json(PLAN);
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await within(detail).findAllByTestId("shot-card")).toHaveLength(2);
    expect(within(detail).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says the prompts stayed on the device that wrote a synced Short", async () => {
    renderDetail({ ...SHORT_RUN, ai_shorts: { ...MARKER, plan_id: null } } as HistoryRunDetail);
    const detail = screen.getByTestId("history-detail");

    expect(within(detail).getByText("The Flow prompts are on another device")).toBeInTheDocument();
    expect(within(detail).getByText("What are you carrying from yesterday?")).toBeInTheDocument();
    expect(within(detail).queryByRole("link", { name: "Open in AI Shorts" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/ai-shorts/"))).toBe(false);
  });

  it("never shows another run's prompts", async () => {
    planResponse = () => json({ ...PLAN, analysis_run_id: 4201 });
    renderDetail(SHORT_RUN);

    expect(await screen.findByText("The Flow prompts are on another device")).toBeInTheDocument();
    expect(screen.queryByTestId("shot-card")).not.toBeInTheDocument();
  });

  it("opens Performance to link the published Short", async () => {
    const onLink = vi.fn();
    const user = userEvent.setup();
    renderDetail(SHORT_RUN, onLink);
    await screen.findAllByTestId("shot-card");

    await user.click(screen.getByRole("button", { name: /Performance/ }));
    const performance = screen.getByTestId("history-performance");
    await user.click(within(performance).getByRole("button", { name: "Link video" }));
    expect(onLink).toHaveBeenCalledTimes(1);
  });

  it("shows a linked Short's numbers in Performance, already open", async () => {
    renderDetail({
      ...SHORT_RUN,
      linked_video_report: {
        linked: true,
        link_id: 3,
        video_id: "shortvideo1",
        ownership_verified: true,
        performance: { views: 1520, likes: 40, comments: 2, captured_at: "2026-10-15T00:00:00Z", snapshot_window: "24h" },
      },
    } as HistoryRunDetail);

    const trigger = screen.getByRole("button", { name: /Performance/ });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveTextContent("Linked to shortvideo1 · 1,520 views");
    const published = screen.getByTestId("published-video");
    expect(within(published).getByText("1,520")).toBeInTheDocument();
    expect(screen.getByText("YouTube linked")).toBeInTheDocument();
  });

  it("offers to delete the package from its header, with focus starting on Close", async () => {
    const onDelete = vi.fn();
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HistoryDetail
            open
            run={SHORT_RUN}
            isLoading={false}
            error={null}
            onClose={() => undefined}
            onLink={() => undefined}
            onDelete={onDelete}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Delete comes first in the header, but Enter on opening must not reach it.
    await waitFor(() => expect(screen.getByRole("button", { name: "Close package detail" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Delete this package" }));
    expect(onDelete).toHaveBeenCalledTimes(1);
  });
});

describe("HistoryDetail for a Creator package", () => {
  it("keeps its scores, Studio test and full package, and fetches no plan", async () => {
    renderDetail(CREATOR_RUN);
    const detail = screen.getByTestId("history-detail");

    expect(within(detail).getByText("Saved package")).toBeInTheDocument();
    expect(within(detail).getByText("Opportunity")).toBeInTheDocument();
    expect(within(detail).getByText("Title quality")).toBeInTheDocument();
    expect(within(detail).getByText("Retention risk")).toBeInTheDocument();
    expect(within(detail).getByText("Creator-selected package")).toBeInTheDocument();
    expect(within(detail).getByText("Published-video learning")).toBeInTheDocument();
    expect(within(detail).getByTestId("studio-test-panel")).toBeInTheDocument();
    expect(within(detail).getByText("Three changes that worked.")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { name: "Chapters" })).toBeInTheDocument();
    expect(within(detail).getByText("0:00 Intro")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { name: "Source script" })).toBeInTheDocument();
    expect(within(detail).getByText("Not linked")).toBeInTheDocument();

    expect(within(detail).queryByText(/AI Shorts/)).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("history-performance")).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("history-detail-plan")).not.toBeInTheDocument();
    await waitFor(() => expect(requested("/api/history/runs/9/studio-tests")).toBe(true));
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/ai-shorts/"))).toBe(false);
  });
});
