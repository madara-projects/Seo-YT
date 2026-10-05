import { Clapperboard, Link2 } from "lucide-react";
import { CopyButton } from "@/components/common/CopyButton";
import { Inset, Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { allPromptsText, shotHeading } from "@/lib/aiShortsFormat";
import type { AiShortsShot } from "@/api/aiShortsTypes";

/**
 * One card per 8-second part, with the prompt to paste into Flow. The first
 * part is a Text to Video prompt; each later one extends the clip before it,
 * and says what must carry over.
 */
export function ShotCards({ shots }: { shots: AiShortsShot[] }) {
  return (
    <section aria-labelledby="ai-shorts-prompts-heading" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="ai-shorts-prompts-heading" className="font-display text-base font-semibold tracking-tight text-foreground">
          Flow prompts
        </h2>
        {shots.length > 1 ? (
          <CopyButton
            value={allPromptsText(shots)}
            label="Copy all prompts"
            variant="soft"
            successMessage="All prompts copied, labelled by part."
          />
        ) : null}
      </div>

      {shots.length ? (
        shots.map((shot) => (
          <Panel
            key={shot.part}
            icon={Clapperboard}
            headingLevel={3}
            title={shotHeading(shot)}
            description={shot.title}
            aside={
              <CopyButton
                value={shot.prompt}
                label="Copy prompt"
                aria-label={`Copy prompt for Part ${shot.part}`}
                successMessage={`Part ${shot.part} prompt copied.`}
              />
            }
            data-testid="shot-card"
          >
            <div className="space-y-3">
              {/* Monospace and freely selectable: it is pasted, not read. */}
              <pre
                className="select-text whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-4 font-mono text-[0.8125rem] leading-relaxed text-foreground"
                data-testid="shot-prompt"
              >
                {shot.prompt}
              </pre>
              {shot.continuity ? (
                <Inset className="flex gap-2.5">
                  <Link2 className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    <span className="font-medium text-foreground">Continuity:</span> {shot.continuity}
                  </p>
                </Inset>
              ) : null}
            </div>
          </Panel>
        ))
      ) : (
        <UnavailableNote>No prompts were returned for this plan.</UnavailableNote>
      )}
    </section>
  );
}
