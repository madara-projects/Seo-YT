import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TrafficSourceLearning } from "./TrafficSourceLearning";

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TrafficSourceLearning />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) =>
    String(url).endsWith("window=7d")
      ? json({
          traffic_source_groups: [
            { format: "youtube_shorts", language: "english", traffic_source: "RELATED_VIDEO", snapshot_window: "7d", sample_size: 6, minimum_samples: 5, more_needed: 0,
              learning_allowed: true, median_views: 1200, median_retention_percentage: 38.5 },
            { format: "tutorial", language: "tamil", traffic_source: "YT_SEARCH", snapshot_window: "7d", sample_size: 2, minimum_samples: 5, more_needed: 3,
              learning_allowed: false, median_views: null, median_retention_percentage: null },
          ],
          without_traffic_sources: 1,
        })
      : json({ traffic_source_groups: [], without_traffic_sources: 0 }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("TrafficSourceLearning", () => {
  it("compares a source only past the evidence minimum and says how many more the others need", async () => {
    renderPanel();

    expect(await screen.findByText("Suggested videos")).toBeInTheDocument();
    expect(screen.getByText("6 videos · median 1,200 views · 38.5% viewed")).toBeInTheDocument();
    expect(screen.getByText("YouTube search")).toBeInTheDocument();
    expect(screen.getByText("2 of 5 videos · 3 more needed")).toBeInTheDocument();
    expect(screen.getByText("1 comparable video has no breakdown for this window.")).toBeInTheDocument();
    // Each group is one format and language, and says which.
    expect(screen.getByText("Shorts · English")).toBeInTheDocument();
    expect(screen.getByText("Tutorial · Tamil")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/learning/cohorts?window=7d", expect.anything());
  });

  it("switches the evidence window", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText("Suggested videos");

    await user.click(screen.getByRole("button", { name: "28 days" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/learning/cohorts?window=28d", expect.anything()));
    expect(await screen.findByText(/No comparable video has a traffic-source breakdown/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "28 days" })).toHaveAttribute("aria-pressed", "true");
  });
});
