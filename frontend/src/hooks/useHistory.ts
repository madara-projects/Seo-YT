import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  CohortLearning,
  HistoryRunDetail,
  HistoryRunsResponse,
  HistorySummary,
  PublishedVideosResponse,
} from "@/api/historyTypes";

/**
 * History and Dashboard data access.
 *
 * Both pages read the same `/api/history` summary, so it lives under one query
 * key and TanStack Query de-duplicates the request across them — this replaces
 * the hand-rolled `historySummaryCache` / `invalidateHistorySummary` pair in
 * the legacy `state.js`.
 */

export const historyKeys = {
  all: ["history"] as const,
  summary: () => [...historyKeys.all, "summary"] as const,
  runs: (limit: number, offset: number) => [...historyKeys.all, "runs", limit, offset] as const,
  run: (runId: number) => [...historyKeys.all, "run", runId] as const,
  published: () => [...historyKeys.all, "published"] as const,
  cohorts: () => [...historyKeys.all, "cohorts"] as const,
};

export function useHistorySummary() {
  return useQuery({
    queryKey: historyKeys.summary(),
    queryFn: () => apiRequest<HistorySummary>("/api/history"),
  });
}

export function useHistoryRuns(limit = 50, offset = 0) {
  return useQuery({
    queryKey: historyKeys.runs(limit, offset),
    queryFn: () =>
      apiRequest<HistoryRunsResponse>(`/api/history/runs?limit=${limit}&offset=${offset}`),
  });
}

export function useHistoryRun(runId: number | null) {
  return useQuery({
    queryKey: historyKeys.run(runId ?? 0),
    queryFn: () => apiRequest<HistoryRunDetail>(`/api/history/runs/${runId}`),
    enabled: typeof runId === "number" && runId > 0,
  });
}

export function usePublishedVideos() {
  return useQuery({
    queryKey: historyKeys.published(),
    queryFn: () => apiRequest<PublishedVideosResponse>("/api/published-videos"),
  });
}

export function useCohortLearning() {
  return useQuery({
    queryKey: historyKeys.cohorts(),
    queryFn: () => apiRequest<CohortLearning>("/api/learning/cohorts"),
  });
}

/** Server-side cap on `run_ids` in one bulk delete (DeleteHistoryRunsRequest). */
export const MAX_BULK_DELETE = 100;

export interface DeleteRunsResult {
  status?: string;
  deleted_count?: number;
  deleted_run_ids?: number[];
  run_id?: number;
  cloud_sync?: { state?: string };
}

/**
 * Deletes one or many saved packages.
 *
 * Bulk delete is all-or-nothing server side — it 404s and deletes nothing if
 * any id is missing — so the UI must never report partial success. The
 * response carries the cloud-sync state, which decides whether the deletion
 * propagated or was only queued; the legacy UI surfaced that distinction and
 * it matters when sync is offline.
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
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}

/** Wording the legacy UI used to distinguish a synced deletion from a queued one. */
export function cloudDeletionNote(state?: string): string {
  return state === "healthy/idle"
    ? "Deletion synced to cloud."
    : "Cloud deletion is queued and will retry automatically.";
}

export function useLinkVideo() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, { runId: number; youtubeVideoId: string }>({
    mutationFn: ({ runId, youtubeVideoId }) =>
      apiRequest(`/api/history/runs/${runId}/link-video`, {
        method: "POST",
        body: { youtube_video_id: youtubeVideoId },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}

export function useRefreshLinkedVideo() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, number>({
    mutationFn: (linkId) =>
      apiRequest(`/api/published-videos/${linkId}/refresh`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}
