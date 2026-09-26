import { useCallback, useEffect, useState } from "react";

/** Where the root font size drops to 80% (see `index.css`). */
const DESKTOP_SCALE_QUERY = "(min-width: 64rem)";

function rootFontPx(): number {
  if (typeof window === "undefined") return 16;
  return parseFloat(window.getComputedStyle(document.documentElement).fontSize) || 16;
}

/**
 * Converts rem to px for the few APIs that only take pixels (Recharts axis
 * widths and margins, IntersectionObserver margins), so they follow the
 * interface scale like everything written in rem. Re-read when the desktop
 * breakpoint, where that scale changes, is crossed.
 */
export function useRemPx(): (rem: number) => number {
  const [base, setBase] = useState(rootFontPx);

  useEffect(() => {
    const media = window.matchMedia?.(DESKTOP_SCALE_QUERY);
    const update = () => setBase(rootFontPx());
    media?.addEventListener?.("change", update);
    return () => media?.removeEventListener?.("change", update);
  }, []);

  return useCallback((rem: number) => Math.round(rem * base), [base]);
}
