import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";
import { PublishedVideo } from "./HistoryDetailParts";
import { historyKeys } from "@/hooks/queryKeys";
import type { LinkedVideoReport } from "@/api/historyTypes";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// The six links in the finding: verified, completed, but the language was never recorded.
const REPORT: LinkedVideoReport = {
  linked: true,
  link_id: 4,
  video_id: "sleepvideo1",
  ownership_verified: true,
  performance: { views: 1000, snapshot_window: "7d", captured_at: "2026-09-10T00:00:00Z" },
  comparable_metadata: {
    link_id: 4,
    language: "unknown",
    format: "youtube_shorts",
    duration_bucket: "under_60s",
    topic_category: "unknown",
    sources: { language: "unknown", format: "package", duration_bucket: "creator", topic_category: "unknown" },
  },
  snapshots: [
    { snapshot_window: "24h", snapshot_status: "complete", attempt_count: 1, retry_allowed: false },
    { snapshot_window: "7d", snapshot_status: "failed", attempt_count: 3, retry_allowed: false },
  ],
  diagnosis: {
    verdict: "Early read: views are building",
    what_worked: [],
    needs_improvement: [],
    confidence: "Collecting evidence",
    learning_eligible: false,
  },
};

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;
let client: QueryClient;

function renderReport(report: LinkedVideoReport = REPORT) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PublishedVideo report={report} packageTitle="Saved package" />
    </QueryClientProvider>,
  );
}

function calls(path: string): [string, RequestInit][] {
  return (fetchMock.mock.calls as [string, RequestInit][]).filter(([url]) => String(url) === path);
}

/** The options of the first request to `path`. */
function sent(path: string): RequestInit {
  const call = calls(path)[0];
  if (!call) throw new Error(`No request to ${path}`);
  return call[1];
}

beforeAll(() => {
  // Radix Select uses pointer capture and scrolls the chosen item into view; jsdom has neither.
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => undefined;
  Element.prototype.scrollIntoView ??= () => undefined;
});

