import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { THEME_TRANSITION_MS, ThemeProvider, useTheme } from "./theme";

const originalMatchMedia = window.matchMedia;
/** jsdom has no View Transitions; the tests add and remove a stand-in. */
function setStartViewTransition(value: unknown) {
  (document as unknown as { startViewTransition?: unknown }).startViewTransition = value;
}

function media(reducedMotion: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reducedMotion && query === "(prefers-reduced-motion: reduce)",
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function Toggle() {
  const { resolvedTheme, toggle } = useTheme();
  return <button onClick={toggle}>{resolvedTheme}</button>;
}

function renderToggle() {
  render(
    <ThemeProvider>
      <Toggle />
    </ThemeProvider>,
  );
  return screen.getByRole("button");
}

const root = document.documentElement;

beforeEach(() => {
  localStorage.setItem("win-engine-theme", "light");
  media(false);
});

afterEach(() => {
  window.matchMedia = originalMatchMedia;
  Reflect.deleteProperty(document, "startViewTransition");
  root.classList.remove("dark", "theme-transition", "theme-snap");
  localStorage.clear();
  vi.useRealTimers();
});

describe("theme switching", () => {
  it("gives every element one shared colour transition when View Transitions are missing", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const button = renderToggle();

    await user.click(button);

    expect(root).toHaveClass("dark");
    expect(root).toHaveClass("theme-transition");
    act(() => {
      vi.advanceTimersByTime(THEME_TRANSITION_MS);
    });
    expect(root).not.toHaveClass("theme-transition");
  });

  it("cross-fades with a View Transition and holds element transitions off meanwhile", async () => {
    let finish: () => void = () => undefined;
    const start = vi.fn((update: () => void) => {
      // The snapshot is taken with every element's own transition off.
      expect(root).toHaveClass("theme-snap");
      update();
      return {
        ready: Promise.resolve(),
        finished: new Promise<void>((resolve) => {
          finish = resolve;
        }),
      };
    });
    setStartViewTransition(start);
    const user = userEvent.setup();
    const button = renderToggle();

    await user.click(button);

    expect(start).toHaveBeenCalledTimes(1);
    expect(root).toHaveClass("dark");
    expect(root).not.toHaveClass("theme-transition");
    await act(async () => finish());
    expect(root).not.toHaveClass("theme-snap");
  });

  it("switches at once with reduced motion", async () => {
    media(true);
    const start = vi.fn();
    setStartViewTransition(start);
    const user = userEvent.setup();
    const button = renderToggle();

    await user.click(button);

    expect(root).toHaveClass("dark");
    expect(start).not.toHaveBeenCalled();
    expect(root).not.toHaveClass("theme-transition");
    expect(root).not.toHaveClass("theme-snap");
  });
});
