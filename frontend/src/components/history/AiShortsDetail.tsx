import { useState } from "react";
import { BarChart3, ChevronDown, Clapperboard, Loader2, MonitorSmartphone } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/States";
import { PlanView } from "@/components/ai-shorts/PlanView";
import { useAiShortsPlan } from "@/hooks/useAiShorts";
import { ApiError, apiErrorMessage, apiRequestId } from "@/api/client";
import { asObject, cn } from "@/lib/utils";
import { formatCompact, toFiniteNumber } from "@/lib/format";
import { partsLabel } from "@/lib/aiShortsFormat";
import type { AiShortsPlan } from "@/api/aiShortsTypes";
import type { HistoryRunDetail } from "@/api/historyTypes";
import {
  Callout,
  LinkCallout,
  PublishedVideo,
  RetentionCallout,
  SavedPackageFields,
  SelectionCallout,
  hasSelection,
  retentionGuidance,
} from "./HistoryDetailParts";

export interface AiShortsMarker {
  planId: number | null;
  label: string;
  language: string | null;
}

/**
 * The AI Shorts plan a package was written from. Its saved payload carries
 * `source_page: "ai_shorts"` and an `ai_shorts` block naming the plan; the
 * server copies them onto the run, with the plan id of the plan kept on this
 * device (null for a package synced from another device).
 */
export function aiShortsMarker(run: HistoryRunDetail | null): AiShortsMarker | null {
  if (!run) return null;
  const pkg = asObject(run.package);
  const marker = asObject(run.ai_shorts ?? pkg.ai_shorts);
  const written =
    run.source_page === "ai_shorts" || pkg.source_page === "ai_shorts" || Object.keys(marker).length > 0;
  if (!written) return null;
  const planId = toFiniteNumber(marker.plan_id);
  const parts = toFiniteNumber(marker.parts);
  const total = toFiniteNumber(marker.total_seconds);
  return {
    planId: planId !== null && planId > 0 ? planId : null,
    label: parts !== null && parts > 0 ? `AI Shorts · ${partsLabel(parts, total ?? undefined)}` : "AI Shorts",
    language: typeof marker.language === "string" && marker.language ? marker.language : null,
  };
}

export type RunPlan =
  | { status: "elsewhere" }
  | { status: "loading" }
  | { status: "ready"; plan: AiShortsPlan }
  | { status: "gone" }
  | { status: "error"; error: unknown; retry: () => void };

/** The plan behind an AI Shorts run, or null for any other run. */
export function useRunPlan(run: HistoryRunDetail | null, marker: AiShortsMarker | null): RunPlan | null {
  const planId = marker?.planId ?? null;
  const query = useAiShortsPlan(planId);
  if (!run || !marker) return null;
  if (planId === null) return { status: "elsewhere" };
  if (query.isPending) return { status: "loading" };
  const retry = () => void query.refetch();
  if (query.error) {
    return query.error instanceof ApiError && query.error.status === 404
      ? { status: "gone" }
      : { status: "error", error: query.error, retry };
  }
  const plan = query.data;
  if (!plan || !Array.isArray(plan.shots)) {
    return { status: "error", error: new Error("This AI Short's plan could not be read."), retry };
  }
  // A synced payload can name the writing device's plan id, which here is another run's plan.
  if (typeof plan.analysis_run_id === "number" && plan.analysis_run_id !== run.id) return { status: "elsewhere" };
  return { status: "ready", plan };
}

