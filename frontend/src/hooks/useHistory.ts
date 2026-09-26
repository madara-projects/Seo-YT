import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  CohortLearning,
  HistoryRun,
  HistoryRunDetail,
  HistoryRunsResponse,
  HistorySummary,
  LinkVideoResult,
  PublishedVideosResponse,
} from "@/api/historyTypes";
import type { DeletionCloudSync } from "@/api/systemTypes";
import { asArray } from "@/lib/utils";
import { historyKeys, invalidatePackageViews } from "./queryKeys";

/**
 * History and Dashboard data access.
 *
 * Both pages read the same `/api/history` summary, so it lives under one query
 * key and TanStack Query de-duplicates the request across them.
 */

export function useHistorySummary() {
  return useQuery({
    queryKey: historyKeys.summary(),
    queryFn: ({ signal }) => apiRequest<HistorySummary>("/api/history", { signal }),
  });
}

/** The server caps `limit` at 100. */
const RUNS_PAGE_SIZE = 100;
/**
 * At most this many pages (1,000 packages) are loaded. The server allows 60
 * reads a minute per route, and a refetch reloads every page, so deleting and
 * linking patch the loaded list instead of reloading it (see below).
 */
const MAX_RUN_PAGES = 10;

export interface LoadedRuns {
  runs: HistoryRun[];
  /** Every saved package, including any beyond the pages loaded. */
  total: number;
}

/**
 * Every saved package, newest first, page by page. Search, the library's
 * totals and bulk selection all work on the whole list, so it is loaded in
 * full rather than stopping at the first page.
 */
export function useHistoryRuns() {
  return useQuery({
    queryKey: historyKeys.runs(),
    queryFn: async ({ signal }): Promise<LoadedRuns> => {
      const runs: HistoryRun[] = [];
      const seen = new Set<number>();
      let total: number | null = null;
      for (let page = 0; page < MAX_RUN_PAGES; page += 1) {
        const data = await apiRequest<HistoryRunsResponse>(
          `/api/history/runs?limit=${RUNS_PAGE_SIZE}&offset=${page * RUNS_PAGE_SIZE}`,
          { signal },
        );
        const rows = asArray<HistoryRun>(data.runs);
        // A package saved while paging shifts the offsets by one; skip the repeat.
        const fresh = rows.filter((run) => !seen.has(run.id));
        fresh.forEach((run) => seen.add(run.id));
        runs.push(...fresh);
        if (typeof data.total === "number") total = data.total;
        // A short page, or one with nothing new, is the end of the list.
        if (rows.length < RUNS_PAGE_SIZE || !fresh.length || (total !== null && runs.length >= total)) break;
      }
      return { runs, total: Math.max(total ?? 0, runs.length) };
    },
  });
}

export function useHistoryRun(runId: number | null) {
  return useQuery({
    queryKey: historyKeys.run(runId ?? 0),
    queryFn: ({ signal }) => apiRequest<HistoryRunDetail>(`/api/history/runs/${runId}`, { signal }),
    enabled: typeof runId === "number" && runId > 0,
  });
}

export function usePublishedVideos() {
  return useQuery({
    queryKey: historyKeys.published(),
    queryFn: ({ signal }) => apiRequest<PublishedVideosResponse>("/api/published-videos", { signal }),
  });
}

export function useCohortLearning() {
  return useQuery({
    queryKey: historyKeys.cohorts(),
    queryFn: ({ signal }) => apiRequest<CohortLearning>("/api/learning/cohorts", { signal }),
  });
}

/** Server-side cap on `run_ids` in one bulk delete (DeleteHistoryRunsRequest). */
export const MAX_BULK_DELETE = 100;

export interface DeleteRunsResult {
  status?: string;
  deleted_count?: number;
  deleted_run_ids?: number[];
  run_id?: number;
  cloud_sync?: DeletionCloudSync;
}

/**
 * Deletes one or many saved packages.
 *
 * Bulk delete is all-or-nothing server side — it 404s and deletes nothing if
 * any id is missing — so the UI must never report partial success.
 */
