import { Ban, Music, Palette } from "lucide-react";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { SectionTitle } from "@/components/common/SectionTitle";
import { UnavailableNote } from "@/components/common/States";
import { asArray, displayValue } from "@/lib/utils";
import type { AiShortsPlan } from "@/api/aiShortsTypes";

/** The mood the prompts are built around, the sound, and what to keep out of the frame. */
export function MoodAudio({ plan }: { plan: AiShortsPlan }) {
  const mood = plan.mood ?? {};
  const keywords = asArray<string>(mood.keywords);
  const audio = plan.audio ?? {};
  const negative = String(plan.negative_prompt ?? "").trim();

  return (
    <Panel
      icon={Palette}
      title="Mood and audio"
      description="What every prompt was written around, so a take can be judged against it."
      aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}
      data-testid="mood-audio"
    >
      <div className="space-y-5">
        <dl className="grid gap-4 sm:grid-cols-2">
          <Field label="Feeling">{displayValue(mood.feeling)}</Field>
          <Field label="Pace">{displayValue(mood.pace)}</Field>
          <Field label="Visual metaphor" className="sm:col-span-2">
            {displayValue(mood.visual_metaphor)}
          </Field>
          <Field label="Palette">{displayValue(mood.palette)}</Field>
          <Field label="Keywords">
            {keywords.length ? (
              <span className="flex flex-wrap gap-1.5">
                {keywords.map((keyword, index) => (
                  <span
                    key={`${keyword}-${index}`}
                    className="rounded-lg border border-border bg-elevated px-2 py-0.5 text-xs font-normal text-foreground"
                  >
                    {keyword}
                  </span>
                ))}
              </span>
            ) : (
              "Unavailable"
            )}
          </Field>
        </dl>

        <div className="space-y-2">
          <SectionTitle icon={Music}>Audio</SectionTitle>
          <Inset>
            <p className="text-[0.8125rem] font-medium text-foreground">{displayValue(audio.style)}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {displayValue(audio.description, "No audio description was returned.")}
            </p>
          </Inset>
        </div>

        <div className="space-y-2">
          <SectionTitle
            icon={Ban}
            aside={negative ? <CopyButton value={negative} label="Copy negative prompt" size="xs" /> : null}
          >
            Negative prompt
          </SectionTitle>
          {negative ? (
            <pre className="select-text whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-3.5 font-mono text-xs leading-relaxed text-foreground">
              {negative}
            </pre>
          ) : (
            <UnavailableNote>No negative prompt was returned.</UnavailableNote>
          )}
        </div>
      </div>
    </Panel>
  );
}
