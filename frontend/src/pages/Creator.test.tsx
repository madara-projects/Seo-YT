import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import CreatorPage from "./Creator";
import { mutationKeys } from "@/hooks/queryKeys";
import { creatorFormDefaults, type CreatorFormValues } from "@/schemas/creator";
import type { AnalyzeResponse } from "@/api/types";

// Two saved packages plus a title-only variant, as `/analyze` returns them.
const RESULT: AnalyzeResponse = {
  title: "Why silence hurts more than words",
  description: "A short reflection on the things we never say.",
  tags: ["silence hurts", "unsaid words", "shorts"],
  hashtags: ["#shorts", "#silence"],
  generation_source: "gemini",
  history_run_id: 42,
  research_warnings: ["Only 2 public results matched the topic; research was limited."],
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

const SUBMITTED: CreatorFormValues = { ...creatorFormDefaults, script: "Silence says everything.", format_choice: "short" };

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

function analyzeBodies() {
  return fetchMock.mock.calls
    .filter(([url, init]) => String(url) === "/analyze" && init?.method === "POST")
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>);
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

/** A client holding a finished analysis, as if the creator had just run one. */
async function clientWithResult(result: AnalyzeResponse, variables: CreatorFormValues = SUBMITTED) {
  const client = newClient();
  await client
    .getMutationCache()
    .build(client, { mutationKey: mutationKeys.analyze, mutationFn: async () => result })
    .execute(variables);
  return client;
}

function renderWith(client: QueryClient, route: string) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <CreatorPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function renderResults(route = "/creator", result: AnalyzeResponse = RESULT) {
  return renderWith(await clientWithResult(result), route);
}

beforeEach(() => {
  localStorage.clear();
  pendingSaves = [];
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (path === "/analyze" && init?.method === "POST") return json(RESULT);
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

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Creator setup", () => {
  it("asks what is being made first, with Short chosen by default", async () => {
    renderWith(newClient(), "/creator");

    const group = await screen.findByRole("group", { name: "What are you making?" });
    expect(within(group).getByRole("radio", { name: /Short/ })).toBeChecked();
    expect(within(group).getByRole("radio", { name: /Long video/ })).not.toBeChecked();
    expect(within(group).getByRole("radio", { name: /Not sure/ })).not.toBeChecked();
    expect(screen.getByText(/#shorts in the title, a focused tag set, no chapters/)).toBeInTheDocument();
    expect(screen.getByTestId("setup-summary")).toHaveTextContent("Short · English · Global");
  });

  it("says why Generate is disabled until there is a script", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    const generate = await screen.findByRole("button", { name: "Generate package" });
    expect(generate).toBeDisabled();
    expect(generate).toHaveAccessibleDescription("Add your script or idea to generate a package.");

    await user.type(screen.getByLabelText("Script"), "Silence says everything.");

    expect(generate).toBeEnabled();
    expect(generate).toHaveAccessibleDescription(/Uses YouTube quota/);
  });

  it("sends a Short as youtube_shorts", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    await user.type(await screen.findByLabelText("Script"), "Silence says everything.");
    await user.click(screen.getByRole("button", { name: "Generate package" }));

    await waitFor(() => expect(analyzeBodies()).toHaveLength(1));
    expect(analyzeBodies()[0]).toMatchObject({ script: "Silence says everything.", video_format: "youtube_shorts" });
  });

  it.each([
    ["Tutorial", "tutorial"],
    ["Talking head", "talking_head"],
    ["Other", "long_form"],
  ])("sends a long %s as %s", async (kind, expected) => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    await user.click(await screen.findByRole("radio", { name: /Long video/ }));
    await user.click(screen.getByRole("radio", { name: kind }));
    await user.type(screen.getByLabelText("Script"), "How I edit a vlog in one hour.");
    await user.click(screen.getByRole("button", { name: "Generate package" }));

    await waitFor(() => expect(analyzeBodies()).toHaveLength(1));
    expect(analyzeBodies()[0]).toMatchObject({ video_format: expected });
  });

  it("sends long_form for a long video with no kind", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    await user.click(await screen.findByRole("radio", { name: /Long video/ }));
    expect(screen.getByText(/No #shorts; chapters only from your own timestamps/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Script"), "How I edit a vlog in one hour.");
    await user.click(screen.getByRole("button", { name: "Generate package" }));
    await waitFor(() => expect(analyzeBodies()).toHaveLength(1));
    expect(analyzeBodies()[0]).toMatchObject({ video_format: "long_form" });
  });

  it("sends no format when the creator isn't sure", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    await user.click(await screen.findByRole("radio", { name: /Not sure/ }));
    await user.type(screen.getByLabelText("Script"), "Silence says everything.");
    await user.click(screen.getByRole("button", { name: "Generate package" }));

    await waitFor(() => expect(analyzeBodies()).toHaveLength(1));
    expect(analyzeBodies()[0]).not.toHaveProperty("video_format");
  });

  it("moves between the format cards with the arrow keys", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    const short = await screen.findByRole("radio", { name: /Short/ });
    short.focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("radio", { name: /Long video/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Long video/ })).toHaveFocus();
  });

  it("remembers the last format for the next package", async () => {
    const user = userEvent.setup();
    const first = renderWith(newClient(), "/creator");
    await user.click(await screen.findByRole("radio", { name: /Long video/ }));
    await user.click(screen.getByRole("radio", { name: "Review" }));
    first.unmount();

    renderWith(newClient(), "/creator");

    expect(await screen.findByRole("radio", { name: /Long video/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Review" })).toBeChecked();
    expect(screen.getByTestId("setup-summary")).toHaveTextContent("Long video · Review · English · Global");
  });

  it("shows the Short details first and counts the ones filled", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    const trigger = await screen.findByRole("button", { name: /More details \(optional\)/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(within(trigger).getByText("None filled")).toBeInTheDocument();
    await user.click(trigger);

    const groups = screen.getAllByRole("group").filter((group) => group.getAttribute("data-testid")?.startsWith("details-"));
    expect(groups[0]).toHaveAttribute("data-testid", "details-visuals");
    await user.type(screen.getByLabelText("On-screen quote or text"), "Silence says everything.");
    await user.type(screen.getByLabelText("Who is it for?"), "Tamil quote lovers");

    expect(within(trigger).getByText("2 filled")).toBeInTheDocument();
  });

  it("puts language, the summary and Generate in a side panel on wide screens", async () => {
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(min-width: 80rem)",
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    try {
      const user = userEvent.setup();
      renderWith(newClient(), "/creator");

      const panel = await screen.findByRole("complementary", { name: "Your package" });
      expect(within(panel).getByTestId("setup-summary")).toHaveTextContent("Short · English · Global");
      expect(within(panel).getByRole("combobox", { name: "Output language" })).toBeInTheDocument();
      expect(within(panel).getByText(/#shorts in the title/)).toBeInTheDocument();
      expect(within(panel).getByRole("button", { name: "Generate package" })).toBeDisabled();
      // One Generate button and one set of language fields: no bottom bar on wide screens.
      expect(screen.queryByTestId("setup-bar")).not.toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: "Generate package" })).toHaveLength(1);

      await user.type(screen.getByLabelText("Script"), "Silence says everything.");
      expect(within(panel).getByRole("button", { name: "Generate package" })).toBeEnabled();
    } finally {
      window.matchMedia = original;
    }
  });

  it("puts audience details first for a long video", async () => {
    const user = userEvent.setup();
    renderWith(newClient(), "/creator");

    await user.click(await screen.findByRole("radio", { name: /Long video/ }));
    await user.click(screen.getByRole("button", { name: /More details \(optional\)/ }));

    const groups = screen.getAllByRole("group").filter((group) => group.getAttribute("data-testid")?.startsWith("details-"));
    expect(groups[0]).toHaveAttribute("data-testid", "details-audience");
  });
});

describe("Creator results", () => {
  it("opens on the Package tab with the result's idea, format and status", async () => {
    await renderResults();

    const header = await screen.findByRole("region", { name: "This package" });
    expect(within(header).getByText("Silence says everything.")).toBeInTheDocument();
    expect(within(header).getByText("Short")).toBeInTheDocument();
    expect(within(header).getByText("English · Global")).toBeInTheDocument();
    expect(within(header).getByText("Written with Gemini")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Package" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("package-card")).toHaveTextContent("Why silence hurts more than words");
  });

  it("keeps the tab in the URL", async () => {
    const user = userEvent.setup();
    await renderResults();

    await user.click(await screen.findByRole("tab", { name: "Compare options" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/creator?tab=compare");
    expect(await screen.findAllByTestId("package-option-card")).toHaveLength(3);
  });

  it.each([
    ["packaging", "Package"],
    ["compare", "Compare options"],
    ["research", "Research and insights"],
    ["angle", "Research and insights"],
    ["brief", "Research and insights"],
    ["decision", "Before you publish"],
    ["checklist", "Before you publish"],
  ])("opens an old ?stage=%s link on the %s tab", async (stage, tabName) => {
    await renderResults(`/creator?stage=${stage}`);

    expect(await screen.findByRole("tab", { name: tabName })).toHaveAttribute("aria-selected", "true");
  });

  it("opens an old ?stage=idea link on the setup screen", async () => {
    await renderResults("/creator?stage=idea");

    expect(await screen.findByRole("button", { name: /Back to results/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Script")).toHaveValue("Silence says everything.");
  });

  it("goes back to the setup with the values kept, and returns to the results", async () => {
    const user = userEvent.setup();
    await renderResults("/creator?tab=compare");

    await user.click(await screen.findByRole("button", { name: /Edit and regenerate/ }));

    expect(screen.getByLabelText("Script")).toHaveValue("Silence says everything.");
    expect(screen.getByRole("radio", { name: /Short/ })).toBeChecked();
    await user.click(screen.getByRole("button", { name: /Back to results/ }));
    expect(await screen.findByRole("tab", { name: "Compare options" })).toHaveAttribute("aria-selected", "true");
  });

  it("starts a new package from an empty script", async () => {
    const user = userEvent.setup();
    await renderResults();

    await user.click(await screen.findByRole("button", { name: /New package/ }));

    expect(screen.getByLabelText("Script")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Generate package" })).toBeDisabled();
  });

  it("lists the research warnings from the header", async () => {
    const user = userEvent.setup();
    await renderResults();

    await user.click(await screen.findByRole("button", { name: "1 research warning" }));

    const dialog = await screen.findByRole("dialog", { name: "Research warnings" });
    expect(within(dialog).getByText(RESULT.research_warnings![0]!)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Open research and insights" }));
    expect(screen.getByRole("tab", { name: "Research and insights" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows no package as chosen until the creator uses one", async () => {
    await renderResults("/creator?tab=compare");

    const cards = await screen.findAllByTestId("package-option-card");
    expect(cards).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Selected" })).not.toBeInTheDocument();
    expect(screen.getByText("Choose to save")).toBeInTheDocument();
    // The variant is a title only: there is no saved package to record.
    expect(within(cards[2]!).getByText("Title only")).toBeInTheDocument();
    expect(within(cards[2]!).getByRole("button", { name: "Select" })).toBeDisabled();
    expect(saves()).toHaveLength(0);
  });

  it("previews another option and uses it from the Package tab", async () => {
    const user = userEvent.setup();
    await renderResults();

    const switcher = await screen.findByTestId("package-switcher");
    await user.click(within(switcher).getByRole("radio", { name: /^Package B: Silence says everything/ }));
    expect(screen.getByTestId("package-card")).toHaveTextContent("Silence says everything");
    expect(saves()).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Use package B" }));
    await waitFor(() => expect(saves()).toEqual([{ package_id: "package-b" }]));
    pendingSaves.shift()!();

    expect(await screen.findByText("Saved to History")).toBeInTheDocument();
    expect(screen.getByTestId("use-package")).toHaveTextContent("In use");
  });

  it("won't record a title-only option", async () => {
    const user = userEvent.setup();
    await renderResults();

    const switcher = await screen.findByTestId("package-switcher");
    await user.click(within(switcher).getByRole("radio", { name: /\(title only\)/ }));

    expect(screen.getByTestId("use-package")).toBeDisabled();
    expect(screen.getByText(/A title-only option has no saved package behind it/)).toBeInTheDocument();
  });

  it("saves choices one after another, so the last click is the last write", async () => {
    const user = userEvent.setup();
    await renderResults("/creator?tab=compare");

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

  it("shows how the tags were chosen under Research and insights", async () => {
    await renderResults("/creator?tab=research");

    const panel = await screen.findByTestId("keyword-research");
    expect(within(panel).getByText("YouTube evidence")).toBeInTheDocument();
    expect(
      within(panel).getByText(/1 subject tag matches sampled public result metadata; 1 is source-only\./),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Search volume: unavailable.")).toBeInTheDocument();
  });

  it("folds the brief's provenance away under Research and insights", async () => {
    const user = userEvent.setup();
    await renderResults("/creator?tab=research", {
      ...RESULT,
      creator_brief: {
        target_audience: "Tamil quote lovers",
        field_provenance: { target_audience: { source: "inferred" } },
      },
    } as AnalyzeResponse);

    const trigger = await screen.findByRole("button", { name: /What you supplied vs inferred/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(await screen.findByText("Creator brief provenance")).toBeInTheDocument();
  });

  it("says why a first frame wasn't analysed instead of printing units on nothing", async () => {
    await renderResults("/creator?tab=research", {
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

  it("shows a quote Short's pacing under Research and insights", async () => {
    await renderResults("/creator?tab=research");

    const panel = await screen.findByTestId("pacing-analysis");
    expect(within(panel).getByRole("heading", { name: "Quote Short pacing" })).toBeInTheDocument();
    expect(within(panel).getByText("Quote length")).toBeInTheDocument();
    expect(within(panel).getByText("9 words")).toBeInTheDocument();
  });

  it("shows the decision and the checklist before publishing", async () => {
    await renderResults("/creator?tab=publish");

    expect(await screen.findByText("No decision to review yet")).toBeInTheDocument();
    expect(screen.getByText("No package chosen yet")).toBeInTheDocument();
  });
});
