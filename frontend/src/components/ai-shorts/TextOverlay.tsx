import { Eye, Type } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { asArray } from "@/lib/utils";
import type { AiShortsOverlay, AiShortsPlan } from "@/api/aiShortsTypes";

/** Which lines of the quote show during each part. The wording is the creator's, untouched. */
export function TextOverlay({ plan }: { plan: AiShortsPlan }) {
  const overlays = asArray<AiShortsOverlay>(plan.text_overlay_plan);

  return (
    <Panel
      icon={Type}
      title="Text on screen"
      description="When each line shows. The quote is kept exactly as you typed it; add the text in your editor, not in the Flow prompt."
      aside={<EvidenceChip tone="ok">Exact wording kept</EvidenceChip>}
      data-testid="text-overlay"
    >
      <div className="space-y-3">
        {/* A Short is judged in its first second, so the rule sits above the plan, whatever the plan says. */}
        <Inset className="flex gap-2.5" role="note" aria-label="First-frame rule">
          <Eye className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <p className="text-xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">First frame:</span> the first line must be on screen from
            the very first frame, large and high-contrast. No typing animation and no fade-in: a Short is judged in
            its first second.
          </p>
        </Inset>
        {overlays.length ? (
          <ol className="grid gap-3 sm:grid-cols-2">
            {overlays.map((overlay) => {
              const lines = asArray<string>(overlay.lines);
              return (
                <li key={overlay.part} className="min-w-0">
                  <Inset className="h-full space-y-2">
                    <p className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">Part {overlay.part}</span>
                      {overlay.seconds ? <span className="numeric">{overlay.seconds} s</span> : null}
                    </p>
                    {lines.length ? (
                      <ul className="space-y-1">
                        {lines.map((line, index) => (
                          <li key={index} className="break-words font-display text-[0.9375rem] font-semibold leading-snug text-foreground">
                            {line}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground">No text during this part.</p>
                    )}
                  </Inset>
                </li>
              );
            })}
          </ol>
        ) : (
          <UnavailableNote>No on-screen text plan was returned.</UnavailableNote>
        )}
      </div>
    </Panel>
  );
}
