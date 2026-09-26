import { useEffect, useState } from "react";

function matches(query: string): boolean {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.(query).matches);
}

/**
 * Whether a media query matches now, kept current as the window changes. For
 * layouts that move an element rather than restyle it: rendering it once, in
 * the right place, keeps a single copy of each control for keyboard and
 * screen-reader users, where CSS alone would need two.
 */
export function useMediaQuery(query: string): boolean {
  const [matched, setMatched] = useState(() => matches(query));

  useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return;
    const onChange = () => setMatched(list.matches);
    onChange();
    list.addEventListener?.("change", onChange);
    return () => list.removeEventListener?.("change", onChange);
  }, [query]);

  return matched;
}
