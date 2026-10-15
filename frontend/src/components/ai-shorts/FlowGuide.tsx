import { Lightbulb, ListChecks } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { stepPromptPart, stepText } from "@/lib/aiShortsFormat";
import { cn } from "@/lib/utils";
import type { AiShortsShot } from "@/api/aiShortsTypes";

/**
 * The steps to take in Flow, as a checklist the creator ticks while working,
 * with the prompt a step pastes one click away. The ticks belong to the plan
 * view (they survive a tab change), never to the server.
 */
export function FlowGuide({
  steps,
  cautions,
  shots,
  done,
  onToggle,
}: {
  steps: string[];
  cautions: string[];
  shots: AiShortsShot[];
  done: ReadonlySet<number>;
  onToggle: (index: number, checked: boolean) => void;
}) {
  const count = steps.filter((_, index) => done.has(index)).length;
  const prompts = new Map(shots.map((shot) => [shot.part, String(shot.prompt ?? "").trim()]));

  return (
    <div className="space-y-4" data-testid="flow-guide">
      <Panel
        icon={ListChecks}
        title="Make it in Flow"
        description="Tick each step as you go. The ticks stay on this screen only."
        aside={
          steps.length ? (
            <EvidenceChip tone={count === steps.length ? "ok" : "neutral"}>
              {count} / {steps.length} done
            </EvidenceChip>
          ) : null
        }
      >
        {steps.length ? (
          <ol className="space-y-2">
            {steps.map((step, index) => {
              const checked = done.has(index);
              const text = stepText(step);
              const part = stepPromptPart(text);
              const prompt = part !== null ? prompts.get(part) : undefined;
              return (
                <li
                  key={index}
                  className={cn(
                    "flex flex-wrap items-start gap-x-3 gap-y-2 rounded-xl border p-3 transition-colors",
                    checked
                      ? "border-tone-ok-border bg-tone-ok-bg/50"
                      : "border-border bg-card hover:border-foreground/20 hover:bg-accent/50",
                  )}
                >
                  <label className="flex min-w-0 flex-1 basis-60 cursor-pointer items-start gap-3">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => onToggle(index, value === true)}
                      className="mt-0.5"
                      aria-label={`Step ${index + 1}: ${text}`}
                    />
                    <span
                      className="numeric grid size-5 shrink-0 place-items-center rounded-full bg-muted text-[0.6875rem] font-semibold text-muted-foreground"
                      aria-hidden="true"
                    >
                      {index + 1}
                    </span>
                    <span
                      className={cn(
                        "min-w-0 break-words text-[0.8125rem] leading-relaxed",
                        checked ? "text-muted-foreground" : "text-foreground",
                      )}
                    >
                      {text}
                    </span>
                  </label>
                  {prompt ? (
                    <CopyButton
                      value={prompt}
                      label={`Copy Part ${part} prompt`}
                      size="xs"
                      variant="soft"
                      className="ml-auto"
                      successMessage={`Part ${part} prompt copied.`}
                    />
                  ) : null}
                </li>
              );
            })}
          </ol>
        ) : (
          <UnavailableNote>No Flow steps were returned for this plan.</UnavailableNote>
        )}
      </Panel>

      {cautions.length ? (
        <section
          aria-label="Keep in mind"
          className="@container rounded-2xl border border-border bg-card/60 px-4 py-3.5 sm:px-5"
        >
          <h3 className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            <Lightbulb className="size-3.5" aria-hidden="true" />
            Keep in mind
          </h3>
          <ul className="mt-2 grid gap-x-6 gap-y-1.5 @3xl:grid-cols-2">
            {cautions.map((caution, index) => (
              <li key={index} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 break-words">{caution}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
