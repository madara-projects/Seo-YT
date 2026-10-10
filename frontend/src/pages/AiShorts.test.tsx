import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import AiShortsPage from "./AiShorts";
import { invalidatePackageViews } from "@/hooks/queryKeys";
import { AI_SHORTS_FALLBACK_PLAN, AI_SHORTS_PLAN, AI_SHORTS_PLAN_SUMMARIES } from "@/test/fixtures/aiShorts";
import type { AiShortsPlanSummary } from "@/api/aiShortsTypes";

const QUOTE = AI_SHORTS_PLAN.quote;

type MockResponse = { ok: boolean; status: number; text: () => Promise<string> };

function json(body: unknown, status = 200): MockResponse {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

let fetchMock: ReturnType<typeof vi.fn>;
let plans: AiShortsPlanSummary[];
/** Plans deleted on the server, from this page or from History; reading one is a 404. */
let deleted: Set<number>;
/** What `POST /api/ai-shorts/generate` answers; tests swap it for a draft or a failure. */
let generateResponse: () => MockResponse;
let writeText: ReturnType<typeof vi.fn>;

function calls(method: string, path: string | RegExp) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const requested = String(url);
    const matches = typeof path === "string" ? requested === path : path.test(requested);
    return matches && (init?.method ?? "GET") === method;
  });
}

function generateBodies() {
  return calls("POST", "/api/ai-shorts/generate").map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>);
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

/** Pass the client of an earlier render to come back to the page with the app's cache. */
function renderPage(route = "/ai-shorts", client = newClient()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AiShortsPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * A user whose copies land in `writeText`. user-event's `setup()` installs its
 * own clipboard stub, so the mock is put back after it.
 */
function setupUser() {
  const user = userEvent.setup();
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return user;
}

/** Types a valid quote and asks for the prompts. */
async function generate(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Quote"), QUOTE);
  await user.click(screen.getByRole("button", { name: "Write Flow prompts" }));
}

beforeEach(() => {
  plans = [...AI_SHORTS_PLAN_SUMMARIES];
  deleted = new Set();
  generateResponse = () => json(AI_SHORTS_PLAN);
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path === "/api/ai-shorts/generate" && method === "POST") return generateResponse();
    if (path.startsWith("/api/ai-shorts/plans?") && method === "GET") return json({ plans });
    const detail = path.match(/^\/api\/ai-shorts\/plans\/(\d+)$/);
    if (detail && method === "GET") {
      const id = Number(detail[1]);
      if (id === AI_SHORTS_PLAN.id && !deleted.has(id)) return json(AI_SHORTS_PLAN);
      if (id === AI_SHORTS_FALLBACK_PLAN.id && !deleted.has(id)) return json(AI_SHORTS_FALLBACK_PLAN);
      return json({ error: { code: "not_found", message: "AI Short not found.", request_id: "req-404" } }, 404);
    }
    if (detail && method === "DELETE") {
      deleted.add(Number(detail[1]));
      plans = plans.filter((plan) => plan.id !== Number(detail[1]));
      return { ok: true, status: 204, text: async () => "" };
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);

  // jsdom has no clipboard; the CopyButton prefers this API when it exists.
  writeText = vi.fn().mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (navigator as { clipboard?: unknown }).clipboard;
});

