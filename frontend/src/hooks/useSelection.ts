import { useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

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
 */
export function useSelection<K extends string>(kinds: readonly K[]) {
  const [searchParams, setSearchParams] = useSearchParams();
  const detailRef = useRef<HTMLDivElement>(null);
  const pendingReveal = useRef(false);
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
    (kind: K | null, id: number | null) => {
      pendingReveal.current = kind !== null && id !== null;
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const name of kindsKey.split(",")) next.delete(name);
          if (kind !== null && id !== null) next.set(kind, String(id));
          return next;
        },
        { replace: true },
      );
    },
    [kindsKey, setSearchParams],
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
  const selectId = useCallback((id: number | null) => select(id === null ? null : name, id), [name, select]);
  return { selectedId: selected?.id ?? null, select: selectId, detailRef };
}
