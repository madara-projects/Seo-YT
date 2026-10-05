import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
  type MutationStatus,
  type QueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { apiRequest, formatApiError } from "@/api/client";
import type {
  AiShortsGenerateRequest,
  AiShortsPlan,
  AiShortsPlanSummary,
  AiShortsPlansResponse,
} from "@/api/aiShortsTypes";
import { asArray } from "@/lib/utils";
import { aiShortsKeys, historyKeys, invalidatePackageViews, mutationKeys, systemKeys } from "./queryKeys";

/** The list shows the newest plans; the server pages beyond this. */
export const AI_SHORTS_LIST_LIMIT = 20;

export function useAiShortsPlans() {
  return useQuery({
    queryKey: aiShortsKeys.plans(),
    queryFn: async ({ signal }) => {
      const data = await apiRequest<AiShortsPlansResponse>(
        `/api/ai-shorts/plans?limit=${AI_SHORTS_LIST_LIMIT}`,
        { signal },
      );
      return { plans: asArray<AiShortsPlanSummary>(data.plans) };
    },
  });
}

export function useAiShortsPlan(planId: number | null) {
  return useQuery({
    queryKey: aiShortsKeys.plan(planId ?? 0),
    queryFn: ({ signal }) => apiRequest<AiShortsPlan>(`/api/ai-shorts/plans/${planId}`, { signal }),
    enabled: typeof planId === "number" && planId > 0,
    // A plan never changes once written, so one read is enough; the generate
    // mutation seeds this cache so the result shows without a second request.
    staleTime: Infinity,
  });
}

export interface AiShortsRun {
  status: MutationStatus;
  data: AiShortsPlan | undefined;
  error: unknown;
  variables: AiShortsGenerateRequest | undefined;
  submittedAt: number;
}

/**
 * The newest generate run, from the mutation cache rather than page state, so
 * a run started before the creator left the page is still found on return:
 * its progress while it runs (Gemini calls are not spent twice), then its
 * result.
 */
export function useLatestAiShortsRun(): AiShortsRun | null {
  const runs = useMutationState({
    filters: { mutationKey: mutationKeys.aiShorts },
    select: (mutation): AiShortsRun => ({
      status: mutation.state.status,
      data: mutation.state.data as AiShortsPlan | undefined,
      error: mutation.state.error,
      variables: mutation.state.variables as AiShortsGenerateRequest | undefined,
      submittedAt: mutation.state.submittedAt,
    }),
  });
  return runs.reduce<AiShortsRun | null>(
    (newest, run) => (run.status !== "idle" && (!newest || run.submittedAt >= newest.submittedAt) ? run : newest),
    null,
  );
}

/**
 * Writes the Flow prompts and the package for one quote. Never retried: a run
 * is several Gemini calls, and a silent retry would spend them twice. No
 * client timeout either; the server finishes the run whatever the page does,
 * and saves it to History.
 */
export function useGenerateAiShorts() {
  const queryClient = useQueryClient();

  return useMutation<AiShortsPlan, unknown, AiShortsGenerateRequest>({
    mutationKey: mutationKeys.aiShorts,
    retry: false,
    gcTime: 30 * 60_000,
    mutationFn: (body) => apiRequest<AiShortsPlan>("/api/ai-shorts/generate", { method: "POST", body }),
    onSuccess: (plan) => {
      if (typeof plan.id === "number") queryClient.setQueryData(aiShortsKeys.plan(plan.id), plan);
      void queryClient.invalidateQueries({ queryKey: aiShortsKeys.plans() });
      // The package is saved to History, which Settings counts.
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings });

      if (plan.generation_source === "fallback") {
        toast.warning("Gemini was unavailable; a built-in template draft was written. Retry for Gemini prompts.");
      } else if (plan.checks && plan.checks.passed === false) {
        toast.warning("Flow prompts written, with issues to review before you paste them.");
      } else {
        toast.success("Flow prompts and package written. Saved to History.");
      }
    },
    onError: (error) => {
      toast.error(formatApiError(error, "The Flow prompts could not be written."));
    },
  });
}

/**
 * Forgets the generate runs a deleted plan has made stale: the run that wrote
 * it and every finished run before that one. With no plan open, the page shows
 * the newest run's result for as long as the run stays cached, so the deleted
 * plan came back as "not found" on the next visit, or an older run's plan took
 * its place. A run still in progress is kept.
 */
function forgetRunsOfPlan(queryClient: QueryClient, planId: number) {
  const cache = queryClient.getMutationCache();
  const runs = cache.findAll({ mutationKey: mutationKeys.aiShorts });
  const writer = runs.find((run) => (run.state.data as AiShortsPlan | undefined)?.id === planId);
  if (!writer) return;
  for (const run of runs) {
    if (run.state.status !== "pending" && run.state.submittedAt <= writer.state.submittedAt) cache.remove(run);
  }
}

export function useDeleteAiShortsPlan() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, number>({
    mutationFn: (planId) => apiRequest(`/api/ai-shorts/plans/${planId}`, { method: "DELETE" }),
    onSuccess: (_result, planId) => {
      queryClient.setQueryData<{ plans: AiShortsPlanSummary[] }>(aiShortsKeys.plans(), (loaded) =>
        loaded ? { plans: loaded.plans.filter((plan) => plan.id !== planId) } : loaded,
      );
      queryClient.removeQueries({ queryKey: aiShortsKeys.plan(planId) });
      forgetRunsOfPlan(queryClient, planId);
      // The plan's History package goes with it, and everything that counts
      // packages; the AI Shorts list is among those views.
      invalidatePackageViews(queryClient);
    },
    // A 404 means it was already gone, so the list on screen is out of date.
    onError: () => void queryClient.invalidateQueries({ queryKey: aiShortsKeys.plans() }),
  });
}
