import { useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useMounted, withParams, type ParamChanges } from "./useUrlState";

export interface Selection<K extends string> {
  kind: K;
  id: number;
}

/** Stacked below this width, so choosing from the list scrolls to the inspector. */
const STACKED_QUERY = "(max-width: 63.99rem)";

function positiveId(value: string | null): number | null {
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
}

/**
 * The record open in a list-and-inspector page, kept in the URL (`?idea=12`)
 * so it can be linked to and survives a reload. A page with more than one
 * kind of record (the watchlist's channels and videos) passes each parameter
 * name; selecting one clears the others. Choosing from the list also brings
 * the inspector into view when the two are stacked on a narrow screen.
 *
 * `extra` changes other parameters (a filter, a page) in the same navigation;
 * a separate call in the same event would be overwritten.
 */
export function useSelection<K extends string>(kinds: readonly K[]) {
  const [searchParams, setSearchParams] = useSearchParams();
  const detailRef = useRef<HTMLDivElement>(null);
  const pendingReveal = useRef(false);
  const mounted = useMounted();
  const kindsKey = kinds.join(",");

  let selected: Selection<K> | null = null;
  for (const kind of kinds) {
    const id = positiveId(searchParams.get(kind));
    if (id !== null) {
      selected = { kind, id };
      break;
    }
  }

  const select = useCallback(
    (kind: K | null, id: number | null, extra: ParamChanges = {}) => {
      // A request that finishes after the page was left must not navigate back to it.
      if (!mounted.current) return;
      pendingReveal.current = kind !== null && id !== null;
      const changes: ParamChanges = {};
      for (const name of kindsKey.split(",")) changes[name] = null;
      if (kind !== null && id !== null) changes[kind] = id;
      setSearchParams((current) => withParams(current, { ...changes, ...extra }), { replace: true });
    },
    [kindsKey, mounted, setSearchParams],
  );

  const selectedKey = selected ? `${selected.kind}:${selected.id}` : "";
  useEffect(() => {
    if (!pendingReveal.current || !selectedKey) return;
    pendingReveal.current = false;
    if (window.matchMedia?.(STACKED_QUERY).matches) {
      detailRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
  }, [selectedKey]);

  return { selected, select, detailRef };
}

/** `useSelection` for a page with one kind of record. */
export function useSelectedId(name: string) {
  const { selected, select, detailRef } = useSelection([name]);
  const selectId = useCallback(
    (id: number | null, extra?: ParamChanges) => select(id === null ? null : name, id, extra),
    [name, select],
  );
  return { selectedId: selected?.id ?? null, select: selectId, detailRef };
}
