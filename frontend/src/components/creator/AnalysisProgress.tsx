import { Check, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/hooks/useElapsed";

/**
 * Progress for a long, opaque request.
 *
 * The backend exposes no progress events, so this shows elapsed time and the
 * typical sequence rather than a synthetic percentage. Which phase is
 * highlighted is an estimate from elapsed time, and the copy says so:
 * inventing a progress bar that does not track real work would be exactly the
 * kind of confident-but-unfounded signal the rest of the product refuses.
 */
const PHASES = [
  { from: 0, label: "Brief & queries", detail: "Building the creator brief and planning research queries" },
  { from: 20, label: "YouTube research", detail: "Running YouTube research and scoring public results" },
  { from: 60, label: "Writing", detail: "Generating the package with Gemini" },
  { from: 150, label: "Finishing", detail: "Still generating - long runs are expected on this backend" },
] as const;

export function AnalysisProgress({ elapsed }: { elapsed: number }) {
  const activeIndex = PHASES.reduce((found, phase, index) => (elapsed >= phase.from ? index : found), 0);
  const active = PHASES[activeIndex] ?? PHASES[0];

  return (
    <div
      role="status"
      aria-live="polite"
      className="relative overflow-hidden rounded-2xl border-gradient p-5 shadow-card sm:p-6"
    >
      <div
        className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-brand-gradient opacity-15 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3.5">
          <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-gradient text-white shadow-[0_8px_20px_-8px_oklch(0.55_0.25_300/0.9)]">
            <Sparkles className="size-5 animate-pulse" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-display text-base font-semibold text-foreground">
              Analyzing and packaging
            </p>
            <p className="truncate text-[13px] text-muted-foreground">{active.detail}</p>
          </div>
        </div>
        <span className="numeric shrink-0 text-2xl font-semibold tabular-nums text-foreground">
          {formatDuration(elapsed)}
        </span>
      </div>

      <div
        className="relative mt-5 h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label="Analysis in progress"
      >
        <div className="h-full w-1/3 animate-indeterminate rounded-full bg-brand-gradient" />
      </div>

      <ol className="relative mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {PHASES.map((phase, index) => {
          const done = index < activeIndex;
          const current = index === activeIndex;
          return (
            <li
              key={phase.label}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors",
                current && "border-brand-border bg-brand-soft text-foreground",
                done && "border-border bg-card text-muted-foreground",
                !done && !current && "border-dashed border-border text-muted-foreground/70",
              )}
            >
              {done ? (
                <Check className="size-3.5 shrink-0 text-tone-ok" aria-hidden="true" />
              ) : current ? (
                <Loader2 className="size-3.5 shrink-0 animate-spin text-brand" aria-hidden="true" />
              ) : (
                <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />
              )}
              <span className="font-medium">{phase.label}</span>
            </li>
          );
        })}
      </ol>

      <p className="relative mt-4 text-xs leading-relaxed text-muted-foreground">
        The typical sequence, estimated from elapsed time — the server does not report live progress.
        Several Gemini calls run in turn, so a full run usually takes one to three minutes. Leaving
        this page does not stop it: the run finishes on the server and appears in History.
      </p>
    </div>
  );
}
