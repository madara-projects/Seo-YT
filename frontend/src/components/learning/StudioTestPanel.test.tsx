import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudioTestPanel } from "./StudioTestPanel";
import type { StudioTest, StudioTestOverview } from "@/api/learningTypes";

const PKG_A = { package_id: "package-a", title: "How I Fixed My Sleep Schedule in 7 Days", thumbnail_text: "7 DAYS" };
const PKG_B = { package_id: "package-b", title: "How I Fixed My Sleep Schedule in Seven Days", thumbnail_text: "SLEEP FIXED" };
const PKG_C = { package_id: "package-c", title: "The Night Routine That Finally Worked", thumbnail_text: "IT WORKED" };
const PKG_D = { package_id: "package-d", title: "Why Your Alarm Is Not the Problem", thumbnail_text: "" };
const CANDIDATES = [PKG_A, PKG_B, PKG_C, PKG_D];

const NOTE =
  "YouTube Studio runs this test. This app never runs it; its own before/after comparisons are not equivalent to YouTube's test.";

function overview(extra: Partial<StudioTestOverview> = {}): StudioTestOverview {
  return {
    analysis_run_id: 7,
    eligible: true,
    video_format: "long_form",
    reason: null,
    min_variants: 2,
    max_variants: 3,
    candidates: CANDIDATES,
    similar_pairs: [{ first: "package-a", second: "package-b", similarity: 0.93, message: "" }],
    linked_video: null,
    tests: [],
    note: NOTE,
    ...extra,
  };
}

const TEST: StudioTest = {
  id: 11,
  analysis_run_id: 7,
  linked_video: null,
  variants: [
    { label: "A", ...PKG_A },
    { label: "B", ...PKG_C },
  ],
  status: "prepared",
  winner_variant: null,
  result: null,
  notes: "",
  created_at: "2026-09-20T10:00:00Z",
  similar_pairs: [],
};

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;
let current: StudioTestOverview;

function renderPanel(runId: number | null = 7) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <StudioTestPanel runId={runId} />
    </QueryClientProvider>,
  );
}

function calls(method: string) {
  return fetchMock.mock.calls
    .filter(([, init]) => init?.method === method)
    .map(([url, init]) => ({ url: String(url), body: JSON.parse(String(init?.body ?? "{}")) }));
}

