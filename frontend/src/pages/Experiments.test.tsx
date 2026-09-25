import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ExperimentsPage from "./Experiments";
import { EXPERIMENT_RESULT_FIXTURE } from "@/test/fixtures/experiment";

const CHANNEL_ID = "UCzU9GK79bxzBfBYrc_D9jjg";

// Shaped like `AuditExperimentStore.experiment` output.
const EXPERIMENT = {
  id: 3,
  name: "Question titles vs statements",
  description: "",
  hypothesis: "Question titles may be associated with a higher average view percentage on Shorts.",
  mode: "controlled",
  status: "active",
  variable: "title_mechanism",
  variable_category: "title_mechanism",
  control_definition: "A plain statement title",
  variant_definition: "The same idea asked as a question",
  success_metric: "average_view_percentage",
  secondary_metrics: ["views"],
  target_sample_size: null,
  minimum_sample_size: 5,
  observation_window: "24h",
  start_date: null,
  end_date: null,
  notes: "",
  created_at: "2026-09-10T09:00:00+00:00",
  updated_at: "2026-09-24T09:30:00+00:00",
  assignments: [
    { id: 101, published_video_link_id: 5, role: "control", assigned_at: "2026-09-11T09:00:00+00:00", notes: "", youtube_video_id: "z4HKMfQ3nJc", published_at: "2026-09-07T11:50:35Z", title: "a mere heart that ponders" },
    { id: 102, published_video_link_id: 6, role: "variant", assigned_at: "2026-09-12T09:00:00+00:00", notes: "", youtube_video_id: "KhtCgbdlZgI", published_at: "2026-09-08T11:50:35Z", title: "Does silence hurt more than words?" },
  ],
  latest_result: EXPERIMENT_RESULT_FIXTURE as unknown,
  assignment_counts: { control: 1, variant: 1, observational_reference: 0 },
};

type ExperimentRecord = typeof EXPERIMENT;

