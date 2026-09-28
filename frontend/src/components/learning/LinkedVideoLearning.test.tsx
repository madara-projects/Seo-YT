import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LinkedVideoLearning } from "./LinkedVideoLearning";
import type { LinkedTrafficEvidence, RetentionProbeResult } from "@/api/learningTypes";

const EVIDENCE: LinkedTrafficEvidence = {
  traffic_sources: {
    sources: [
      { source: "YT_SEARCH", views: 700, watch_time_minutes: 2100, share_percent: 70 },
      { source: "RELATED_VIDEO", views: 300, watch_time_minutes: 900, share_percent: 30 },
    ],
    total_views: 1000,
    dominant_source: "YT_SEARCH",
    dominant_share_percent: 70,
    window: "7d",
  },
  traffic_source_cohort: {
    traffic_source: "YT_SEARCH",
    snapshot_window: "7d",
    sample_size: 2,
    minimum_samples: 5,
    more_needed: 3,
    learning_allowed: false,
    median_views: null,
    median_retention_percentage: null,
  },
};

const POINTS = Array.from({ length: 100 }, (_, index) => ({
  elapsed_ratio: (index + 1) / 100,
  audience_watch_ratio: 1 - index * 0.005,
  relative_retention_performance: 0.6,
}));

const AVAILABLE: RetentionProbeResult = {
  status: "available",
  reason: null,
  message: "YouTube Analytics returned the audience-retention curve for this video.",
  requests: 1,
  points: POINTS,
  duration_seconds: 600,
  observations: {
    hook: { end_ratio: 0.15, still_watching_percent: 93, relative_retention_performance: 0.6 },
    biggest_drop: { from_ratio: 0.04, at_ratio: 0.05, at_seconds: 30, drop_points: 20.4, in_hook: true, chapter: null },
    chapters: [],
    observations: ["The biggest single drop (20.4 points of the audience) comes 5% of the way in, around 0:30, within the hook (the first 15%)."],
    note: "Observations of when viewers left, not proof of why.",
  },
};

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;
let probeAnswer: RetentionProbeResult;

function renderLearning(props: Partial<React.ComponentProps<typeof LinkedVideoLearning>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LinkedVideoLearning evidence={EVIDENCE} linkId={5} verified {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  probeAnswer = AVAILABLE;
  fetchMock = vi.fn(async () => json(probeAnswer));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("LinkedVideoLearning", () => {
  it("shows the traffic sources and how many more comparable videos are needed", () => {
    renderLearning();
    const block = screen.getByTestId("traffic-sources");

    expect(within(block).getByText("YouTube search")).toBeInTheDocument();
    expect(within(block).getByText("Suggested videos")).toBeInTheDocument();
    expect(within(block).getByText(/mostly YouTube search \(70\.0% of views\)/)).toBeInTheDocument();
    expect(within(block).getByTestId("traffic-cohort")).toHaveTextContent("3 more needed before comparing");
  });

  it("compares with peers only once enough of them exist", () => {
    renderLearning({
      evidence: {
        ...EVIDENCE,
        traffic_source_cohort: {
          ...EVIDENCE.traffic_source_cohort!,
          sample_size: 6,
          more_needed: 0,
          learning_allowed: true,
          confidence_label: "Early signal",
          median_views: 1500,
          median_retention_percentage: 41.5,
        },
      },
    });
    expect(screen.getByTestId("traffic-cohort")).toHaveTextContent("Early signal: 6 other comparable videos");
    expect(screen.getByTestId("traffic-cohort")).toHaveTextContent("41.5% average viewed");
  });

  it("says when no breakdown is stored", () => {
    renderLearning({ evidence: { traffic_sources: null, traffic_source_cohort: null } });
    expect(screen.getByText(/No traffic-source breakdown is stored yet/)).toBeInTheDocument();
  });

  it("offers the probe only for a verified video and marks it as one request", () => {
    const { unmount } = renderLearning({ verified: false });
    expect(screen.queryByRole("button", { name: "Check retention curve" })).not.toBeInTheDocument();
    expect(screen.getByText(/verified as your connected channel's own/)).toBeInTheDocument();
    unmount();

    renderLearning();
    expect(screen.getByRole("button", { name: "Check retention curve" })).toBeInTheDocument();
    expect(screen.getByText("Uses one YouTube Analytics request.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("draws the curve and lists observations when YouTube returns one", async () => {
    const user = userEvent.setup();
    renderLearning();
    await user.click(screen.getByRole("button", { name: "Check retention curve" }));

    expect(await screen.findByTestId("retention-curve")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/published-videos/5/retention-probe", expect.objectContaining({ method: "POST" }));
    expect(screen.getByRole("list", { name: "Observations" })).toHaveTextContent("within the hook");
    expect(screen.getByText(/not proof of why/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
  });

  it.each([
    ["missing_scope", "Analytics permission missing", 1],
    ["not_channel_video", "Not the channel's own video", 1],
    ["no_data_yet", "No retention data yet", 0],
    ["api_error", "YouTube request failed", 1],
  ] as const)("explains an unavailable curve: %s", async (reason, label, requests) => {
    probeAnswer = { status: "unavailable", reason, message: "Details from the server.", requests, points: [], observations: null };
    const user = userEvent.setup();
    renderLearning();
    await user.click(screen.getByRole("button", { name: "Check retention curve" }));

    await waitFor(() => expect(screen.getByText(`${label}.`)).toBeInTheDocument());
    expect(screen.getByText(/Details from the server\./)).toHaveTextContent(
      requests ? "One YouTube Analytics request was made." : "No YouTube request was made.",
    );
    expect(screen.queryByTestId("retention-curve")).not.toBeInTheDocument();
  });
});