beforeEach(() => {
  current = overview();
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") return json({ ...TEST, id: 12 }, 201);
    if (init?.method === "PATCH") return json({ ...TEST, status: "linked" });
    if (String(url) === "/api/history/runs/7/studio-tests") return json(current);
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("StudioTestPanel", () => {
  it("offers the saved packages with copy buttons and says it only records YouTube's own test", async () => {
    renderPanel();

    expect(await screen.findByText(PKG_C.title)).toBeInTheDocument();
    expect(screen.getByText("Record only")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Copy title/ })).toHaveLength(4);
    // A package without thumbnail text has nothing to copy for it.
    expect(screen.getAllByRole("button", { name: /^Copy thumbnail text/ })).toHaveLength(3);
    expect(screen.getByText(/not equivalent to YouTube's test/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save as a prepared test/ })).toBeDisabled();
  });

  it("allows at most three packages, warns about near-identical titles, and saves the choice", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText(PKG_A.title);

    await user.click(screen.getByRole("checkbox", { name: `Use "${PKG_A.title}" as a variant` }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: `Use "${PKG_B.title}" as a variant` }));
    expect(screen.getByRole("status")).toHaveTextContent("Variant A and Variant B have titles too similar");

    await user.click(screen.getByRole("checkbox", { name: `Use "${PKG_C.title}" as a variant` }));
    expect(screen.getByText("3 of 3 chosen.", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: `Use "${PKG_D.title}" as a variant` })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Save as a prepared test/ }));
    await waitFor(() => expect(calls("POST")).toHaveLength(1));
    expect(calls("POST")[0]).toEqual({
      url: "/api/history/runs/7/studio-tests",
      body: { package_ids: ["package-a", "package-b", "package-c"], notes: "" },
    });
  });

  it("shows one line for a Short instead of the test", async () => {
    current = overview({ eligible: false, video_format: "short", reason: "YouTube's Test & Compare is not available for Shorts." });
    renderPanel();

    expect(await screen.findByTestId("studio-shorts-note")).toHaveTextContent("not available for Shorts");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("says so when the package was never saved", () => {
    renderPanel(null);
    expect(screen.getByText(/not saved to History/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("links a prepared test once the package has a published video", async () => {
    const user = userEvent.setup();
    current = overview({ tests: [TEST] });
    const { unmount } = renderPanel();
    const card = await screen.findByTestId("studio-test");
    expect(within(card).getByText("Prepared, not linked")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /Link to published video/ })).toBeDisabled();
    expect(within(card).getByText(/After publishing, link the video/)).toBeInTheDocument();
    unmount();

    current = overview({ tests: [TEST], linked_video: { link_id: 3, youtube_video_id: "sleepvideo1" } });
    renderPanel();
    await user.click(within(await screen.findByTestId("studio-test")).getByRole("button", { name: /Link to published video/ }));
    await waitFor(() => expect(calls("PATCH")).toHaveLength(1));
    expect(calls("PATCH")[0]).toEqual({ url: "/api/studio-tests/11", body: { link_video: true } });
  });

  it("records the result read in Studio", async () => {
    const user = userEvent.setup();
    const linked = { ...TEST, status: "linked", linked_video: { link_id: 3, youtube_video_id: "sleepvideo1" } };
    current = overview({ tests: [linked], linked_video: linked.linked_video });
    renderPanel();

    await user.click(within(await screen.findByTestId("studio-test")).getByRole("button", { name: "Record Studio result" }));
    const form = screen.getByRole("form", { name: "Record the Studio result of test 11" });
    const save = within(form).getByRole("button", { name: "Save result" });
    expect(save).toBeDisabled();

    await user.click(within(form).getByRole("radio", { name: "A winner" }));
    expect(save).toBeDisabled();
    await user.click(within(form).getByRole("radio", { name: "Variant B" }));
    await user.type(within(form).getByLabelText("Variant A (%)"), "41.2");
    await user.type(within(form).getByLabelText("Variant B (%)"), "58.8");
    await user.type(within(form).getByLabelText("Notes"), "B won");
    await user.click(save);

    await waitFor(() => expect(calls("PATCH")).toHaveLength(1));
    expect(calls("PATCH")[0]).toEqual({
      url: "/api/studio-tests/11",
      body: { outcome: "winner", winner_variant: "B", watch_time_share: { A: 41.2, B: 58.8 }, notes: "B won" },
    });
  });

  it("shows a recorded result", async () => {
    current = overview({
      tests: [
        {
          ...TEST,
          status: "completed",
          linked_video: { link_id: 3, youtube_video_id: "sleepvideo1" },
          winner_variant: null,
          result: { outcome: "no_clear_winner", watch_time_share: { A: 50, B: 50 } },
        },
      ],
    });
    renderPanel();
    const card = await screen.findByTestId("studio-test");
    expect(within(card).getByText("Result recorded")).toBeInTheDocument();
    expect(within(card).getByText("No clear winner · watch-time share A 50.0% · B 50.0%")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Correct the Studio result" })).toBeInTheDocument();
  });

  it("never moves a recorded result to a video linked later", async () => {
    current = overview({
      tests: [{ ...TEST, status: "completed", winner_variant: "B", result: { outcome: "winner", watch_time_share: { A: 40, B: 60 } } }],
      linked_video: { link_id: 4, youtube_video_id: "sleepvideo2" },
    });
    renderPanel();
    const card = await screen.findByTestId("studio-test");
    expect(within(card).getByText(/read for a video that is no longer linked/)).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /Link to published video/ })).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /Studio result/ })).not.toBeInTheDocument();
  });
});
