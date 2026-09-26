import type { QueryClient } from "@tanstack/react-query";

/**
 * Every query and mutation key in one module. A change on one page often
 * shows on several others (deleting a package also removes its audits and
 * experiment assignments), so hooks invalidate each other's keys; keeping the
 * keys here stops the hook modules importing each other in a circle.
 */

export const historyKeys = {
  all: ["history"] as const,
  summary: () => [...historyKeys.all, "summary"] as const,
  runs: () => [...historyKeys.all, "runs"] as const,
  run: (runId: number) => [...historyKeys.all, "run", runId] as const,
  published: () => [...historyKeys.all, "published"] as const,
  cohorts: () => [...historyKeys.all, "cohorts"] as const,
};

export const systemKeys = {
  health: ["health"] as const,
  settings: ["system", "settings"] as const,
  cloudSync: ["system", "cloud-sync"] as const,
  channel: ["system", "channel"] as const,
};

export const ideaKeys = {
  all: ["ideas"] as const,
  lists: () => [...ideaKeys.all, "list"] as const,
  list: (status: string, offset: number) => [...ideaKeys.lists(), status, offset] as const,
  detail: (id: number) => [...ideaKeys.all, "detail", id] as const,
};

export const demandKeys = {
  all: ["demand"] as const,
  lists: () => [...demandKeys.all, "list"] as const,
  list: (offset: number) => [...demandKeys.lists(), offset] as const,
  snapshot: (id: number) => [...demandKeys.all, "snapshot", id] as const,
};

export const auditKeys = {
  all: ["audits"] as const,
  lists: () => [...auditKeys.all, "list"] as const,
  list: (auditState: string, evidenceState: string) => [...auditKeys.lists(), auditState, evidenceState] as const,
  detail: (linkId: number) => [...auditKeys.all, "detail", linkId] as const,
};

export const experimentKeys = {
  all: ["experiments"] as const,
  lists: () => [...experimentKeys.all, "list"] as const,
  list: (status: string, mode: string) => [...experimentKeys.lists(), status, mode] as const,
  detail: (id: number) => [...experimentKeys.all, "detail", id] as const,
};

export const watchKeys = {
  all: ["watchlist"] as const,
  lists: () => [...watchKeys.all, "list"] as const,
  channels: (state: string) => [...watchKeys.lists(), "channels", state] as const,
  videos: (state: string, query: string) => [...watchKeys.lists(), "videos", state, query] as const,
  channel: (id: number) => [...watchKeys.all, "channel", id] as const,
  video: (id: number) => [...watchKeys.all, "video", id] as const,
};

/** Mutations other components look for while they run. */
export const mutationKeys = {
  /** `/analyze`: the Creator finds a run started before it was (re)mounted. */
  analyze: ["analyze"] as const,
  /** Settings and Channel refresh through the same key, so one never starts while the other runs. */
  channelRefresh: ["channel-refresh"] as const,
  /** Demand research spends quota: the form finds a run still in flight after the page is left and reopened. */
  demandResearch: ["demand-research"] as const,
  /**
   * Everything done to one record (`kind` is "idea", "audit", "watch-video"…).
   * The state outlives the panel that started it, so switching records and
   * back still shows a request in flight, and its error.
   */
  record: (kind: string, id: number) => ["record-action", kind, id] as const,
  recordAction: (kind: string, id: number, action: string) => ["record-action", kind, id, action] as const,
};

/**
 * A package was saved, deleted or linked. Deleting cascades to its published
 * link, audits and experiment assignments and returns its idea to "scripted";
 * linking publishes the idea and creates an audit candidate; Settings counts
 * all of them. Every view of that data is refreshed, not just History.
 */
export function invalidatePackageViews(queryClient: QueryClient, { keepRunList = false } = {}) {
  void queryClient.invalidateQueries({
    queryKey: historyKeys.all,
    // The package list reloads page by page; a caller that has already
    // patched it in the cache spares those requests.
    predicate: keepRunList ? (query) => query.queryKey[1] !== "runs" : undefined,
  });
  for (const queryKey of [ideaKeys.all, auditKeys.all, experimentKeys.all, systemKeys.settings]) {
    void queryClient.invalidateQueries({ queryKey });
  }
}
