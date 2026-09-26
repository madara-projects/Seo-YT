import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import CreatorPage from "./Creator";
import { mutationKeys } from "@/hooks/queryKeys";
import { creatorFormDefaults } from "@/schemas/creator";
import type { AnalyzeResponse } from "@/api/types";

// Two saved packages plus a title-only variant, as `/analyze` returns them.
const RESULT: AnalyzeResponse = {
  title: "Why silence hurts more than words",
  description: "A short reflection on the things we never say.",
  tags: ["silence hurts", "unsaid words", "shorts"],
  hashtags: ["#shorts", "#silence"],
  generation_source: "gemini",
  history_run_id: 42,
  title_variants: ["The words I never said"],
  title_thumbnail_packages: [
    { package_id: "package-a", title: "Why silence hurts more than words", quality_status: "approved", misleading_risk: "low" },
    { package_id: "package-b", title: "Silence says everything", quality_status: "approved", misleading_risk: "low" },
  ],
  keyword_research: {
    status: "youtube_evidence",
    confidence: "observed_youtube_relevance",
    selected_keywords: [
      { keyword: "silence hurts", classification: "topic", evidence_count: 2 },
      { keyword: "unsaid words", classification: "emotion", evidence_count: 0 },
      { keyword: "shorts", classification: "platform_format", evidence_count: 5 },
    ],
  },
  pacing_analysis: {
    analysis_type: "quote_short",
    pace_label: "reflective",
    avg_sentence_length: 9,
    hook_density: "single emotional hook",
    recommendation: "Show the quote within the first second.",
  },
};

let fetchMock: ReturnType<typeof vi.fn>;
/** Answers to selection saves, released one at a time by the test. */
let pendingSaves: Array<() => void>;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function saves() {
  return fetchMock.mock.calls
    .filter(([url, init]) => String(url) === "/api/history/runs/42/selection" && init?.method === "PUT")
    .map(([, init]) => JSON.parse(String(init?.body)) as { package_id: string });
}

/** A client holding a finished analysis, as if the creator had just run one. */
async function clientWithResult(result: AnalyzeResponse) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  await client
    .getMutationCache()
    .build(client, { mutationKey: mutationKeys.analyze, mutationFn: async () => result })
    .execute({ ...creatorFormDefaults, script: "Silence says everything.", video_format: "youtube_shorts" });
  return client;
}

async function renderCreator(route: string, result: AnalyzeResponse = RESULT) {
  const client = await clientWithResult(result);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <CreatorPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  pendingSaves = [];
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (path === "/api/history/runs/42" && (init?.method ?? "GET") === "GET") {
      return json({ id: 42, selected_package: null });
    }
    if (path === "/api/history/runs/42/selection" && init?.method === "PUT") {
      return new Promise((resolve) => {
        pendingSaves.push(() => resolve(json({ status: "selected" })));
      });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("CreatorPage", () => {
  it("shows no package as selected until the creator chooses one", async () => {
    await renderCreator("/creator?stage=compare");

    const cards = await screen.findAllByTestId("package-option-card");
    expect(cards).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Selected" })).not.toBeInTheDocument();
    expect(screen.getByText("Choose to save")).toBeInTheDocument();
    // The variant is a title only: there is no saved package to record.
    expect(within(cards[2]!).getByText("Title only")).toBeInTheDocument();
    expect(within(cards[2]!).getByRole("button", { name: "Select" })).toBeDisabled();
    expect(saves()).toHaveLength(0);
  });

  it("saves choices one after another, so the last click is the last write", async () => {
    const user = userEvent.setup();
    await renderCreator("/creator?stage=compare");

    await user.click(await screen.findByTestId("select-package-a"));
    await user.click(screen.getByTestId("select-package-b"));

    // The second save waits for the first to answer.
    await waitFor(() => expect(saves()).toHaveLength(1));
    expect(screen.getByText("Saving selection")).toBeInTheDocument();
    pendingSaves.shift()!();

    await waitFor(() => expect(saves()).toHaveLength(2));
    expect(saves().map((body) => body.package_id)).toEqual(["package-a", "package-b"]);
    pendingSaves.shift()!();

    expect(await screen.findByText("Selection saved")).toBeInTheDocument();
    expect(screen.getByTestId("select-package-b")).toHaveTextContent(/^Selected$/);
    expect(screen.getByTestId("select-package-a")).toHaveTextContent(/^Select$/);
  });

  it("shows how the tags were chosen on the Packaging stage", async () => {
    await renderCreator("/creator?stage=packaging");

    const panel = await screen.findByTestId("keyword-research");
    expect(within(panel).getByText("YouTube evidence")).toBeInTheDocument();
    expect(
      within(panel).getByText(/1 subject tag matches sampled public result metadata; 1 is source-only\./),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Search volume: unavailable.")).toBeInTheDocument();
  });

  it("says why a first frame wasn't analysed instead of printing units on nothing", async () => {
    await renderCreator("/creator?stage=angle", {
      ...RESULT,
      retention_assistant: {
        risk_level: "low",
        opening: { status: "available", score: 72, clarity: "clear", specificity: "specific" },
        first_frame: {
          status: "unavailable",
          reason: "No on-screen text or first-visual description was supplied.",
          score: null,
        },
        pacing: {
          status: "available",
          format_assessment: "long_form_or_unspecified",
          word_count: 42,
          timing_confidence: "relative_stage_only",
        },
        quote_presentation: { status: "unavailable" },
      },
    } as AnalyzeResponse);

    expect(await screen.findByText("No on-screen text or first-visual description was supplied.")).toBeInTheDocument();
    expect(screen.getByText("42 words · timing relative stage only")).toBeInTheDocument();
    expect(screen.queryByText(/Unavailable words|Unavailables/)).not.toBeInTheDocument();
  });

  it("shows a quote Short's pacing on the Angle stage", async () => {
    await renderCreator("/creator?stage=angle");

    const panel = await screen.findByTestId("pacing-analysis");
    expect(within(panel).getByRole("heading", { name: "Quote Short pacing" })).toBeInTheDocument();
    expect(within(panel).getByText("Quote length")).toBeInTheDocument();
    expect(within(panel).getByText("9 words")).toBeInTheDocument();
  });
});
