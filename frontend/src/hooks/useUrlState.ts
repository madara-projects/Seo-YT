import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** False once the component has unmounted: a URL change from then on belongs to another page. */
export function useMounted() {
  // True from the first render, so a child's mount effect (which runs before
  // this one) can still change the URL.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}

/** New values for search parameters; null, undefined or "" removes one. */
export type ParamChanges = Record<string, string | number | null | undefined>;

export function withParams(current: URLSearchParams, changes: ParamChanges): URLSearchParams {
  const next = new URLSearchParams(current);
  for (const [name, value] of Object.entries(changes)) {
    if (value === null || value === undefined || value === "") next.delete(name);
    else next.set(name, String(value));
  }
  return next;
}

/**
 * View state kept in the URL (a filter, a page, a tab), so a reload or a
 * shared link shows the same view. Change several parameters in one `set`
 * call: React Router's setter reads the URL as of the last render, so two
 * calls in one event would overwrite each other.
 */
export function useUrlState() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mounted = useMounted();

  const get = useCallback((name: string, fallback = "") => searchParams.get(name) ?? fallback, [searchParams]);

  const set = useCallback(
    (changes: ParamChanges) => {
      // "?…" resolves against this page, so a late call from a page already
      // left would navigate the creator back to it.
      if (!mounted.current) return;
      setSearchParams((current) => withParams(current, changes), { replace: true });
    },
    [mounted, setSearchParams],
  );

  return { get, set };
}

/**
 * A text box whose value is kept in the URL. The box itself is local state:
 * React Router applies location changes inside a transition, so an input
 * bound straight to the URL lags behind fast typing, moves the caret and can
 * drop characters. The trimmed value is written to the URL once typing has
 * paused for `delayMs`, and `settled` (read back from the URL) is what a query
 * should use. A URL change from elsewhere (back, forward, a link) replaces
 * what is in the box.
 */
export function useUrlTextParam(name: string, delayMs = 300) {
  const { get, set } = useUrlState();
  const fromUrl = get(name);
  const [value, setValue] = useState(fromUrl);
  const written = useRef(fromUrl);
  const timer = useRef<number | undefined>(undefined);
  // The setter as of the latest render: one captured when the key was pressed
  // would write back the URL as it was then, undoing anything changed since.
  const latestSet = useRef(set);

  useEffect(() => {
    latestSet.current = set;
  }, [set]);

  useEffect(() => {
    if (fromUrl === written.current) return;
    written.current = fromUrl;
    window.clearTimeout(timer.current);
    setValue(fromUrl);
  }, [fromUrl]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const change = useCallback(
    (next: string) => {
      setValue(next);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        const settled = next.trim();
        written.current = settled;
        latestSet.current({ [name]: settled || null });
      }, delayMs);
    },
    [name, delayMs],
  );

  return { value, change, settled: fromUrl.trim() };
}

/** A non-negative whole number from the URL, or 0. */
export function offsetParam(value: string): number {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : 0;
}
