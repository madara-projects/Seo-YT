import { Loader2 } from "lucide-react";
import { formatDuration } from "@/hooks/useElapsed";

/**
 * Progress for a long, opaque request.
 *
 * The backend exposes no progress events, so this shows elapsed time and the
 * observed range rather than a synthetic percentage. Inventing a progress bar
 * that does not track real work would be exactly the kind of confident-but-
 * unfounded signal the rest of the product refuses to show.
 */
export function AnalysisProgress({ elapsed }: { elapsed: number }) {
  const stage =
    elapsed < 20
      ? "Building the creator brief and planning research queries"
      : elapsed < 60
        ? "Running YouTube research and scoring public results"
        : elapsed < 150
          ? "Generating the package with Gemini"
          : "Still generating - long runs are expected on this backend";

  return (
    <div
      role="status"
      aria-live="polite"
      className="space-y-3 rounded-lg border border-border bg-muted/40 p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
          Analyzing and packaging
        </span>
        <span className="numeric text-sm font-semibold tabular-nums text-foreground">
          {formatDuration(elapsed)}
        </span>
      </div>

      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-label="Analysis in progress"
      >
        <div className="h-full w-1/3 animate-[indeterminate_1.6s_ease-in-out_infinite] rounded-full bg-primary" />
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {stage}. This backend runs several Gemini calls in sequence, so a full run usually takes
        between one and three minutes. Leaving this page cancels the request.
      </p>

      <style>{`
        @keyframes indeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
      `}</style>
    </div>
  );
}
