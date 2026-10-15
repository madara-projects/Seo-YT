import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PlanView } from "./PlanView";
import { AI_SHORTS_FALLBACK_PLAN, AI_SHORTS_LEGACY_PLAN, AI_SHORTS_PLAN } from "@/test/fixtures/aiShorts";
import type { AiShortsPlan } from "@/api/aiShortsTypes";

const TAB_KEY = "win-engine-ai-shorts-tab";

let writeText: ReturnType<typeof vi.fn>;

/** user-event's `setup()` installs its own clipboard stub, so the mock is put back after it. */
function setupUser() {
  const user = userEvent.setup();
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return user;
}

function renderView(props: Partial<Parameters<typeof PlanView>[0]> = {}) {
  const view = (next: Partial<Parameters<typeof PlanView>[0]>) => (
    <MemoryRouter>
      <PlanView plan={AI_SHORTS_PLAN} {...props} {...next} />
    </MemoryRouter>
  );
  const result = render(view({}));
  return { ...result, rerenderWith: (next: Partial<Parameters<typeof PlanView>[0]>) => result.rerender(view(next)) };
}

async function openTab(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(screen.getByRole("tab", { name }));
}

/** The last thing copied. */
async function copied(): Promise<string> {
  await waitFor(() => expect(writeText).toHaveBeenCalled());
  return writeText.mock.calls.at(-1)![0] as string;
}

beforeEach(() => {
  localStorage.clear();
  writeText = vi.fn().mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  delete (navigator as { clipboard?: unknown }).clipboard;
});

