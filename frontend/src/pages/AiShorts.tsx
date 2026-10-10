import { useCallback, useState } from "react";
import { Clapperboard, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/States";
import { PlanEmpty, PlanSkeleton } from "@/components/ai-shorts/PlanStates";
import { PlanResults } from "@/components/ai-shorts/PlanResults";
import { QuoteForm } from "@/components/ai-shorts/QuoteForm";
import { RecentPlans } from "@/components/ai-shorts/RecentPlans";
import {
  useAiShortsPlan,
  useAiShortsPlans,
  useDeleteAiShortsPlan,
  useGenerateAiShorts,
  useLatestAiShortsRun,
} from "@/hooks/useAiShorts";
import { useElapsedSeconds } from "@/hooks/useElapsed";
import { useSelectedId } from "@/hooks/useSelection";
import { ApiError, apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { aiShortsFormDefaults, quoteBlocker, quoteExcerpt, type AiShortsFormValues } from "@/lib/aiShortsFormat";
import type { AiShortsGenerateRequest, AiShortsPlan, AiShortsPlanSummary } from "@/api/aiShortsTypes";

/** A quote Short has no audience region to ask for; the package language is the only choice. */
const REGION = "global";

function toRequest(values: AiShortsFormValues): AiShortsGenerateRequest {
  return {
    quote: values.quote.trim(),
    language: values.language || "english",
    parts: values.parts,
    mood_hint: values.moodHint.trim(),
    region: REGION,
  };
}

/** The form as it was for a run, so coming back mid-run shows what was asked for. */
function fromRequest(request: AiShortsGenerateRequest | undefined): AiShortsFormValues | null {
  if (!request) return null;
  return {
    quote: request.quote,
    moodHint: request.mood_hint ?? "",
    parts: request.parts,
    language: request.language,
  };
}

/**
 * AI Shorts: a quote in, Google Flow prompts and a package out. The form and
 * the recent plans sit on the left; the open plan on the right. The open plan
 * lives in the URL (`?plan=`) so it can be linked to; without one, the newest
 * run's result shows, found in the mutation cache even after leaving the page
 * while it ran.
 */
export default function AiShortsPage() {
  const latest = useLatestAiShortsRun();
  const generate = useGenerateAiShorts();
  const mutate = generate.mutate;
  const deletePlan = useDeleteAiShortsPlan();
  const { selectedId, select, detailRef } = useSelectedId("plan");

  const [values, setValues] = useState<AiShortsFormValues>(() => fromRequest(latest?.variables) ?? aiShortsFormDefaults);
  // A run whose outcome the creator has moved on from: its error is no longer
  // shown, and its result no longer stands in for an open plan. (Deleting a
  // plan drops the runs it made stale from the cache instead; see the hook.)
  const [ignoredRun, setIgnoredRun] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AiShortsPlanSummary | null>(null);

  const isPending = latest?.status === "pending";
  const elapsed = useElapsedSeconds(isPending, latest?.submittedAt);
  const current = latest && latest.submittedAt !== ignoredRun ? latest : null;
  const failure = current?.status === "error" ? current.error : null;
  const latestPlanId = current?.status === "success" && typeof current.data?.id === "number" ? current.data.id : null;
  const planId = selectedId ?? latestPlanId;

  const plans = useAiShortsPlans();
  const detail = useAiShortsPlan(planId);
  const plan = detail.data ?? null;
  // The newest run's plan can be deleted from History, which doesn't know the
  // run that wrote it: then there is nothing to show, not an error. A plan
  // named in the URL that is gone is still reported.
  const latestPlanGone = selectedId === null && detail.error instanceof ApiError && detail.error.status === 404;

  const submit = useCallback(
    (next: AiShortsFormValues) => {
      if (quoteBlocker(next)) return;
      setValues(next);
      // The new plan opens once it is written; the hook has already cached it.
      mutate(toRequest(next), { onSuccess: (data) => select(data.id) });
    },
    [mutate, select],
  );

  const handleSubmit = () => submit(values);

  /** The same quote again, after a built-in template draft, for Gemini: the draft's own request, not the form's. */
  const regenerate = (draft: AiShortsPlan) =>
    submit({ quote: draft.quote, moodHint: draft.mood_hint ?? "", parts: draft.parts, language: draft.language });

  const retryFailed = () => {
    const prior = fromRequest(current?.variables);
    if (prior) submit(prior);
  };

  const openPlan = (id: number) => {
    // Opening a saved plan is moving on from the last run's error, if any.
    if (latest) setIgnoredRun(latest.submittedAt);
    select(id);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    try {
      await deletePlan.mutateAsync(target.id);
      toast.success("AI Short deleted.");
      if (selectedId === target.id) select(null);
      setDeleteTarget(null);
    } catch (error) {
      toast.error(formatApiError(error, "Could not delete this AI Short."));
    }
  };

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up lg:flex lg:h-full lg:min-h-0 lg:flex-col">
      <PageHeader
        compact
        eyebrow="Studio"
        icon={Clapperboard}
        title="AI Shorts"
        description="Type a quote and get Google Flow (Veo 3.1) prompts for each 8-second part, plus the title, description, hashtags and tags for the Short. Nothing here uploads or publishes."
      />

      <div className="grid grid-cols-1 items-start gap-5 lg:min-h-0 lg:flex-1 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-stretch">
        <div className="min-w-0 space-y-5 lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain lg:pr-2 lg:pb-4" data-testid="ai-shorts-input-scroll">
          <QuoteForm
            values={values}
            onChange={(patch) => setValues((prior) => ({ ...prior, ...patch }))}
            onSubmit={handleSubmit}
            isPending={isPending}
          />
          <RecentPlans
            plans={plans.data?.plans ?? []}
            isPending={plans.isPending}
            isFetching={plans.isFetching}
            error={plans.error}
            selectedId={planId}
            onSelect={openPlan}
            onDelete={setDeleteTarget}
            onRefresh={() => void plans.refetch()}
          />
        </div>

        <div ref={detailRef} className="min-w-0 scroll-mt-24 space-y-5 lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain lg:pr-2 lg:pb-4" data-testid="ai-shorts-results-scroll" tabIndex={0} role="region" aria-label="AI Shorts results">
          {isPending ? (
            <PlanSkeleton mode="writing" elapsed={elapsed} />
          ) : (
            <>
              {failure ? (
                <ErrorState
                  message={apiErrorMessage(failure, "The Flow prompts could not be written.")}
                  requestId={apiRequestId(failure)}
                  onRetry={retryFailed}
                />
              ) : null}
              {planId !== null && !latestPlanGone ? (
                detail.isPending ? (
                  <PlanSkeleton mode="loading" />
                ) : detail.error ? (
                  <ErrorState
                    message={apiErrorMessage(detail.error, "Could not load this AI Short.")}
                    requestId={apiRequestId(detail.error)}
                    onRetry={() => void detail.refetch()}
                  />
                ) : plan ? (
                  <PlanResults key={plan.id} plan={plan} onRetry={() => regenerate(plan)} retrying={isPending} />
                ) : null
              ) : failure ? null : (
                <PlanEmpty />
              )}
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        icon={Trash2}
        title="Delete this AI Short?"
        description={
          deleteTarget
            ? `“${quoteExcerpt(deleteTarget.quote)}” — its prompts and package are removed from Recent AI Shorts. This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        pendingLabel="Deleting…"
        pending={deletePlan.isPending}
        destructive
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