beforeEach(() => {
  vi.mocked(toast.success).mockClear();
  vi.mocked(toast.error).mockClear();
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/comparable-metadata")) {
      return json({ status: "updated", link_id: 4, comparable_metadata: JSON.parse(String(init?.body)) });
    }
    if (path.endsWith("/refresh")) return json({ message: "Current YouTube metadata and available analytics were refreshed." });
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("learning labels on a linked video", () => {
  it("says the video is left out of learning because its language is unknown", () => {
    renderReport();
    const block = screen.getByTestId("learning-labels");
    expect(block).toHaveTextContent("Not used for learning");
    expect(block).toHaveTextContent("Its language is unknown.");
    expect(block).toHaveTextContent("once its topic is set too");
    expect(within(block).getByText("Excluded")).toBeInTheDocument();
    expect(within(block).getByText("YouTube Short")).toBeInTheDocument();
  });

  it("saves only the labels that changed, through the comparable-metadata route", async () => {
    const user = userEvent.setup();
    renderReport();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const block = screen.getByTestId("learning-labels");
    await user.click(within(block).getByRole("button", { name: "Edit labels" }));

    const save = within(block).getByRole("button", { name: "Save labels" });
    // Nothing changed yet, so there is nothing to send (the route 422s an empty body).
    expect(save).toBeDisabled();

    await user.click(within(block).getByRole("combobox", { name: "Language" }));
    await user.click(await screen.findByRole("option", { name: "Tamil" }));
    await user.type(within(block).getByLabelText("Topic"), "  sleep   habits ");
    await user.click(save);

    await waitFor(() => expect(calls("/api/published-videos/4/comparable-metadata")).toHaveLength(1));
    const init = sent("/api/published-videos/4/comparable-metadata");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ language: "tamil", topic_category: "sleep habits" });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Learning labels saved."));
    // The report, cohorts and audits read the labels; the paged package list does not.
    expect(invalidate).toHaveBeenCalledWith(expect.objectContaining({ queryKey: historyKeys.all }));
    expect(invalidate).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["audits"] }));
    expect(within(block).queryByRole("button", { name: "Save labels" })).not.toBeInTheDocument();
  });

  it("reloads the package's detail but not the paged package list", async () => {
    const user = userEvent.setup();
    renderReport();
    client.setQueryData(historyKeys.run(7), { id: 7 });
    client.setQueryData([...historyKeys.runs(), { page: 1 }], { runs: [] });
    const block = screen.getByTestId("learning-labels");
    await user.click(within(block).getByRole("button", { name: "Edit labels" }));
    await user.click(within(block).getByRole("combobox", { name: "Language" }));
    await user.click(await screen.findByRole("option", { name: "Tamil" }));
    await user.click(within(block).getByRole("button", { name: "Save labels" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Learning labels saved."));
    expect(client.getQueryState(historyKeys.run(7))?.isInvalidated).toBe(true);
    expect(client.getQueryState([...historyKeys.runs(), { page: 1 }])?.isInvalidated).toBe(false);
  });

  it("sends one save for a double submit", async () => {
    const user = userEvent.setup();
    renderReport();
    const block = screen.getByTestId("learning-labels");
    await user.click(within(block).getByRole("button", { name: "Edit labels" }));
    await user.click(within(block).getByRole("combobox", { name: "Language" }));
    await user.click(await screen.findByRole("option", { name: "Tamil" }));
    const form = within(block).getByRole("form", { name: "Edit learning labels" });
    // Both before any await, so only the submit guard can stop the second.
    fireEvent.submit(form);
    fireEvent.submit(form);

    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    expect(calls("/api/published-videos/4/comparable-metadata")).toHaveLength(1);
  });

  it("keeps the editor open and reports the server's refusal", async () => {
    fetchMock.mockImplementation(async () =>
      json({ error: { message: "Invalid format.", request_id: "req-9" } }, 422),
    );
    const user = userEvent.setup();
    renderReport();
    const block = screen.getByTestId("learning-labels");
    await user.click(within(block).getByRole("button", { name: "Edit labels" }));
    await user.type(within(block).getByLabelText("Topic"), "sleep");
    await user.click(within(block).getByRole("button", { name: "Save labels" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Invalid format. Request ID: req-9"));
    expect(within(block).getByRole("button", { name: "Save labels" })).toBeEnabled();
  });

  it("names an included video once the server says it counts", () => {
    renderReport({
      ...REPORT,
      comparable_metadata: { language: "english", format: "youtube_shorts", duration_bucket: "under_60s", topic_category: "sleep" },
      diagnosis: { ...REPORT.diagnosis, counts_toward_generation: true },
    });
    const block = screen.getByTestId("learning-labels");
    expect(block).toHaveTextContent("Used for learning");
    expect(within(block).getByText("Included")).toBeInTheDocument();
  });
});

describe("refreshing a linked video from History", () => {
  it("refreshes with no body, once, however often the button is pressed", async () => {
    let release: (value: unknown) => void = () => undefined;
    fetchMock.mockImplementation(
      () => new Promise((resolve) => (release = () => resolve(json({ message: "Current YouTube metadata and available analytics were refreshed." })))),
    );
    const user = userEvent.setup();
    renderReport();
    const button = screen.getByRole("button", { name: "Refresh data" });
    await user.click(button);
    await user.click(button);

    expect(await screen.findByRole("button", { name: "Refreshing…" })).toBeDisabled();
    expect(calls("/api/published-videos/4/refresh")).toHaveLength(1);
    const init = sent("/api/published-videos/4/refresh");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();

    release(null);
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Current YouTube metadata and available analytics were refreshed."),
    );
    expect(await screen.findByRole("button", { name: "Refresh data" })).toBeEnabled();
  });

  it("stops a second click made before the first has re-rendered", async () => {
    renderReport();
    const button = screen.getByRole("button", { name: "Refresh data" });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    expect(calls("/api/published-videos/4/refresh")).toHaveLength(1);
  });

  it("offers no retry while every window still has attempts left", () => {
    renderReport();
    expect(screen.queryByRole("button", { name: "Retry failed windows" })).not.toBeInTheDocument();
  });

  it("retries exhausted windows with the retry flag", async () => {
    const user = userEvent.setup();
    renderReport({
      ...REPORT,
      snapshots: [{ snapshot_window: "7d", snapshot_status: "failed", attempt_count: 3, retry_allowed: false, retry_exhausted: true }],
    });
    await user.click(screen.getByRole("button", { name: "Retry failed windows" }));

    await waitFor(() => expect(calls("/api/published-videos/4/refresh")).toHaveLength(1));
    const init = sent("/api/published-videos/4/refresh");
    expect(JSON.parse(String(init.body))).toEqual({ retry_failed_windows: true });
  });

  it("reports a failed refresh", async () => {
    fetchMock.mockImplementation(async () => json({ error: { message: "YouTube refused the request." } }, 400));
    const user = userEvent.setup();
    renderReport();
    await user.click(screen.getByRole("button", { name: "Refresh data" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("YouTube refused the request."));
  });
});

describe("the evidence behind the verdict", () => {
  it("shows the window and how many peers the verdict compared with", () => {
    renderReport({
      ...REPORT,
      diagnosis: { ...REPORT.diagnosis, window: "7d", baseline_sample_size: 6, peer_baseline_available: true },
    });
    expect(screen.getByTestId("diagnosis-basis")).toHaveTextContent("From the 7-day window · compared with 6 comparable videos.");
  });

  it("says when there were too few peers to compare with", () => {
    renderReport({
      ...REPORT,
      diagnosis: { ...REPORT.diagnosis, window: "24h", baseline_sample_size: 2, peer_baseline_available: false },
    });
    expect(screen.getByTestId("diagnosis-basis")).toHaveTextContent(
      "From the 24-hour window · 2 comparable videos so far, too few to compare with.",
    );
  });

  it("blames the report's unknown labels, not a lack of peers, for a size of 0", () => {
    renderReport({
      ...REPORT,
      diagnosis: { ...REPORT.diagnosis, window: "24h", baseline_sample_size: 0, peer_baseline_available: false },
    });
    expect(screen.getByTestId("diagnosis-basis")).toHaveTextContent(
      "From the 24-hour window · not compared with other videos while its language and topic are unknown.",
    );
  });

  it("shows the verdict alone for a server that sends neither", () => {
    renderReport();
    expect(screen.getByText("Early read: views are building")).toBeInTheDocument();
    expect(screen.queryByTestId("diagnosis-basis")).not.toBeInTheDocument();
  });
});
