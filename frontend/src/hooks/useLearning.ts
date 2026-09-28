import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  RetentionProbeResult,
  StudioTest,
  StudioTestOverview,
  StudioTestUpdate,
  TrafficCohortResponse,
} from "@/api/learningTypes";
import { historyKeys } from "./queryKeys";

/**
 * Outcome learning: YouTube Studio tests (prepared and recorded here, run by
 * YouTube), traffic-source cohorts and the retention-curve probe. The keys sit
 * under `historyKeys.all`, so deleting or linking a package refreshes them too.
 */
export const learningKeys = {
  studioTests: (runId: number) => [...historyKeys.all, "studio-tests", runId] as const,
  trafficCohorts: (window: string) => [...historyKeys.cohorts(), "traffic", window] as const,
};

export function useStudioTests(runId: number | null) {
  return useQuery({
    queryKey: learningKeys.studioTests(runId ?? 0),
    queryFn: ({ signal }) => apiRequest<StudioTestOverview>(`/api/history/runs/${runId}/studio-tests`, { signal }),
    enabled: typeof runId === "number" && runId > 0,
  });
}

export function useCreateStudioTest(runId: number | null) {
  const queryClient = useQueryClient();
  return useMutation<StudioTest, unknown, { packageIds: string[]; notes?: string }>({
    mutationFn: ({ packageIds, notes }) =>
      apiRequest<StudioTest>(`/api/history/runs/${runId}/studio-tests`, {
        method: "POST",
        body: { package_ids: packageIds, notes: notes ?? "" },
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: learningKeys.studioTests(runId ?? 0) }),
  });
}

export function useUpdateStudioTest(runId: number | null) {
  const queryClient = useQueryClient();
  return useMutation<StudioTest, unknown, { testId: number; changes: StudioTestUpdate }>({
    mutationFn: ({ testId, changes }) =>
      apiRequest<StudioTest>(`/api/studio-tests/${testId}`, { method: "PATCH", body: changes }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: learningKeys.studioTests(runId ?? 0) }),
  });
}

/** One YouTube Analytics request per call; the answer is shown, not stored. */
export function useRetentionProbe(linkId: number | null) {
  return useMutation<RetentionProbeResult, unknown, void>({
    mutationFn: () =>
      apiRequest<RetentionProbeResult>(`/api/published-videos/${linkId}/retention-probe`, { method: "POST" }),
  });
}

export function useTrafficCohorts(window: string) {
  return useQuery({
    queryKey: learningKeys.trafficCohorts(window),
    queryFn: ({ signal }) =>
      apiRequest<TrafficCohortResponse>(`/api/learning/cohorts?window=${encodeURIComponent(window)}`, { signal }),
  });
}
