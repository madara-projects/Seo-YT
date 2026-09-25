import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AuditsPage from "./Audits";
import { AUDIT_FIXTURE } from "@/test/fixtures/audit";

// Shaped like `AuditExperimentStore.audit_candidates` rows.
const AUDITED = {
  id: 5,
  analysis_run_id: 42,
  youtube_video_id: "z4HKMfQ3nJc",
  published_at: "2026-09-07T11:50:35Z",
  selected_title: "Silence says everything 💔 #shorts",
  package_topic: "Silence says everything 💔 #shorts",
  youtube_metadata: { title: "Silence says everything 💔 #shorts" },
  latest_performance: { views: 3105, snapshot_window: "current", captured_at: "2026-09-24T09:00:00+00:00" },
  ownership_verified: true,
  verified_channel_id: "UCzU9GK79bxzBfBYrc_D9jjg",
  audit_id: 9,
  audit_captured_at: AUDIT_FIXTURE.captured_at,
  audit_state: "mature_observation",
  evidence_state: "observed",
  idea: { id: 7, topic: "Why silence hurts more than words" },
};

const NOT_RUN = {
  ...AUDITED,
  id: 6,
  analysis_run_id: 43,
  youtube_video_id: "KhtCgbdlZgI",
  youtube_metadata: { title: "Letters I never sent" },
  latest_performance: null,
  ownership_verified: false,
  audit_id: null,
  audit_captured_at: null,
  audit_state: "not_run",
  evidence_state: "unavailable",
  idea: null,
};

let candidates: (typeof AUDITED)[];
let connected: boolean;
let refreshFails = false;
let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function calls(method: string, path: string) {
  return fetchMock.mock.calls.filter(([url, init]) => String(url) === path && (init?.method ?? "GET") === method);
}

function renderPage(route = "/audits") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/audits" element={<AuditsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  candidates = [structuredClone(AUDITED), structuredClone(NOT_RUN) as unknown as typeof AUDITED];
  connected = true;
  refreshFails = false;
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path === "/youtube/channel/status") {
      return json({ configured: true, connected, channel: connected ? { id: AUDITED.verified_channel_id, title: "Kind of Lost" } : null });
    }
    if (path.startsWith("/api/audits?") || path === "/api/audits") {
      return json({ candidates, total: candidates.length });
    }
    const detail = path.match(/^\/api\/audits\/(\d+)(\/refresh)?$/);
    if (detail) {
      const id = Number(detail[1]);
      if (detail[2] && method === "POST") {
        if (refreshFails) return json({ detail: "The linked video is no longer available to the connected YouTube account." }, 400);
        const audit = { ...AUDIT_FIXTURE, id: 10, video: { ...AUDIT_FIXTURE.video, link_id: id, analysis_run_id: 43 } };
        return json(
          {
            status: "audited",
            audit,
            versions: [{ id: 10, captured_at: AUDIT_FIXTURE.captured_at, summary_state: "mature_observation" }],
            video_refresh: { captured: [{ snapshot_window: "7d" }] },
          },
          201,
        );
      }
      if (id === 5) {
        return json({
          audit: AUDIT_FIXTURE,
          versions: [
            { id: 9, captured_at: AUDIT_FIXTURE.captured_at, summary_state: "mature_observation" },
            { id: 4, captured_at: "2026-09-10T09:00:00+00:00", summary_state: "observable" },
          ],
          status: "available",
        });
      }
      return json({ audit: null, versions: [], status: "not_run" });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("AuditsPage", () => {
  it("lists linked published videos with their audit state", async () => {
    renderPage();

    const items = await screen.findAllByTestId("audit-candidate");
    expect(items).toHaveLength(2);
    expect(within(items[0]!).getByText("Mature observation")).toBeInTheDocument();
    expect(within(items[0]!).getByText("Verified")).toBeInTheDocument();
    expect(within(items[1]!).getByText("Not audited")).toBeInTheDocument();
    expect(screen.getByText("2 published videos")).toBeInTheDocument();
  });

  it("explains where published videos come from when there are none", async () => {
    candidates = [];
    renderPage();

    expect(await screen.findByText(/use Link on the package in History/)).toBeInTheDocument();
  });

  it("compares what went live with the saved package, field by field", async () => {
    renderPage("/audits?link=5");

    const detail = await screen.findByTestId("audit-detail");
    expect(within(detail).getByText("Differences found")).toBeInTheDocument();
    expect(
      within(detail).getByText(/differs from the saved package in: description, hashtags\./),
    ).toBeInTheDocument();
    const fields = within(detail).getAllByTestId("audit-field");
    expect(fields.map((field) => within(field).getAllByText(/Matches|Changed/)[0]!.textContent)).toEqual([
      "Matches",
      "Changed",
      "Matches",
      "Changed",
    ]);
    expect(within(fields[3]!).getByText("#shorts, #tamilquotes, #silence, #mounam")).toBeInTheDocument();
    // Two completed windows; the 28-day one hasn't come due.
    expect(within(detail).getByText(`${(812).toLocaleString()} views`)).toBeInTheDocument();
    expect(within(detail).getByText("Not complete yet")).toBeInTheDocument();
    expect(within(detail).getByText("No explicit generated-package selection was recorded.")).toBeInTheDocument();
    expect(within(detail).getByText("Audit history (2)")).toBeInTheDocument();
    expect(within(detail).getByRole("link", { name: "Active topic" })).toHaveAttribute("href", "/demand?snapshot=12");
  });

  it("runs the first audit of a video", async () => {
    const user = userEvent.setup();
    renderPage("/audits?link=6");

    const detail = await screen.findByTestId("audit-detail");
    expect(within(detail).getByText("What an audit does")).toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Run audit" }));

    await waitFor(() => expect(calls("POST", "/api/audits/6/refresh")).toHaveLength(1));
    expect(await within(detail).findByText("Differences found")).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "Refresh audit" })).toBeInTheDocument();
  });

  it("points to the channel connection instead of offering an audit that can't run", async () => {
    connected = false;
    renderPage("/audits?link=6");

    const detail = await screen.findByTestId("audit-detail");
    expect(await within(detail).findByRole("link", { name: /Connect your channel/ })).toHaveAttribute("href", "/channel");
    expect(within(detail).queryByRole("button", { name: "Run audit" })).not.toBeInTheDocument();
    expect(screen.getByText("Channel not connected")).toBeInTheDocument();
  });

  it("reports a failed refresh", async () => {
    refreshFails = true;
    const user = userEvent.setup();
    renderPage("/audits?link=5");

    await user.click(await screen.findByRole("button", { name: "Refresh audit" }));

    expect(
      await screen.findByText("The linked video is no longer available to the connected YouTube account."),
    ).toBeInTheDocument();
  });
});
