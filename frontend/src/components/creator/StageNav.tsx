import { Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { STAGES, type StageKey } from "@/lib/creatorConstants";

/**
 * Step rail for the eight-stage workflow. Stages past "idea" stay reachable
 * only once an analysis exists, because every later stage renders analysis
 * output and would otherwise show nothing but empty states.
 */
export function StageNav({
  current,
  unlocked,
  onSelect,
}: {
  current: StageKey;
  unlocked: boolean;
  onSelect: (stage: StageKey) => void;
}) {
  const currentIndex = STAGES.findIndex((stage) => stage.key === current);

  return (
    <nav aria-label="Creator workflow stages" className="overflow-x-auto scrollbar-thin">
      <ol className="flex min-w-max items-center gap-1 pb-1">
        {STAGES.map((stage, index) => {
          const isCurrent = stage.key === current;
          const isComplete = unlocked && index < currentIndex;
          const isLocked = !unlocked && index > 0;

          return (
            <li key={stage.key}>
              <button
                type="button"
                onClick={() => onSelect(stage.key)}
                disabled={isLocked}
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isCurrent && "bg-primary text-primary-foreground",
                  !isCurrent && !isLocked && "text-muted-foreground hover:bg-muted hover:text-foreground",
                  isLocked && "cursor-not-allowed text-muted-foreground/50",
                )}
                title={isLocked ? "Run Analyze to unlock this stage." : stage.hint}
              >
                <span
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px]",
                    isCurrent
                      ? "border-primary-foreground/40 bg-primary-foreground/15"
                      : isComplete
                        ? "border-tone-ok-border bg-tone-ok-bg text-tone-ok"
                        : "border-border",
                  )}
                >
                  {isLocked ? (
                    <Lock className="h-2.5 w-2.5" aria-hidden="true" />
                  ) : isComplete ? (
                    <Check className="h-3 w-3" aria-hidden="true" />
                  ) : (
                    stage.step
                  )}
                </span>
                {stage.label}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
