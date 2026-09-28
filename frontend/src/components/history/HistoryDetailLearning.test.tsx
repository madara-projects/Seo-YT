import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { HistoryDetail } from "./HistoryDetail";
import type { HistoryRunDetail } from "@/api/historyTypes";

const RUN = {
  id: 9,
  created_at: "2026-09-01T10:00:00Z",
  title: "How I fixed my sleep",
  package: { title: "How I fixed my sleep", description: "d", tags: [], hashtags: [] },
  linked_video_report: {
    linked: true,
    link_id: 4,
    video_id: "sleepvideo1",
    ownership_verified: true,
    performance: { views: 1000, snapshot_window: "7d", captured_at: "2026-09-10T00:00:00Z" },
    traffic_sources: {
      sources: [{ source: "YT_SEARCH", views: 800, watch_time_minutes: 1000, share_percent: 80 }],
      total_views: 800,
      dominant_source: "YT_SEARCH",
      dominant_share_percent: 80,
      window: "7d",
    },
    traffic_source_cohort: null,
  },
} as unknown as HistoryRunDetail;

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function renderDetail(run: HistoryRunDetail) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HistoryDetail open run={run} isLoading={false} error={null} onClose={() => undefined} onLink={() => undefined} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      json(
        String(url) === "/api/history/runs/9/studio-tests"
          ? { eligible: true, candidates: [], similar_pairs: [], tests: [], max_variants: 3, min_variants: 2, note: "" }
          : {},
      ),
    ),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("HistoryDetail outcome learning", () => {
  it("adds traffic sources, the retention probe and the Studio test to a linked package", async () => {
    renderDetail(RUN);
    const published = await screen.findByTestId("published-video");

    expect(within(published).getByTestId("traffic-sources")).toHaveTextContent("YouTube search");
    expect(within(published).getByRole("button", { name: "Check retention curve" })).toBeInTheDocument();
    expect(screen.getByTestId("studio-test-panel")).toBeInTheDocument();
    expect(await screen.findByText(/no title\/thumbnail packages to test/)).toBeInTheDocument();
  });

  it("offers no retention probe for an unverified video", async () => {
    renderDetail({
      ...RUN,
      linked_video_report: { ...RUN.linked_video_report, ownership_verified: false },
    } as HistoryRunDetail);
    const published = await screen.findByTestId("published-video");
    expect(within(published).queryByRole("button", { name: "Check retention curve" })).not.toBeInTheDocument();
  });
});