function PlanLoading() {
  return (
    <div className="space-y-4">
      <div role="status" className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-card">
        <Loader2 className="size-4 shrink-0 animate-spin text-brand" aria-hidden="true" />
        <p className="text-[0.8125rem] text-muted-foreground">Loading the Flow prompts…</p>
      </div>
      {[3, 4, 4].map((lines, index) => (
        <div key={index} className="space-y-2.5 rounded-2xl border border-border bg-card p-5" aria-hidden="true">
          <Skeleton className="h-4 w-40" />
          {Array.from({ length: lines }).map((_, line) => (
            <Skeleton key={line} className={cn("h-3", line === lines - 1 ? "w-2/3" : "w-full")} />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Where the Flow prompts would be: the plan itself, or why it can't be
 * shown. Without it, the saved package below still holds the upload fields.
 */
function PlanArea({ plan }: { plan: RunPlan }) {
  switch (plan.status) {
    case "loading":
      return <PlanLoading />;
    case "ready":
      // Keyed so the Flow checklist starts unticked for each plan.
      return <PlanView key={plan.plan.id} plan={plan.plan} context="history" />;
    case "error":
      return (
        <ErrorState
          message={`Could not load the Flow prompts. ${apiErrorMessage(plan.error, "")}`.trim()}
          requestId={apiRequestId(plan.error)}
          onRetry={plan.retry}
        />
      );
    case "gone":
      return (
        <Callout
          icon={Clapperboard}
          tone="warn"
          title="The Flow prompts for this Short were deleted"
          body="Its AI Shorts plan is no longer saved, so the prompts, on-screen text and Flow steps are gone. The saved upload package is below."
        />
      );
    case "elsewhere":
      return (
        <Callout
          icon={MonitorSmartphone}
          title="The Flow prompts are on another device"
          body="This package synced from the device that wrote it. Its Flow prompts stayed there; the saved upload package is below."
        />
      );
  }
}

/**
 * After publishing: the linked video and what it measured, folded away until
 * there is a video. Shorts have no Test & Compare and no measured opportunity,
 * so neither is offered here.
 */
function Performance({ run, onLink }: { run: HistoryRunDetail; onLink: () => void }) {
  const report = run.linked_video_report ?? null;
  const isLinked = Boolean(report?.linked);
  const [open, setOpen] = useState(isLinked);
  const pkg = asObject(run.package);
  const findings = retentionGuidance(pkg)?.findings ?? 0;
  const views = toFiniteNumber(report?.performance?.views);
  const summary = isLinked
    ? `Linked to ${report?.video_id || "a YouTube video"}${views !== null ? ` · ${formatCompact(views)} views` : ""}`
    : "No YouTube video linked yet. Link the Short after publishing.";

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <section
        aria-label="Performance"
        className="overflow-hidden rounded-2xl border border-border bg-card shadow-card"
        data-testid="history-performance"
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-5"
          >
            <span className="flex min-w-0 items-center gap-2.5">
              <BarChart3 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0">
                <span className="block font-display text-base font-semibold text-foreground">Performance</span>
                <span className="block break-words text-[0.8125rem] text-muted-foreground">{summary}</span>
              </span>
            </span>
            <ChevronDown
              className={cn("size-4 shrink-0 text-muted-foreground transition-transform duration-200", open && "rotate-180")}
              aria-hidden="true"
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-4 border-t border-border p-4 sm:p-5">
            {isLinked && report ? (
              <PublishedVideo report={report} fallbackTitle={String(pkg.title || run.title || "Saved package")} />
            ) : (
              <LinkCallout
                onLink={onLink}
                body="No YouTube video is linked yet. Link the Short after publishing to keep its views and retention with this package."
              />
            )}
            {/* Only guidance with findings is worth reading for a quote Short. */}
            {findings > 0 ? <RetentionCallout pkg={pkg} /> : null}
            {hasSelection(run.selected_package) ? <SelectionCallout selection={run.selected_package} /> : null}
          </div>
        </CollapsibleContent>
      </section>
    </Collapsible>
  );
}

/**
 * An AI Shorts run: its plan first (prompts per part, on-screen text, Flow
 * steps, scene notes and package), then how the published Short did.
 */
export function AiShortsBody({ run, plan, onLink }: { run: HistoryRunDetail; plan: RunPlan; onLink: () => void }) {
  const showSaved = plan.status !== "ready" && plan.status !== "loading";
  return (
    <div className="space-y-6">
      <div className="min-w-0" data-testid="history-detail-plan">
        <PlanArea plan={plan} />
      </div>
      {showSaved ? <SavedPackageFields run={run} shorts /> : null}
      <Performance run={run} onLink={onLink} />
    </div>
  );
}
