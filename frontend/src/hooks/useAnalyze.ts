import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { AnalyzeResponse } from "@/api/types";
import { toAnalyzePayload, type CreatorFormValues } from "@/schemas/creator";

/**
 * Runs one `/analyze` request.
 *
 * Two deliberate choices:
 *  - `retry: false`. A single run costs real YouTube quota and several Gemini
 *    calls, and currently takes 1-3 minutes. Silently retrying a failure would
 *    double-spend the user's quota without their knowledge.
 *  - no client-side timeout. The backend runs four Gemini calls sequentially,
 *    so aborting early would throw away work that is still progressing.
 *    Cancellation stays an explicit user action.
 */
export function useAnalyze() {
  const queryClient = useQueryClient();

  return useMutation<AnalyzeResponse, unknown, CreatorFormValues>({
    mutationKey: ["analyze"],
    retry: false,
    mutationFn: (values) =>
      apiRequest<AnalyzeResponse>("/analyze", {
        method: "POST",
        headers: { "Cache-Control": "no-cache" },
        body: toAnalyzePayload(values),
      }),
    onSuccess: () => {
      // A completed run is persisted to History by the backend.
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });
}

/**
 * Records the creator's explicit package choice against the saved run.
 * This writes to local SQLite History only; it never touches YouTube.
 */
export function useSelectPackage() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, { runId: number; packageId: string }>({
    mutationFn: ({ runId, packageId }) =>
      apiRequest(`/api/history/runs/${runId}/selection`, {
        method: "PUT",
        body: { package_id: packageId },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });
}