describe("PlanView header", () => {
  it("shows the quote, one meta line, and a status that opens to the real warnings", async () => {
    const user = setupUser();
    const onRetry = vi.fn();
    renderView({ onRetry });

    const header = screen.getByRole("region", { name: "This AI Short" });
    expect(within(header).getByText(`“${AI_SHORTS_PLAN.quote}”`)).toBeInTheDocument();
    const meta = within(header).getByTestId("plan-meta");
    expect(within(meta).getByText("2 parts · 16 s")).toBeInTheDocument();
    expect(within(meta).getByText("English")).toBeInTheDocument();
    expect(within(meta).getByText("Written with Gemini")).toBeInTheDocument();

    // Closed until asked: the warning is one click away, the fix is not among them.
    const status = within(header).getByRole("button", { name: "1 thing to check" });
    expect(status).toHaveAttribute("aria-expanded", "false");
    expect(within(header).queryByText(AI_SHORTS_PLAN.checks!.warnings![0]!)).not.toBeInTheDocument();
    await user.click(status);
    expect(status).toHaveAttribute("aria-expanded", "true");
    const list = within(header).getByRole("list", { name: "Things to check" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(list).toHaveTextContent(AI_SHORTS_PLAN.checks!.warnings![0]!);
    expect(header).not.toHaveTextContent(/added a calm upper-middle/);

    expect(within(header).getByRole("link", { name: "Open in History" })).toHaveAttribute("href", "/history?run=4201");
    await user.click(within(header).getByRole("button", { name: "Write again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("is ready when the only notes are fixes the planner made itself", () => {
    renderView({ plan: { ...AI_SHORTS_PLAN, checks: { passed: true, warnings: ["Part 1: added a calm upper-middle"] } } });

    const header = screen.getByRole("region", { name: "This AI Short" });
    expect(within(header).getByText("Ready")).toBeInTheDocument();
    // Nothing to open, and the package (passed) has nothing to flag.
    expect(within(header).queryByRole("button", { name: /Ready/ })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Upload package" })).toBeInTheDocument();
    expect(screen.queryByTestId("package-notes-badge")).not.toBeInTheDocument();
  });

  it("counts the package's quality notes too, apart from the prompts', and flags the Upload package tab", async () => {
    const user = setupUser();
    // Plan 10: the prompts' only notes were fixes, but the package's quality check asks for a review.
    renderView({
      plan: {
        ...AI_SHORTS_LEGACY_PLAN,
        checks: { passed: true, warnings: ["Part 1: added a calm upper-middle, audio line"] },
        package: {
          ...AI_SHORTS_PLAN.package,
          generation_quality: {
            verdict: "YELLOW",
            issues: [],
            warnings: [
              { code: "fewer_legitimate_alternatives", message: "Only 2 materially distinct title alternative(s) passed; the result was not padded." },
              { code: "sparse_subject_tags", message: "Add a phrase viewers search for this quote's own theme before uploading." },
            ],
          },
        },
      },
    });

    const header = screen.getByRole("region", { name: "This AI Short" });
    const status = within(header).getByRole("button", { name: "2 things to check" });
    expect(status.className).toMatch(/tone-warn/);
    await user.click(status);
    expect(within(header).getByTestId("status-group-prompts")).toHaveTextContent("Nothing to check.");
    const notes = within(header).getByRole("list", { name: "Package notes" });
    expect(within(notes).getAllByRole("listitem")).toHaveLength(2);
    expect(notes).toHaveTextContent("Only 2 materially distinct title alternative(s) passed");

    // Seen from the Prompts tab too.
    const tab = screen.getByRole("tab", { name: "Upload package (2 notes)" });
    expect(within(tab).getByTestId("package-notes-badge")).toHaveTextContent("2");
    await user.click(within(header).getByRole("button", { name: "Open Upload package" }));
    expect(tab).toHaveAttribute("aria-selected", "true");
    expect(within(screen.getByTestId("shorts-package")).getByText("Quality check: review warnings")).toBeInTheDocument();
  });

  it("opens a failed check by itself", () => {
    renderView({ plan: { ...AI_SHORTS_PLAN, checks: { passed: false, issues: ["Part 2: Gemini returned no prompt"], warnings: [] } } });

    const header = screen.getByRole("region", { name: "This AI Short" });
    expect(within(header).getByRole("button", { name: "1 thing to check" })).toHaveAttribute("aria-expanded", "true");
    const list = within(header).getByRole("list", { name: "Things to check" });
    expect(list).toHaveTextContent("Part 2");
    expect(list).toHaveTextContent("Gemini returned no prompt.");
  });

  it("names a template draft and offers Gemini in its place", () => {
    renderView({ plan: AI_SHORTS_FALLBACK_PLAN, onRetry: vi.fn() });

    const header = screen.getByRole("region", { name: "This AI Short" });
    expect(within(header).getByText("Draft: built-in template")).toBeInTheDocument();
    expect(within(header).getByText(/Gemini was unavailable/)).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Retry with Gemini" })).toBeEnabled();
  });

  it("leaves out Write again and Open in History in History's own view", () => {
    renderView({ context: "history", onRetry: vi.fn() });

    const header = screen.getByRole("region", { name: "This AI Short" });
    expect(within(header).queryByRole("button", { name: /Write again|Retry with Gemini/ })).not.toBeInTheDocument();
    expect(within(header).queryByRole("link", { name: "Open in History" })).not.toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Copy all prompts" })).toBeInTheDocument();
  });

  it("disables Write again while another plan is being written", () => {
    renderView({ onRetry: vi.fn(), retrying: true });

    expect(screen.getByRole("button", { name: "Write again" })).toBeDisabled();
  });
});

describe("PlanView tabs", () => {
  it("opens on Prompts, switches by click and by arrow key, and remembers the last tab", async () => {
    const user = setupUser();
    const { unmount } = renderView();

    const tablist = screen.getByRole("tablist", { name: "AI Short sections" });
    expect(within(tablist).getAllByRole("tab").map((tab) => tab.getAttribute("aria-controls")?.replace(/^.*-content-/, ""))).toEqual([
      "prompts",
      "package",
      "flow",
      "notes",
    ]);
    expect(screen.getByRole("tab", { name: "Make it in Flow (0 of 6 steps done)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Prompts" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByTestId("shot-card")).toHaveLength(2);

    await openTab(user, /Upload package/);
    expect(screen.getByRole("tab", { name: "Upload package" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("shorts-package")).toBeInTheDocument();
    expect(screen.queryByTestId("shot-card")).not.toBeInTheDocument();
    expect(localStorage.getItem(TAB_KEY)).toBe("package");

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Make it in Flow/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Make it in Flow/ })).toHaveFocus();
    expect(screen.getByTestId("flow-guide")).toBeInTheDocument();
    expect(localStorage.getItem(TAB_KEY)).toBe("flow");

    unmount();
    renderView({ plan: AI_SHORTS_LEGACY_PLAN });
    expect(screen.getByRole("tab", { name: /Make it in Flow/ })).toHaveAttribute("aria-selected", "true");
  });

  it("still works when storage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const user = setupUser();
    renderView();

    expect(screen.getByRole("tab", { name: "Prompts" })).toHaveAttribute("aria-selected", "true");
    await openTab(user, /Scene notes/);
    expect(screen.getByTestId("scene-notes")).toBeInTheDocument();
  });
});

describe("Prompts tab", () => {
  it("shows a sectioned prompt as labelled rows and copies the prompt itself", async () => {
    const user = setupUser();
    renderView();

    const [first, second] = screen.getAllByTestId("shot-card");
    expect(within(first!).getByRole("heading", { name: "Part 1 · 0–8 s · Text to video" })).toBeInTheDocument();
    expect(within(first!).getByText("The table, before")).toBeInTheDocument();
    expect(within(second!).getByRole("heading", { name: "Part 2 · 8–16 s · Extend Part 1" })).toBeInTheDocument();

    const rows = within(first!).getAllByTestId("prompt-section");
    expect(rows.map((row) => within(row).getByRole("term").textContent)).toEqual([
      "Shot",
      "Subject",
      "Setting",
      "Light",
      "Look",
      "Keep out",
    ]);
    expect(within(rows[2]!).getByRole("definition")).toHaveTextContent("A dim kitchen at night.");
    expect(within(second!).getByText("Action")).toBeInTheDocument();
    expect(within(second!).getByText(/Same table, same framing and light as Part 1/)).toBeInTheDocument();

    await user.click(within(first!).getByRole("button", { name: "Copy prompt for Part 1" }));
    expect(await copied()).toBe(AI_SHORTS_PLAN.shots[0]!.prompt);
    await user.click(within(second!).getByRole("button", { name: "Copy prompt for Part 2" }));
    expect(await copied()).toBe(AI_SHORTS_PLAN.shots[1]!.prompt);
  });

  it("shows an older prompt as readable paragraphs", () => {
    renderView({ plan: AI_SHORTS_LEGACY_PLAN });

    const prompt = within(screen.getAllByTestId("shot-card")[0]!).getByTestId("shot-prompt");
    expect(within(prompt).queryByRole("term")).not.toBeInTheDocument();
    const paragraphs = prompt.querySelectorAll("p");
    expect(paragraphs.length).toBeGreaterThan(1);
    expect(Array.from(paragraphs, (paragraph) => paragraph.textContent).join(" ")).toBe(AI_SHORTS_LEGACY_PLAN.shots[0]!.prompt);
    // Read in the body font, not the monospace of code.
    expect(prompt.className).not.toMatch(/font-mono/);
  });

  it("copies every prompt labelled by part from the header", async () => {
    const user = setupUser();
    renderView();

    await user.click(screen.getByRole("button", { name: "Copy all prompts" }));
    const text = await copied();
    expect(text.startsWith(`PART 1 · 0–8 S · TEXT TO VIDEO\n${AI_SHORTS_PLAN.shots[0]!.prompt}\n\n`)).toBe(true);
    expect(text).toContain(`PART 2 · 8–16 S · EXTEND PART 1\n${AI_SHORTS_PLAN.shots[1]!.prompt}`);
  });

  it("puts each part's on-screen words on its card, with the first-frame rule on Part 1", async () => {
    const user = setupUser();
    renderView();

    const [first, second] = screen.getAllByTestId("shot-card");
    const firstOverlay = within(first!).getByTestId("shot-overlay");
    expect(firstOverlay).toHaveTextContent("On screen 0–8 s");
    expect(within(firstOverlay).getByText("The biggest betrayal is knowing")).toBeInTheDocument();
    expect(within(firstOverlay).getByRole("note", { name: "First-frame rule" })).toHaveTextContent(
      /on screen from the very first frame, large and high-contrast\. No typing animation and no fade-in/,
    );
    const secondOverlay = within(second!).getByTestId("shot-overlay");
    expect(secondOverlay).toHaveTextContent("On screen 8–16 s");
    expect(within(secondOverlay).queryByRole("note")).not.toBeInTheDocument();

    await user.click(within(secondOverlay).getByRole("button", { name: "Copy on-screen text for Part 2" }));
    expect(await copied()).toBe("that if you didn't find out,\nthey would have never told you.");
  });

  it("shows the planner's fixes as a quiet line on their part, never as a warning", async () => {
    const user = setupUser();
    renderView({ plan: AI_SHORTS_LEGACY_PLAN });

    const [first, second] = screen.getAllByTestId("shot-card");
    const firstFix = within(first!).getByTestId("shot-adjustments");
    expect(firstFix).toHaveTextContent(
      "Adjusted automatically: added a calm upper-middle, audio line, no dialogue, narration or music",
    );
    expect(firstFix).toHaveClass("text-muted-foreground");
    expect(firstFix.className).not.toMatch(/tone-warn/);
    expect(within(second!).getByTestId("shot-adjustments")).toHaveTextContent("Adjusted automatically: trimmed from 131 to 118 words");

    // Only the real warning is counted and listed.
    const header = screen.getByRole("region", { name: "This AI Short" });
    await user.click(within(header).getByRole("button", { name: "1 thing to check" }));
    const list = within(header).getByRole("list", { name: "Things to check" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(list).toHaveTextContent("Part 2");
    expect(list).toHaveTextContent("Prompt names no camera move.");
    expect(list).not.toHaveTextContent(/added|trimmed/);
  });

  it("folds the avoid list away, with its own copy", async () => {
    const user = setupUser();
    renderView();

    const avoid = screen.getByTestId("avoid-list");
    const toggle = within(avoid).getByRole("button", { name: "Avoid list" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(avoid).queryByText(AI_SHORTS_PLAN.negative_prompt!)).not.toBeInTheDocument();

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(within(avoid).getByText(AI_SHORTS_PLAN.negative_prompt!)).toBeInTheDocument();

    await user.click(within(avoid).getByRole("button", { name: "Copy avoid list" }));
    expect(await copied()).toBe(AI_SHORTS_PLAN.negative_prompt);
  });

  it("sums up the scene with its tone and emotion", () => {
    renderView({
      plan: {
        ...AI_SHORTS_PLAN,
        creative_direction: {
          quote_meaning: "Meaning.",
          scene: "A lone runner climbs an empty hill path at dawn.",
          why_it_fits: "Why.",
          opening: "a",
          middle: "b",
          ending: "c",
          emotion: "quiet resolve",
          tone: "hopeful",
        },
      },
    });

    const summary = screen.getByTestId("scene-summary");
    expect(summary).toHaveTextContent("Scene: A lone runner climbs an empty hill path at dawn.");
    expect(within(summary).getByTitle("Tone")).toHaveTextContent("hopeful");
    expect(within(summary).getByTitle("Emotion")).toHaveTextContent("quiet resolve");
  });
});

describe("Upload package tab", () => {
  it("sums up the quality check honestly and copies the chosen title in the package", async () => {
    const user = setupUser();
    renderView();
    await openTab(user, /Upload package/);

    const pkg = screen.getByTestId("shorts-package");
    const quality = within(pkg).getByRole("region", { name: "Quality check" });
    expect(within(quality).getByText("Passed quality check")).toBeInTheDocument();
    expect(within(quality).getByText("The title, description and tags stay true to the quote.")).toBeInTheDocument();
    expect(quality).toHaveTextContent(/not predicted views/);
    expect(quality).toHaveTextContent(/makes no YouTube Data API research/);

    const options = within(pkg).getAllByTestId("title-option");
    expect(options).toHaveLength(3);
    const radios = within(pkg).getAllByRole("radio");
    expect(radios[0]).toBeChecked();
    expect(within(options[0]!).getByText("In the package")).toBeInTheDocument();

    await user.click(within(options[1]!).getByRole("button", { name: "Copy title: They would have never told you" }));
    expect(await copied()).toBe("They would have never told you");

    await user.click(radios[1]!);
    expect(radios[1]).toBeChecked();
    await user.click(within(pkg).getByRole("button", { name: "Copy upload package" }));
    expect((await copied()).split("\n").slice(0, 2)).toEqual(["TITLE", "They would have never told you"]);

    // The choice survives a look at another tab.
    await openTab(user, /Prompts/);
    await openTab(user, /Upload package/);
    expect(screen.getAllByRole("radio")[1]).toBeChecked();
  });

  it("copies the description, hashtags and tags field by field", async () => {
    const user = setupUser();
    renderView();
    await openTab(user, /Upload package/);
    const pkg = screen.getByTestId("shorts-package");

    await user.click(within(pkg).getByRole("button", { name: "Copy description" }));
    expect(await copied()).toBe(AI_SHORTS_PLAN.package!.description);
    await user.click(within(pkg).getByRole("button", { name: "Copy hashtags" }));
    expect(await copied()).toBe("#shorts #betrayal #quotes");
    await user.click(within(pkg).getByRole("button", { name: "Copy tags" }));
    expect(await copied()).toBe("betrayal quotes, quote shorts, trust, shorts");
  });

  it("says when a plan has no package", async () => {
    const user = setupUser();
    renderView({ plan: { ...AI_SHORTS_PLAN, package: undefined } });
    await openTab(user, /Upload package/);

    expect(screen.getByText("No package was returned for this plan.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy upload package" })).not.toBeInTheDocument();
  });
});

describe("Make it in Flow tab", () => {
  const plan: AiShortsPlan = {
    ...AI_SHORTS_PLAN,
    flow_steps: ["1. Open Flow at flow.google and create a project.", "2. Paste the Part 1 prompt and generate.", "3. Click Extend and paste the Part 2 prompt, then generate."],
  };

  it("numbers the steps once and puts the prompt a step pastes one click away", async () => {
    const user = setupUser();
    renderView({ plan });
    await openTab(user, /Make it in Flow/);

    const guide = screen.getByTestId("flow-guide");
    expect(within(guide).getByRole("checkbox", { name: "Step 1: Open Flow at flow.google and create a project." })).toBeInTheDocument();
    expect(within(guide).queryByText(/^1\. Open Flow/)).not.toBeInTheDocument();
    expect(within(guide).getByText(AI_SHORTS_PLAN.cautions![0]!)).toBeInTheDocument();

    await user.click(within(guide).getByRole("button", { name: "Copy Part 2 prompt" }));
    expect(await copied()).toBe(AI_SHORTS_PLAN.shots[1]!.prompt);
  });

  it("keeps the ticks through a tab change and starts afresh for another plan", async () => {
    const user = setupUser();
    const { rerenderWith } = renderView({ plan });
    await openTab(user, /Make it in Flow/);

    await user.click(screen.getByRole("checkbox", { name: /^Step 1:/ }));
    await user.click(screen.getByRole("checkbox", { name: /^Step 3:/ }));
    expect(screen.getByText("2 / 3 done")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Make it in Flow/ })).toHaveTextContent("2/3");

    await openTab(user, /Prompts/);
    await openTab(user, /Make it in Flow/);
    expect(screen.getByRole("checkbox", { name: /^Step 1:/ })).toBeChecked();
    expect(screen.getByText("2 / 3 done")).toBeInTheDocument();

    rerenderWith({ plan: { ...plan, id: 99 } });
    expect(screen.getByText("0 / 3 done")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /^Step 1:/ })).not.toBeChecked();
  });
});

describe("Scene notes tab", () => {
  it("lays out the reading, the scene, the look and the sound as a definition list", async () => {
    const user = setupUser();
    renderView({
      plan: {
        ...AI_SHORTS_PLAN,
        creative_direction: {
          quote_meaning: "Finding out is the betrayal.",
          scene: "A phone face-down on a kitchen table.",
          why_it_fits: "An unread message is what was never said.",
          opening: "The kitchen is dark.",
          middle: "The screen lights once.",
          ending: "It goes out.",
          emotion: "quiet betrayal",
          tone: "sad",
          search_themes: ["betrayal quotes", "trust issues"],
        },
      },
    });
    await openTab(user, /Scene notes/);

    const notes = screen.getByTestId("scene-notes");
    const terms = within(notes).getAllByRole("term").map((term) => term.textContent);
    expect(terms).toEqual([
      "Quote meaning",
      "Emotion",
      "Tone",
      "Chosen scene",
      "Why this scene fits",
      "Visible action",
      "How viewers search for it",
      "Feeling",
      "Pace",
      "Visual metaphor",
      "Palette",
      "Keywords",
      "Audio",
    ]);
    expect(within(notes).getByText("An unread message is what was never said.")).toBeInTheDocument();
    expect(within(notes).getByText("trust issues")).toBeInTheDocument();
    expect(within(notes).getByText("late night")).toBeInTheDocument();
    expect(within(notes).getByText(AI_SHORTS_PLAN.audio!.description!)).toBeInTheDocument();
  });
});
