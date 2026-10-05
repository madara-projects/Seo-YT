import { ArrowRight, Clapperboard, Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/States";
import { formatDuration } from "@/hooks/useElapsed";
import { cn } from "@/lib/utils";

function SectionSkeleton({ lines }: { lines: number }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card" aria-hidden="true">
      <div className="flex items-center gap-3">
        <Skeleton className="size-9 rounded-xl" />
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="mt-4 space-y-2.5">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className={cn("h-3", index === lines - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    </div>
  );
}

/**
 * The results column while a plan is written (20–60 s of Gemini calls the
 * server reports no progress for, so elapsed time stands in for a percentage)
 * or while a saved one loads.
 */
export function PlanSkeleton({ mode, elapsed = 0 }: { mode: "writing" | "loading"; elapsed?: number }) {
  const writing = mode === "writing";
  return (
    <div className="space-y-5" data-testid="plan-skeleton">
      <div role="status" aria-live="polite" className="relative overflow-hidden rounded-2xl border-gradient p-5 shadow-card">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3.5">
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-gradient text-white">
              <Loader2 className="size-5 animate-spin" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="font-display text-base font-semibold text-foreground">
                {writing ? "Writing prompts and package…" : "Loading this AI Short…"}
              </p>
              <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                {writing
                  ? "Usually 20–60 seconds: the mood, each part's prompt, then the package. Leaving this page doesn't stop it."
                  : "Reading the saved plan."}
              </p>
            </div>
          </div>
          {writing ? (
            <span className="numeric shrink-0 text-2xl font-semibold tabular-nums text-foreground">{formatDuration(elapsed)}</span>
          ) : null}
        </div>
        {writing ? (
          <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Writing in progress">
            <div className="h-full w-1/3 animate-indeterminate rounded-full bg-brand-gradient" />
          </div>
        ) : null}
      </div>
      <SectionSkeleton lines={2} />
      <SectionSkeleton lines={4} />
      <SectionSkeleton lines={4} />
      <SectionSkeleton lines={5} />
      <div className="grid gap-5 2xl:grid-cols-2">
        <SectionSkeleton lines={3} />
        <SectionSkeleton lines={3} />
      </div>
      <SectionSkeleton lines={4} />
    </div>
  );
}

const FLOW = ["Quote", "Prompts", "Flow", "Video", "Package"];

/** Before the first run: what happens, in one breath. */
export function PlanEmpty() {
  return (
    <EmptyState
      icon={Clapperboard}
      title="Quote in, Short out"
      description="Type a quote. Gemini writes one Veo 3.1 prompt per 8-second part and the SEO package. Paste each prompt into Google Flow, generate and extend, add the words on screen, then upload with the package. Everything is saved to History."
      action={
        <ol className="flex flex-wrap items-center justify-center gap-1.5" aria-label="How it works">
          {FLOW.map((step, index) => (
            <li key={step} className="flex items-center gap-1.5">
              <span className="rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground">{step}</span>
              {index < FLOW.length - 1 ? <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden="true" /> : null}
            </li>
          ))}
        </ol>
      }
      className="min-h-[24rem]"
    />
  );
}
