import { Palette } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { asArray, displayValue } from "@/lib/utils";
import type { AiShortsPlan } from "@/api/aiShortsTypes";

function Note({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 first:pt-0 last:pb-0 @lg:grid-cols-[10.5rem_minmax(0,1fr)] @lg:gap-4">
      <dt className="text-xs font-medium leading-5 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm leading-relaxed text-foreground">{children}</dd>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {items.map((item, index) => (
        <span
          key={`${item}-${index}`}
          className="max-w-full break-words rounded-lg border border-border bg-elevated px-2 py-0.5 text-xs text-foreground"
        >
          {item}
        </span>
      ))}
    </span>
  );
}

function cleaned(items: unknown): string[] {
  return asArray<unknown>(items).map((item) => String(item ?? "").trim()).filter(Boolean);
}

/**
 * How Gemini read the quote and the scene, look and sound every prompt is
 * written around, so a take can be judged against it. The reading survives a
 * scene the planner threw away as a symbol; a missing mood field says so.
 */
export function SceneNotes({ plan }: { plan: AiShortsPlan }) {
  const mood = plan.mood ?? {};
  const audio = plan.audio ?? {};
  const direction = plan.creative_direction;
  const reading = direction ?? plan.quote_understanding;
  const themes = cleaned(reading?.search_themes);
  const keywords = cleaned(mood.keywords);

  return (
    <Panel
      icon={Palette}
      title="Scene notes"
      description="What every prompt was written around, so a take can be judged against it."
      aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}
      className="@container"
      data-testid="scene-notes"
    >
      <dl className="divide-y divide-border/70">
        {reading ? (
          <>
            <Note label="Quote meaning">{reading.quote_meaning}</Note>
            {reading.emotion ? <Note label="Emotion">{reading.emotion}</Note> : null}
            {reading.tone ? <Note label="Tone">{reading.tone}</Note> : null}
          </>
        ) : null}
        {direction?.scene ? <Note label="Chosen scene">{direction.scene}</Note> : null}
        {direction ? (
          <>
            <Note label="Why this scene fits">{direction.why_it_fits}</Note>
            <Note label="Visible action">
              <ol className="space-y-1">
                {[
                  ["Opening", direction.opening],
                  ["Middle", direction.middle],
                  ["Ending", direction.ending],
                ].map(([label, text]) => (
                  <li key={label}>
                    <span className="text-muted-foreground">{label}:</span> {displayValue(text)}
                  </li>
                ))}
              </ol>
            </Note>
          </>
        ) : null}
        {themes.length ? (
          <Note label="How viewers search for it">
            <Chips items={themes} />
          </Note>
        ) : null}
        <Note label="Feeling">{displayValue(mood.feeling)}</Note>
        <Note label="Pace">{displayValue(mood.pace)}</Note>
        <Note label="Visual metaphor">{displayValue(mood.visual_metaphor)}</Note>
        <Note label="Palette">{displayValue(mood.palette)}</Note>
        <Note label="Keywords">{keywords.length ? <Chips items={keywords} /> : "Unavailable"}</Note>
        <Note label="Audio">
          <span className="block font-medium">{displayValue(audio.style)}</span>
          <span className="mt-0.5 block text-[0.8125rem] text-muted-foreground">
            {displayValue(audio.description, "No audio description was returned.")}
          </span>
        </Note>
      </dl>
    </Panel>
  );
}
