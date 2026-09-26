import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { apiRequest, formatApiError } from "@/api/client";
import type { AnalyzeResponse } from "@/api/types";
import { asArray } from "@/lib/utils";
import { toAnalyzePayload, type CreatorFormValues } from "@/schemas/creator";
import { historyKeys, mutationKeys, systemKeys } from "./queryKeys";
import type { LoadedRuns } from "./useHistory";

/**
 * Runs one `/analyze` request.
 *
 * Deliberate choices:
 *  - `retry: false`. A single run costs real YouTube quota and several Gemini
 *    calls, and currently takes 1-3 minutes. Silently retrying a failure would
 *    double-spend the user's quota without their knowledge.
 *  - no client-side timeout. The backend runs its Gemini calls in turn, so
 *    aborting early would throw away work that is still progressing.
 *  - the run lives in the mutation cache under `mutationKeys.analyze`, kept
 *    for half an hour. Leaving Creator mid-run doesn't lose it: coming back
 *    shows its progress (so it can't be started twice) and then its result.
 *  - the outcome is announced here rather than by the page, so it is
 *    announced once, wherever the creator is when it finishes.
 */
export function useAnalyze() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation<AnalyzeResponse, unknown, CreatorFormValues>({
    mutationKey: mutationKeys.analyze,
    retry: false,
    gcTime: 30 * 60_000,
    mutationFn: (values) =>
      apiRequest<AnalyzeResponse>("/analyze", {
        method: "POST",
        body: toAnalyzePayload(values),
      }),
    onSuccess: (data) => {
      // The backend saves every completed run to History, which Settings counts.
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings });

      const review = { label: "Review", onClick: () => navigate("/creator") };
      const warnings = asArray<string>(data.research_warnings);
      if (data.generation_source === "fallback") {
        toast.warning("Gemini was unavailable; review the local fallback carefully before publishing.", { action: review });
      } else if (warnings.length) {
        toast.warning(`Package generated with ${warnings.length} research warning(s) to review.`, { action: review });
      } else {
        toast.success("Package generated. Review it before you publish.", { action: review });
      }
    },
    onError: (error) => {
      toast.error(formatApiError(error, "Analysis failed."));
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
    onSuccess: (_data, { runId, packageId }) => {
      // Choosing between packages can take several clicks; patching the one
      // row spares a page-by-page reload of the whole library for each.
      queryClient.setQueryData<LoadedRuns>(historyKeys.runs(), (loaded) =>
        loaded
          ? { ...loaded, runs: loaded.runs.map((run) => (run.id === runId ? { ...run, selected_package_id: packageId } : run)) }
          : loaded,
      );
      void queryClient.invalidateQueries({
        queryKey: historyKeys.all,
        predicate: (query) => query.queryKey[1] !== "runs",
      });
    },
  });
}
