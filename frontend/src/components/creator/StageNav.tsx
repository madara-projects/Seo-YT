import { useEffect, useRef } from "react";
import { Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { STAGES, type StageKey } from "@/lib/creatorConstants";

/**
 * Step rail for the eight-stage workflow. Stages past "idea" stay reachable
 * only once an analysis exists, because every later stage renders analysis
 * output and would otherwise show nothing but empty states.
 *
 * Eight equal columns keep every stage visible on a laptop screen; narrower
 * screens scroll the rail sideways and keep the current stage in view.
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
  const navRef = useRef<HTMLElement>(null);

  // Where the rail scrolls sideways, centre the current stage. Adjusting
  // scrollLeft directly never moves the page itself.
  useEffect(() => {
    const nav = navRef.current;
    const active = nav?.querySelector<HTMLElement>('[aria-current="step"]');
    if (!nav || !active || nav.scrollWidth <= nav.clientWidth) return;
    nav.scrollLeft = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
  }, [current]);

  return (
    <nav
      ref={navRef}
      aria-label="Creator workflow stages"
      className="relative overflow-x-auto scrollbar-none max-md:[mask-image:linear-gradient(to_right,transparent,black_6%,black_88%,transparent)]"
    >
      <ol className="grid min-w-170 grid-cols-8">
        {STAGES.map((stage, index) => {
          const isCurrent = stage.key === current;
          const isComplete = unlocked && index < currentIndex;
          const isLocked = !unlocked && index > 0;

          return (
            <li key={stage.key} className="relative">
              {index < STAGES.length - 1 ? (
                <span
                  className={cn(
                    "absolute left-1/2 top-[1.5rem] h-0.5 w-full -translate-y-1/2 rounded-full",
                    isComplete ? "bg-tone-ok/50" : "bg-border",
                  )}
                  aria-hidden="true"
                />
              ) : null}
              <button
                type="button"
                onClick={() => onSelect(stage.key)}
                disabled={isLocked}
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "group relative flex w-full flex-col items-center gap-1.5 rounded-xl px-1 pb-1.5 pt-2 text-center transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isLocked && "cursor-not-allowed",
                )}
                title={isLocked ? "Run Analyze to unlock this stage." : stage.hint}
              >
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-full border text-xs font-semibold transition-all",
                    isCurrent &&
                      "border-transparent bg-brand-gradient text-white shadow-[0_6px_16px_-6px_oklch(0.55_0.25_300/0.9)] ring-4 ring-brand-soft",
                    !isCurrent && isComplete && "border-tone-ok-border bg-tone-ok-bg text-tone-ok",
                    !isCurrent && !isComplete && !isLocked && "border-border bg-card text-muted-foreground group-hover:border-brand-border group-hover:text-brand",
                    isLocked && "border-dashed border-border bg-card text-muted-foreground/60",
                  )}
                >
                  {isLocked ? (
                    <Lock className="size-3" aria-hidden="true" />
                  ) : isComplete ? (
                    <Check className="size-3.5" strokeWidth={3} aria-hidden="true" />
                  ) : (
                    stage.step
                  )}
                </span>
                <span
                  className={cn(
                    "text-xs font-medium leading-tight",
                    isCurrent ? "text-foreground" : "text-muted-foreground",
                    isLocked && "text-muted-foreground/60",
                    !isLocked && !isCurrent && "group-hover:text-foreground",
                  )}
                >
                  {stage.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