export function useDeleteRuns() {
  const queryClient = useQueryClient();

  return useMutation<DeleteRunsResult, unknown, number[]>({
    mutationFn: (runIds) => {
      if (runIds.length === 1) {
        return apiRequest<DeleteRunsResult>(`/api/history/runs/${runIds[0]}`, {
          method: "DELETE",
        });
      }
      return apiRequest<DeleteRunsResult>("/api/history/runs", {
        method: "DELETE",
        body: { run_ids: runIds.slice(0, MAX_BULK_DELETE) },
      });
    },
    onSuccess: (_result, runIds) => {
      // All-or-nothing on the server, so every requested package is gone.
      const removed = new Set(runIds.slice(0, MAX_BULK_DELETE));
      queryClient.setQueryData<LoadedRuns>(historyKeys.runs(), (loaded) =>
        loaded
          ? {
              runs: loaded.runs.filter((run) => !removed.has(run.id)),
              total: Math.max(0, loaded.total - removed.size),
            }
          : loaded,
      );
      for (const id of removed) queryClient.removeQueries({ queryKey: historyKeys.run(id) });
      invalidatePackageViews(queryClient, { keepRunList: true });
    },
    // A 404 means a package was already gone (another device deleted it and a
    // cloud pull removed it here), so the list on screen is out of date.
    onError: () => invalidatePackageViews(queryClient),
  });
}

/**
 * What happened to the deletion in cloud sync. The delete no longer syncs
 * inside the request: it returns the status at that moment, whether the
 * background sync was woken to push the deletion (`run_requested`), and how
 * many deletions still wait for the cloud. The last run's state can't prove
 * the deletion reached the cloud, so it is not used.
 */
export function cloudDeletionNote(cloudSync: DeletionCloudSync | undefined, count = 1): string {
  const one = count === 1;
  // Only a woken sync goes out soon; a queued deletion alone waits for a run.
  if (cloudSync?.run_requested) return "Cloud deletion is queued and will sync shortly.";
  if (cloudSync?.enabled === false || cloudSync?.state === "disabled") {
    // A package synced before sync was turned off leaves a deletion queued for the cloud copy.
    if ((cloudSync.pending_deletions ?? 0) > 0) {
      return one
        ? "Cloud sync is off; the cloud copy is removed when sync next runs."
        : "Cloud sync is off; the cloud copies are removed when sync next runs.";
    }
    return one
      ? "Cloud sync is off; the package was deleted on this device only."
      : "Cloud sync is off; the packages were deleted on this device only.";
  }
  return "Cloud deletion is queued and will retry automatically.";
}

export function useLinkVideo() {
  const queryClient = useQueryClient();

  return useMutation<
    LinkVideoResult,
    unknown,
    { runId: number; youtubeVideoId: string; replaceExistingEvidence?: boolean }
  >({
    mutationFn: ({ runId, youtubeVideoId, replaceExistingEvidence }) =>
      apiRequest<LinkVideoResult>(`/api/history/runs/${runId}/link-video`, {
        method: "POST",
        body: {
          youtube_video_id: youtubeVideoId,
          // Only ever sent after the creator confirmed losing the old video's evidence.
          ...(replaceExistingEvidence ? { replace_existing_evidence: true } : {}),
        },
      }),
    onSuccess: (result, { runId, youtubeVideoId }) => {
      const videoId = result.youtube_video_id || youtubeVideoId;
      const movedFrom = typeof result.moved_from_run_id === "number" ? result.moved_from_run_id : null;
      queryClient.setQueryData<LoadedRuns>(historyKeys.runs(), (loaded) =>
        loaded
          ? {
              ...loaded,
              runs: loaded.runs.map((run) =>
                run.id === runId
                  ? { ...run, linked_youtube_video_id: videoId, linked_video_link_id: result.link_id ?? run.linked_video_link_id }
                  : // A video links to one package: the one it moved from loses it.
                    run.id === movedFrom
                    ? { ...run, linked_youtube_video_id: null, linked_video_link_id: null }
                    : run,
              ),
            }
          : loaded,
      );
      invalidatePackageViews(queryClient, { keepRunList: true });
    },
  });
}