let experiments: ExperimentRecord[];
let connected: boolean;
let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function calls(method: string, path: string) {
  return fetchMock.mock.calls.filter(([url, init]) => String(url) === path && (init?.method ?? "GET") === method);
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderPage(route = "/experiments") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route
            path="/experiments"
            element={
              <>
                <ExperimentsPage />
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
  experiments = [structuredClone(EXPERIMENT)];
  connected = true;
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path === "/youtube/channel/status") {
      return json({ configured: true, connected, channel: connected ? { id: CHANNEL_ID, title: "Kind of Lost" } : null });
    }
    if (path === "/api/audits") {
      return json({
        candidates: [
          { id: 5, analysis_run_id: 9, youtube_video_id: "z4HKMfQ3nJc", ownership_verified: true, verified_channel_id: CHANNEL_ID, audit_state: "not_run", evidence_state: "mature", youtube_metadata: { title: "a mere heart that ponders" } },
          { id: 7, analysis_run_id: 11, youtube_video_id: "dQw4w9WgXcQ", ownership_verified: true, verified_channel_id: CHANNEL_ID, audit_state: "not_run", evidence_state: "mature", youtube_metadata: { title: "Why silence hurts more than words" } },
        ],
        total: 2,
      });
    }
    const base = "/api/experiment-center/experiments";
    if ((path === base || path.startsWith(`${base}?`)) && method === "GET") {
      return json({ experiments, total: experiments.length });
    }
    if (path === base && method === "POST") {
      const body = JSON.parse(String(init?.body));
      const created = { ...structuredClone(EXPERIMENT), ...body, id: 4, assignments: [], latest_result: null, assignment_counts: { control: 0, variant: 0 } };
      experiments = [created, ...experiments];
      return json({ status: "created", experiment: created }, 201);
    }
    const match = path.match(/^\/api\/experiment-center\/experiments\/(\d+)(\/[a-z]+)?(?:\/(\d+))?$/);
    if (match) {
      const experiment = experiments.find((item) => item.id === Number(match[1]));
      if (!experiment) return json({ detail: "Experiment not found." }, 404);
      const action = match[2];
      if (!action && method === "GET") return json({ experiment, result_versions: [{ id: 21, captured_at: EXPERIMENT_RESULT_FIXTURE.captured_at, result_state: "directional_variant" }] });
      if (!action && method === "PATCH") {
        Object.assign(experiment, JSON.parse(String(init?.body)));
        return json({ status: "updated", experiment });
      }
      if (action === "/compare") return json({ status: "compared", result: EXPERIMENT_RESULT_FIXTURE, experiment }, 201);
      if (action === "/assignments" && method === "DELETE") {
        experiment.assignments = experiment.assignments.filter((item) => item.id !== Number(match[3]));
        return json({ status: "removed", assignment_id: Number(match[3]) });
      }
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("ExperimentsPage", () => {
  it("invites a first comparison only when there are none", async () => {
    experiments = [];
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Start only with a real question")).toBeInTheDocument();
    expect(screen.getByText(/No comparisons yet/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "New experiment" })[1]!);
    expect(await screen.findByRole("dialog", { name: "Test one decision at a time" })).toBeInTheDocument();
  });

  it("checks the form before creating anything", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "New experiment" }));
    const form = await screen.findByTestId("experiment-form");
    await user.click(within(form).getByRole("button", { name: "Create comparison" }));

    expect(await within(form).findByText("Name the comparison.")).toBeInTheDocument();
    expect(within(form).getByText("Describe the one thing you change.")).toBeInTheDocument();
    expect(calls("POST", "/api/experiment-center/experiments")).toHaveLength(0);
  });

  it("creates a draft comparison and opens it", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "New experiment" }));
    const form = await screen.findByTestId("experiment-form");
    await user.type(within(form).getByLabelText("Name"), "Hook in the first second");
    await user.type(within(form).getByLabelText("Hypothesis"), "Text on the first frame may keep viewers longer.");
    await user.type(within(form).getByLabelText("Control"), "Open on the visual");
    await user.type(within(form).getByLabelText("Variant"), "Open on text over black");
    await user.click(within(form).getByRole("button", { name: "Create comparison" }));

    await waitFor(() => expect(calls("POST", "/api/experiment-center/experiments")).toHaveLength(1));
    expect(JSON.parse(String(calls("POST", "/api/experiment-center/experiments")[0]![1]?.body))).toEqual({
      name: "Hook in the first second",
      hypothesis: "Text on the first frame may keep viewers longer.",
      mode: "controlled",
      variable: "title_mechanism",
      control_definition: "Open on the visual",
      variant_definition: "Open on text over black",
      success_metric: "average_view_percentage",
      observation_window: "24h",
      status: "draft",
    });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/experiments?experiment=4"));
    const detail = await screen.findByTestId("experiment-detail");
    expect(within(detail).getByRole("heading", { name: "Hook in the first second" })).toBeInTheDocument();
    expect(within(detail).getByText(/Not compared yet/)).toBeInTheDocument();
  });

  it("shows both sides and what the saved evidence says", async () => {
    renderPage("/experiments?experiment=3");

    const detail = await screen.findByTestId("experiment-detail");
    expect(within(within(detail).getByTestId("group-control")).getByText("a mere heart that ponders")).toBeInTheDocument();
    expect(within(within(detail).getByTestId("group-variant")).getByText("Does silence hurt more than words?")).toBeInTheDocument();
    const result = within(detail).getByTestId("experiment-result");
    expect(within(result).getByText("Variant ahead")).toBeInTheDocument();
    expect(within(result).getByText("60.0%")).toBeInTheDocument();
    expect(within(result).getByText("68.0%")).toBeInTheDocument();
    expect(within(result).getByText("+13.3%")).toBeInTheDocument();
    expect(within(result).getByText(/not causal proof/)).toBeInTheDocument();
    expect(within(result).getByText("1 saved comparison. Results never change YouTube or your future packages on their own.")).toBeInTheDocument();
  });

  it("asks before completing, which can't be undone", async () => {
    const user = userEvent.setup();
    renderPage("/experiments?experiment=3");

    await user.click(await screen.findByRole("button", { name: "Mark completed" }));
    const dialog = await screen.findByRole("dialog", { name: "Mark completed?" });
    expect(calls("PATCH", "/api/experiment-center/experiments/3")).toHaveLength(0);

    await user.click(within(dialog).getByRole("button", { name: "Mark completed" }));
    await waitFor(() => expect(calls("PATCH", "/api/experiment-center/experiments/3")).toHaveLength(1));
    expect(JSON.parse(String(calls("PATCH", "/api/experiment-center/experiments/3")[0]![1]?.body))).toEqual({ status: "completed" });
    expect(await screen.findByText("This comparison is closed, so it takes no new videos.")).toBeInTheDocument();
  });

  it("pauses without asking, since it can resume", async () => {
    const user = userEvent.setup();
    renderPage("/experiments?experiment=3");

    await user.click(await screen.findByRole("button", { name: "Pause" }));

    await waitFor(() => expect(calls("PATCH", "/api/experiment-center/experiments/3")).toHaveLength(1));
    expect(await screen.findByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("compares saved evidence and removes an assignment", async () => {
    const user = userEvent.setup();
    renderPage("/experiments?experiment=3");

    await user.click(await screen.findByRole("button", { name: "Compare saved evidence" }));
    await waitFor(() => expect(calls("POST", "/api/experiment-center/experiments/3/compare")).toHaveLength(1));

    await user.click(screen.getByRole("button", { name: "Remove a mere heart that ponders" }));
    await waitFor(() => expect(calls("DELETE", "/api/experiment-center/experiments/3/assignments/101")).toHaveLength(1));
  });

  it("explains why videos can't be assigned without a connected channel", async () => {
    connected = false;
    renderPage("/experiments?experiment=3");

    expect(await screen.findByText(/Connect your channel to assign videos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare saved evidence" })).toBeDisabled();
  });
});