describe("AI Shorts form", () => {
  it("provides independent desktop scroll containers with keyboard-accessible results", () => {
    renderPage();
    expect(screen.getByTestId("ai-shorts-input-scroll")).toHaveClass("lg:overflow-y-auto", "lg:min-h-0");
    expect(screen.getByRole("region", { name: "AI Shorts results" })).toHaveClass("lg:overflow-y-auto", "lg:min-h-0");
    expect(screen.getByRole("region", { name: "AI Shorts results" })).toHaveAttribute("tabindex", "0");
  });

  it("explains the flow before the first run and keeps the button disabled with the reason", async () => {
    const user = setupUser();
    renderPage();

    expect(await screen.findByRole("heading", { name: "AI Shorts", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Quote in, Short out")).toBeInTheDocument();

    const button = screen.getByRole("button", { name: "Write Flow prompts" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("Type the quote first.");

    await user.type(screen.getByLabelText("Quote"), "Short");
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("The quote needs at least 6 characters.");

    await user.type(screen.getByLabelText("Quote"), " words");
    expect(button).toBeEnabled();
    expect(button).toHaveAccessibleDescription("Uses up to 6 Gemini calls. No YouTube Data API quota; tags are checked against free YouTube search suggestions.");
    // Only the recent list was read; nothing was generated.
    expect(generateBodies()).toHaveLength(0);
  });

  it("defaults to two parts and sends the chosen parts, mood and language", async () => {
    const user = setupUser();
    renderPage();

    expect(await screen.findByRole("radio", { name: "2 parts · 16 s" })).toBeChecked();
    await user.click(screen.getByRole("radio", { name: "3 parts · 24 s" }));
    await user.type(screen.getByLabelText(/Mood or scene wish/), "rain on a window");
    await generate(user);

    await waitFor(() => expect(generateBodies()).toHaveLength(1));
    expect(generateBodies()[0]).toEqual({
      quote: QUOTE,
      language: "english",
      parts: 3,
      mood_hint: "rain on a window",
      region: "global",
    });
  });
});

describe("AI Shorts results", () => {
  it("writes both prompts, the Flow steps and the package, and copies the first prompt", async () => {
    const user = setupUser();
    renderPage();
    await generate(user);

    const header = await screen.findByRole("region", { name: "This AI Short" });
    expect(within(header).getByText(`“${QUOTE}”`)).toBeInTheDocument();
    expect(within(header).getByText("2 parts · 16 s")).toBeInTheDocument();
    expect(within(header).getByText("Written with Gemini")).toBeInTheDocument();
    expect(within(header).getByText("Passed with 1 warning")).toBeInTheDocument();
    expect(within(header).getByText(AI_SHORTS_PLAN.checks!.warnings![0]!)).toBeInTheDocument();
    expect(within(header).getByRole("link", { name: "Open in History" })).toHaveAttribute("href", "/history?run=4201");
    // The new plan is in the URL, so it can be linked to and survives a reload.
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/ai-shorts?plan=31"));

    const prompts = screen.getAllByTestId("shot-prompt");
    expect(prompts).toHaveLength(2);
    expect(prompts[0]).toHaveTextContent(AI_SHORTS_PLAN.shots[0]!.prompt);
    expect(prompts[1]).toHaveTextContent(AI_SHORTS_PLAN.shots[1]!.prompt);
    expect(screen.getByRole("heading", { name: "Part 1 · 8 s · Text to Video" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Part 2 · 8 s · Extend from Part 1" })).toBeInTheDocument();
    expect(screen.getByText(/Same table, same framing and light as Part 1/)).toBeInTheDocument();

    const guide = screen.getByTestId("flow-guide");
    expect(within(guide).getByText(AI_SHORTS_PLAN.flow_steps![0]!)).toBeInTheDocument();
    expect(within(guide).getByText(AI_SHORTS_PLAN.cautions![1]!)).toBeInTheDocument();
    expect(within(guide).getByText("0 / 6 done")).toBeInTheDocument();

    expect(within(screen.getByTestId("mood-audio")).getByText(AI_SHORTS_PLAN.mood!.visual_metaphor!)).toBeInTheDocument();
    const overlay = screen.getByTestId("text-overlay");
    expect(within(overlay).getByText("they would have never told you.")).toBeInTheDocument();
    // The rule a Short is judged by sits above the plan: the first line is there from the first frame.
    expect(within(overlay).getByRole("note", { name: "First-frame rule" })).toHaveTextContent(
      /on screen from the very first frame, large and high-contrast\. No typing animation and no fade-in/,
    );

    const pkg = screen.getByTestId("shorts-package");
    expect(within(pkg).getByText(AI_SHORTS_PLAN.package!.title!)).toBeInTheDocument();
    expect(within(pkg).getByText("Passed quality check")).toBeInTheDocument();
    expect(within(pkg).getAllByTestId("title-option")).toHaveLength(3);
    expect(within(pkg).getByText("#betrayal")).toBeInTheDocument();
    expect(within(pkg).getByRole("button", { name: "Copy upload package" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Copy prompt for Part 1" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(AI_SHORTS_PLAN.shots[0]!.prompt));
    // The name stays stable for assistive tech; the visible text confirms the copy.
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy prompt for Part 1" })).toHaveTextContent("Copied"));
  });

  it("says the package makes no YouTube Data API research but checks tags against search suggestions", async () => {
    const user = setupUser();
    renderPage();
    await generate(user);

    const pkg = await screen.findByTestId("shorts-package");
    expect(within(pkg).getByText(/makes no YouTube Data API research/)).toBeInTheDocument();
    expect(within(pkg).getByText(/checked against YouTube.s free search suggestions/)).toBeInTheDocument();
    expect(within(pkg).queryByText(/no YouTube search research/)).not.toBeInTheDocument();
  });

  it("shows how Gemini read the quote: meaning, emotion, tone, the chosen scene and how viewers search for it", async () => {
    const direction = {
      quote_meaning: "Guarding yourself by acting numb so nobody can hurt you again.",
      scene: "A lone figure seen from behind walks along an empty pier at blue dusk.",
      why_it_fits: "Walking alone in the cold reads as guarded solitude at a glance.",
      opening: "The figure walks slowly.",
      middle: "Wind moves their jacket.",
      ending: "They keep walking toward the grey sea.",
      emotion: "guarded, numb after heartbreak",
      tone: "numb",
      search_themes: ["heartbreak quotes", "emotional numbness", "sad quotes"],
    };
    generateResponse = () => json({ ...AI_SHORTS_PLAN, creative_direction: direction });
    const user = setupUser();
    renderPage();
    await generate(user);

    const mood = await screen.findByTestId("mood-audio");
    expect(within(mood).getByText(direction.quote_meaning)).toBeInTheDocument();
    expect(within(mood).getByText(direction.emotion)).toBeInTheDocument();
    expect(within(mood).getByText("numb")).toBeInTheDocument();
    expect(within(mood).getByText(direction.scene)).toBeInTheDocument();
    for (const theme of direction.search_themes) expect(within(mood).getByText(theme)).toBeInTheDocument();
  });

  it("still shows Gemini's reading of the quote when its scene was thrown away as a symbol", async () => {
    const understanding = {
      quote_meaning: "Acting numb so nobody can hurt you again.",
      emotion: "guarded numbness",
      tone: "numb",
      search_themes: ["heartbreak quotes", "emotional numbness"],
    };
    generateResponse = () => json({ ...AI_SHORTS_PLAN, creative_direction: undefined, quote_understanding: understanding });
    const user = setupUser();
    renderPage();
    await generate(user);

    const mood = await screen.findByTestId("mood-audio");
    expect(within(mood).getByText(understanding.quote_meaning)).toBeInTheDocument();
    expect(within(mood).getByText("guarded numbness")).toBeInTheDocument();
    expect(within(mood).getByText("emotional numbness")).toBeInTheDocument();
    // No scene was kept, so there is no scene or visible action to show.
    expect(within(mood).queryByText("Chosen scene")).not.toBeInTheDocument();
    expect(within(mood).queryByText("Visible action")).not.toBeInTheDocument();
  });

  it("shows a plan written before the planner read emotion, tone and search themes", async () => {
    const { emotion: _e, tone: _t, search_themes: _s, ...older } = {
      quote_meaning: "Old meaning.", scene: "Old scene.", why_it_fits: "Old reason.",
      opening: "a", middle: "b", ending: "c", emotion: "x", tone: "sad", search_themes: ["y"],
    };
    generateResponse = () => json({ ...AI_SHORTS_PLAN, creative_direction: older });
    const user = setupUser();
    renderPage();
    await generate(user);

    const mood = await screen.findByTestId("mood-audio");
    expect(within(mood).getByText("Old meaning.")).toBeInTheDocument();
    expect(within(mood).queryByText("Tone")).not.toBeInTheDocument();
    expect(within(mood).queryByText("How viewers search for it")).not.toBeInTheDocument();
  });

  it("copies every prompt labelled by part, and the package in the shared upload format", async () => {
    const user = setupUser();
    renderPage();
    await generate(user);
    await screen.findByRole("region", { name: "This AI Short" });

    await user.click(screen.getByRole("button", { name: "Copy all prompts" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const [all] = writeText.mock.calls[0] as [string];
    expect(all).toContain("PART 1 · 8 S · TEXT TO VIDEO\n");
    expect(all).toContain("PART 2 · 8 S · EXTEND FROM PART 1\n");

    await user.click(screen.getByRole("button", { name: "Copy upload package" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
    const [bundle] = writeText.mock.calls[1] as [string];
    expect(bundle.split("\n").slice(0, 2)).toEqual(["TITLE", AI_SHORTS_PLAN.package!.title]);
    expect(bundle).toContain("\nTAGS\nbetrayal quotes, quote shorts, trust, shorts\n");
    expect(bundle).toContain("\nHASHTAGS\n#shorts #betrayal #quotes");
  });

  it("copies tags as one comma-separated line and hashtags space-separated, with no comma inside a tag", async () => {
    // Two published videos ended up with "deep quotes," as a tag: a generator
    // can leave the comma inside the text, and YouTube splits a paste on commas only.
    generateResponse = () =>
      json({
        ...AI_SHORTS_PLAN,
        package: {
          ...AI_SHORTS_PLAN.package,
          tags: ["deep quotes,", "betrayal quotes", "quote shorts,\ntrust", "Deep Quotes"],
          hashtags: ["#shorts,", "betrayal", "#quotes"],
        },
      });
    const user = setupUser();
    renderPage();
    await generate(user);
    const pkg = await screen.findByTestId("shorts-package");

    // What is shown is what is copied: the count on screen is the count pasted.
    expect(within(pkg).getByText("Video tags").nextElementSibling).toHaveTextContent("4");
    expect(within(pkg).getByText("deep quotes")).toBeInTheDocument();
    expect(within(pkg).queryByText("deep quotes,")).not.toBeInTheDocument();

    await user.click(within(pkg).getByRole("button", { name: "Copy tags" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("deep quotes, betrayal quotes, quote shorts, trust"));

    await user.click(within(pkg).getByRole("button", { name: "Copy hashtags" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("#shorts #betrayal #quotes"));

    await user.click(within(pkg).getByRole("button", { name: "Copy upload package" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(3));
    const [bundle] = writeText.mock.calls[2] as [string];
    expect(bundle).toContain("\nTAGS\ndeep quotes, betrayal quotes, quote shorts, trust\n");
    expect(bundle).not.toMatch(/,\n/);
  });

  it("lets the creator tick the Flow steps on this screen", async () => {
    const user = setupUser();
    renderPage();
    await generate(user);
    const guide = await screen.findByTestId("flow-guide");

    await user.click(within(guide).getByRole("checkbox", { name: /Step 1:/ }));
    await user.click(within(guide).getByRole("checkbox", { name: /Step 3:/ }));

    expect(within(guide).getByText("2 / 6 done")).toBeInTheDocument();
    // Ticking is local; nothing is written anywhere.
    expect(fetchMock.mock.calls.every(([, init]) => (init?.method ?? "GET") !== "PATCH" && (init?.method ?? "GET") !== "PUT")).toBe(true);
  });

  it("labels a built-in template draft and offers to retry with Gemini", async () => {
    generateResponse = () => json(AI_SHORTS_FALLBACK_PLAN);
    const user = setupUser();
    renderPage();
    await generate(user);

    const header = await screen.findByRole("region", { name: "This AI Short" });
    expect(within(header).getByText("Draft: built-in template")).toBeInTheDocument();
    expect(within(header).getByText(/Gemini was unavailable/)).toBeInTheDocument();
    expect(within(screen.getByTestId("shorts-package")).getByText("Quality check: review warnings")).toBeInTheDocument();

    generateResponse = () => json(AI_SHORTS_PLAN);
    await user.click(within(header).getByRole("button", { name: "Retry with Gemini" }));

    await waitFor(() => expect(generateBodies()).toHaveLength(2));
    expect(generateBodies()[1]).toMatchObject({ quote: QUOTE, parts: 2, language: "english" });
    expect(await screen.findByText("Written with Gemini")).toBeInTheDocument();
  });

  it("retries a saved draft with the mood hint it was written with, not the one now in the form", async () => {
    const user = setupUser();
    renderPage("/ai-shorts?plan=32");
    const header = await screen.findByRole("region", { name: "This AI Short" });
    await user.type(screen.getByLabelText(/Mood or scene wish/), "a sunlit meadow");

    await user.click(within(header).getByRole("button", { name: "Retry with Gemini" }));

    await waitFor(() => expect(generateBodies()).toHaveLength(1));
    expect(generateBodies()[0]).toEqual({
      quote: QUOTE,
      language: "english",
      parts: 2,
      mood_hint: "rain on a window",
      region: "global",
    });
  });

  it("shows a failure with its request ID and retries the same request", async () => {
    generateResponse = () =>
      json({ error: { code: "gemini_unavailable", message: "Gemini did not answer.", request_id: "req-9" } }, 502);
    const user = setupUser();
    renderPage();
    await generate(user);

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Gemini did not answer.")).toBeInTheDocument();
    expect(within(alert).getByText("Request ID: req-9")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-results")).not.toBeInTheDocument();

    generateResponse = () => json(AI_SHORTS_PLAN);
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("region", { name: "This AI Short" })).toBeInTheDocument();
    expect(generateBodies()).toHaveLength(2);
    expect(generateBodies()[1]).toEqual(generateBodies()[0]);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the progress note while the prompts are written", async () => {
    let finish: (() => void) | undefined;
    generateResponse = () => {
      throw new Error("unused");
    };
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (String(url) === "/api/ai-shorts/generate" && init?.method === "POST") {
        return new Promise<MockResponse>((resolve) => {
          finish = () => resolve(json(AI_SHORTS_PLAN));
        });
      }
      return json({ plans });
    });
    const user = setupUser();
    renderPage();
    await generate(user);

    expect(await screen.findByText("Writing prompts and package…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Writing…" })).toBeDisabled();

    finish?.();
    expect(await screen.findByRole("region", { name: "This AI Short" })).toBeInTheDocument();
  });
});

describe("Recent AI Shorts", () => {
  it("lists the saved plans, newest first, with a way into History", async () => {
    renderPage();

    const rows = await screen.findAllByTestId("ai-shorts-plan");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("2 parts · 16 s");
    expect(within(rows[0]!).getByText("Gemini")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("Some silences are louder than words.");
    expect(within(rows[1]!).getByText("Draft")).toBeInTheDocument();
    expect(within(rows[1]!).getByRole("link", { name: /Open in History/ })).toHaveAttribute("href", "/history?run=4199");
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/ai-shorts/plans?limit=20");
  });

  it("shows a dash for a plan whose total length the server could not read", async () => {
    // The total comes from the stored plan JSON; damaged, it is null.
    plans = [{ ...AI_SHORTS_PLAN_SUMMARIES[0]!, total_seconds: null }];
    renderPage();

    const [row] = await screen.findAllByTestId("ai-shorts-plan");
    expect(row).toHaveTextContent("2 parts · —");
    expect(row).not.toHaveTextContent("null");
  });

  it("opens a plan from the list and from a ?plan= link", async () => {
    const user = setupUser();
    renderPage();

    const rows = await screen.findAllByTestId("ai-shorts-plan");
    // The row itself; its Delete button is named after the quote too.
    await user.click(within(rows[0]!).getByRole("button", { name: /^“The biggest betrayal/ }));

    expect(await screen.findByRole("region", { name: "This AI Short" })).toHaveTextContent(QUOTE);
    expect(screen.getByTestId("location")).toHaveTextContent("/ai-shorts?plan=31");
    expect(calls("GET", "/api/ai-shorts/plans/31")).toHaveLength(1);
    expect(within(rows[0]!).getByRole("button", { name: /^“The biggest betrayal/ })).toHaveAttribute("aria-current", "true");
  });

  it("opens the plan named in the URL", async () => {
    renderPage("/ai-shorts?plan=32");

    expect(await screen.findByRole("region", { name: "This AI Short" })).toHaveTextContent("Draft: built-in template");
    expect(screen.queryByText("Quote in, Short out")).not.toBeInTheDocument();
  });

  it("says when a linked plan is gone", async () => {
    renderPage("/ai-shorts?plan=99");

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("AI Short not found.")).toBeInTheDocument();
    expect(within(alert).getByText("Request ID: req-404")).toBeInTheDocument();
  });

  it("asks before deleting, deletes nothing on cancel, and removes the plan on confirm", async () => {
    const user = setupUser();
    renderPage();
    const rows = await screen.findAllByTestId("ai-shorts-plan");
    const opener = within(rows[1]!).getByRole("button", { name: /^Delete: Some silences/ });

    await user.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "Delete this AI Short?" });
    expect(within(dialog).getByText(/Some silences are louder than words/)).toBeInTheDocument();
    // Focus starts on Cancel, so Enter straight away never deletes.
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls("DELETE", /\/api\/ai-shorts\/plans\/\d+$/)).toHaveLength(0);
    expect(opener).toHaveFocus();

    await user.click(opener);
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(calls("DELETE", "/api/ai-shorts/plans/30")).toHaveLength(1));
    await waitFor(() => expect(screen.getAllByTestId("ai-shorts-plan")).toHaveLength(1));
    expect(screen.queryByText("Some silences are louder than words.")).not.toBeInTheDocument();
  });

  it("closes the open plan when it is the one deleted", async () => {
    const user = setupUser();
    renderPage("/ai-shorts?plan=31");
    await screen.findByRole("region", { name: "This AI Short" });

    await user.click(screen.getByRole("button", { name: /^Delete: The biggest betrayal/ }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.queryByRole("region", { name: "This AI Short" })).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^\/ai-shorts$/));
    expect(await screen.findByText("Quote in, Short out")).toBeInTheDocument();
  });

  it("does not bring a deleted AI Short back as an error after leaving the page and returning", async () => {
    const user = setupUser();
    const client = newClient();
    const first = renderPage("/ai-shorts", client);
    await generate(user);
    await screen.findByRole("region", { name: "This AI Short" });

    await user.click(screen.getByRole("button", { name: /^Delete: The biggest betrayal/ }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Quote in, Short out")).toBeInTheDocument();
    first.unmount();
    const reads = calls("GET", "/api/ai-shorts/plans/31").length;

    // Back within the half hour the finished generate run stays cached.
    renderPage("/ai-shorts", client);
    expect(await screen.findByText("Quote in, Short out")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // The deleted plan is not asked for again.
    expect(calls("GET", "/api/ai-shorts/plans/31")).toHaveLength(reads);
  });

  it("shows the empty page, not an error, when the last run's plan was deleted from History", async () => {
    const user = setupUser();
    const client = newClient();
    const first = renderPage("/ai-shorts", client);
    await generate(user);
    await screen.findByRole("region", { name: "This AI Short" });
    first.unmount();

    // History deletes the run, the server's cascade takes the plan, and History
    // refreshes every view of packages.
    deleted.add(AI_SHORTS_PLAN.id);
    invalidatePackageViews(client);

    renderPage("/ai-shorts", client);
    expect(await screen.findByText("Quote in, Short out")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "This AI Short" })).not.toBeInTheDocument();
  });

  it("reports an empty list and a failed list honestly", async () => {
    plans = [];
    const first = renderPage();
    expect(await screen.findByText(/No AI Shorts yet/)).toBeInTheDocument();
    first.unmount();

    fetchMock.mockImplementation(async (url: string) =>
      String(url).startsWith("/api/ai-shorts/plans?")
        ? json({ error: { code: "database_unavailable", message: "The database is unavailable.", request_id: "req-3" } }, 503)
        : json({}),
    );
    renderPage();
    expect(await screen.findByText("The database is unavailable.")).toBeInTheDocument();
  });
});
