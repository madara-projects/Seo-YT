import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiRequest } from "@/api/client";
import type {
  DemandGenerateResponse,
  DemandListResponse,
  DemandResearchResponse,
  DemandSnapshot,
} from "@/api/researchTypes";
import type { DemandFormValues } from "@/schemas/demand";
import { demandKeys, historyKeys, ideaKeys, mutationKeys, systemKeys } from "./queryKeys";

export const DEMAND_PAGE_SIZE = 50;

export function useDemandSnapshots(offset: number) {
  return useQuery({
    queryKey: demandKeys.list(offset),
    queryFn: ({ signal }) =>
      apiRequest<DemandListResponse>(`/api/demand/research?limit=${DEMAND_PAGE_SIZE}&offset=${offset}`, { signal }),
    // The list has no filters, so the previous page can stay until the next arrives.
    placeholderData: keepPreviousData,
  });
}

export function useDemandSnapshot(id: number | null) {
  return useQuery({
    queryKey: demandKeys.snapshot(id ?? 0),
    queryFn: ({ signal }) => apiRequest<{ research?: DemandSnapshot }>(`/api/demand/research/${id}`, { signal }),
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
    mutationKey: mutationKeys.demandResearch,
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
        // Announced here rather than by the form, so it is heard even after leaving the page.
        toast.success("Demand snapshot saved.");
      }
      void queryClient.invalidateQueries({ queryKey: demandKeys.lists() });
    },
  });
}

/**
 * Writes a package from a snapshot with the Creator engine (Gemini) and saves
 * it to History. Never retried, for the same reason as `/analyze`. Keyed by
 * the snapshot, so its panel finds a run still in flight after switching.
 */
export function useGenerateFromDemand(snapshotId: number) {
  const queryClient = useQueryClient();
  return useMutation<DemandGenerateResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("demand-snapshot", snapshotId, "generate"),
    retry: false,
    mutationFn: (id) =>
      apiRequest<DemandGenerateResponse>(`/api/demand/research/${id}/generate`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
      // A snapshot from an idea moves that idea to "package generated".
      void queryClient.invalidateQueries({ queryKey: ideaKeys.all });
    },
  });
}
