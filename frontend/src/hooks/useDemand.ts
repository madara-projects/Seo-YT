import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  DemandGenerateResponse,
  DemandListResponse,
  DemandResearchResponse,
  DemandSnapshot,
} from "@/api/researchTypes";
import type { DemandFormValues } from "@/schemas/demand";
import { historyKeys } from "./useHistory";

export const demandKeys = {
  all: ["demand"] as const,
  list: () => [...demandKeys.all, "list"] as const,
  snapshot: (id: number) => [...demandKeys.all, "snapshot", id] as const,
};

export function useDemandSnapshots() {
  return useQuery({
    queryKey: demandKeys.list(),
    queryFn: () => apiRequest<DemandListResponse>("/api/demand/research?limit=50&offset=0"),
  });
}

export function useDemandSnapshot(id: number | null) {
  return useQuery({
    queryKey: demandKeys.snapshot(id ?? 0),
    queryFn: () => apiRequest<{ research?: DemandSnapshot }>(`/api/demand/research/${id}`),
    enabled: typeof id === "number" && id > 0,
    // A snapshot never changes once saved.
    staleTime: Infinity,
  });
}

/**
 * Runs live YouTube research and saves a dated snapshot. It spends API quota,
 * so a failure is surfaced rather than retried behind the user's back.
 */
export function useResearchDemand() {
  const queryClient = useQueryClient();
  return useMutation<DemandResearchResponse, unknown, DemandFormValues>({
    retry: false,
    mutationFn: (values) =>
      apiRequest<DemandResearchResponse>("/api/demand/research", {
        method: "POST",
        body: {
          topic: values.topic.trim(),
          language: values.language,
          format: values.format,
          region: values.region,
          audience_context: values.audience_context.trim(),
        },
      }),
    onSuccess: (data) => {
      if (data.research?.id) {
        queryClient.setQueryData(demandKeys.snapshot(data.research.id), { research: data.research });
      }
      void queryClient.invalidateQueries({ queryKey: demandKeys.list() });
    },
  });
}

/**
 * Writes a package from a snapshot with the Creator engine (Gemini) and saves
 * it to History. Never retried, for the same reason as `/analyze`.
 */
export function useGenerateFromDemand() {
  const queryClient = useQueryClient();
  return useMutation<DemandGenerateResponse, unknown, number>({
    retry: false,
    mutationFn: (id) =>
      apiRequest<DemandGenerateResponse>(`/api/demand/research/${id}/generate`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}
