import { useState } from "react";
import { Info, ListChecks } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { cn } from "@/lib/utils";

/**
 * The steps to take in Flow, as a checklist the creator ticks while working.
 * The ticks are this screen's own: mount it keyed by plan so a new plan
 * starts unticked.
 */
export function FlowGuide({ steps, cautions }: { steps: string[]; cautions: string[] }) {
  const [done, setDone] = useState<ReadonlySet<number>>(() => new Set());
  const count = steps.filter((_, index) => done.has(index)).length;

  const toggle = (index: number, checked: boolean) =>
    setDone((prior) => {
      const next = new Set(prior);
      if (checked) next.add(index);
      else next.delete(index);
      return next;
    });

  return (
    <Panel
      icon={ListChecks}
      title="Generate it in Flow"
      description="Tick each step as you go. The ticks stay on this screen only."
      aside={
        steps.length ? (
          <EvidenceChip tone={count === steps.length ? "ok" : "neutral"}>
            {count} / {steps.length} done
          </EvidenceChip>
        ) : null
      }
      data-testid="flow-guide"
    >
      <div className="space-y-4">
        {steps.length ? (
          <ol className="space-y-2">
            {steps.map((step, index) => {
              const checked = done.has(index);
              return (
                <li key={index}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                      checked
                        ? "border-tone-ok-border bg-tone-ok-bg/50"
                        : "border-border bg-card hover:border-foreground/20 hover:bg-accent/50",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => toggle(index, value === true)}
                      className="mt-0.5"
                      aria-label={`Step ${index + 1}: ${step}`}
                    />
                    <span
                      className="numeric grid size-5 shrink-0 place-items-center rounded-full bg-muted text-[0.6875rem] font-semibold text-muted-foreground"
                      aria-hidden="true"
                    >
                      {index + 1}
                    </span>
                    <span
                      className={cn(
                        "text-[0.8125rem] leading-relaxed",
                        checked ? "text-muted-foreground" : "text-foreground",
                      )}
                    >
                      {step}
                    </span>
                  </label>
                </li>
              );
            })}
          </ol>
        ) : (
          <UnavailableNote>No Flow steps were returned for this plan.</UnavailableNote>
        )}

        {cautions.length ? (
          <div className="rounded-xl border border-border bg-muted/40 px-3.5 py-3" role="note" aria-label="Keep in mind">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Info className="size-3.5" aria-hidden="true" />
              Keep in mind
            </p>
            <ul className="mt-1.5 space-y-1">
              {cautions.map((caution, index) => (
                <li key={index} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                  <span>{caution}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
