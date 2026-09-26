import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "win-engine-theme";

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    /* Private mode or blocked storage: fall back to the system preference. */
  }
  return "system";
}

/** How long a theme switch takes; the CSS in styles/index.css uses the same. */
export const THEME_TRANSITION_MS = 250;

type ViewTransition = { finished: Promise<void>; ready: Promise<void> };
type TransitionDocument = Document & { startViewTransition?: (update: () => void) => ViewTransition };

let switching = 0;
let fallbackTimer: number | undefined;

/**
 * Changes the theme as one smooth step instead of letting each element with
 * its own colour transition animate on its own timing while the rest snaps,
 * which read as a stutter. Where the browser has View Transitions the old
 * and new pages cross-fade, with element transitions held off underneath;
 * elsewhere every element shares one 250 ms colour transition for the
 * switch. With reduced motion the theme changes at once. `apply` runs inside
 * `flushSync`, so the DOM has changed by the time the new page is captured.
 */
export function transitionTheme(apply: () => void): void {
  const root = document.documentElement;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    flushSync(apply);
    return;
  }

  const doc = document as TransitionDocument;
  if (typeof doc.startViewTransition === "function") {
    switching += 1;
    root.classList.add("theme-snap");
    const done = () => {
      switching -= 1;
      if (switching <= 0) root.classList.remove("theme-snap");
    };
    try {
      const transition = doc.startViewTransition(() => flushSync(apply));
      // A switch cut short by the next one rejects `ready`; that is expected.
      transition.ready.catch(() => undefined);
      transition.finished.then(done, done);
    } catch {
      flushSync(apply);
      done();
    }
    return;
  }

  root.classList.add("theme-transition");
  flushSync(apply);
  window.clearTimeout(fallbackTimer);
  fallbackTimer = window.setTimeout(() => root.classList.remove("theme-transition"), THEME_TRANSITION_MS);
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (event: MediaQueryListEvent) => transitionTheme(() => setSystemDark(event.matches));
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);

  const resolvedTheme: "light" | "dark" =
    theme === "system" ? (systemDark ? "dark" : "light") : theme;

  // A layout effect, so the class changes within the commit a switch flushes.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolvedTheme === "dark");
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  const setTheme = useCallback((next: Theme) => {
    transitionTheme(() => setThemeState(next));
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* Persisting the preference is best-effort. */
    }
  }, []);

  const toggle = useCallback(
    () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
    [resolvedTheme, setTheme],
  );

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, toggle }),
    [theme, resolvedTheme, setTheme, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside a ThemeProvider.");
  return context;
}
