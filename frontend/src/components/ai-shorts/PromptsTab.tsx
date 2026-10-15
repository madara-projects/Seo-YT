import { useId, useState } from "react";
import { Ban, ChevronDown, Film, Link2, Type, Wand2 } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { UnavailableNote } from "@/components/common/States";
import {
  partOverlay,
  planAdjustments,
  promptParagraphs,
  promptSections,
  rangeLabel,
  shotHeading,
  shotRanges,
  type SecondsRange,
} from "@/lib/aiShortsFormat";
import { asArray, cn } from "@/lib/utils";
import type { AiShortsPlan, AiShortsShot } from "@/api/aiShortsTypes";

/** The scene every prompt films, with the tone and emotion it was written for. */
function SceneSummary({ plan }: { plan: AiShortsPlan }) {
  const direction = plan.creative_direction;
  const reading = direction ?? plan.quote_understanding;
  const scene = String(direction?.scene ?? "").trim() || String(plan.mood?.visual_metaphor ?? "").trim();
  const tone = String(reading?.tone ?? "").trim();
  const emotion = String(reading?.emotion ?? "").trim() || String(plan.mood?.feeling ?? "").trim();
  if (!scene && !tone && !emotion) return null;

  return (
    <p
      className="flex gap-2 rounded-xl border border-border bg-card/60 px-3.5 py-2.5 text-[0.8125rem] leading-relaxed"
      data-testid="scene-summary"
    >
      <Film className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 break-words">
        <span className="font-medium text-foreground">Scene: </span>
        <span className="text-muted-foreground">{scene || "No scene was kept for this plan."}</span>
        {tone ? (
          <Badge variant="brand" title="Tone" className="ml-2 max-w-full whitespace-normal break-words align-[0.0625rem]">
            <span className="sr-only">Tone: </span>
            {tone}
          </Badge>
        ) : null}
        {emotion ? (
          <Badge variant="neutral" title="Emotion" className="ml-1.5 max-w-full whitespace-normal break-words align-[0.0625rem]">
            <span className="sr-only">Emotion: </span>
            {emotion}
          </Badge>
        ) : null}
      </span>
    </p>
  );
}

/** The prompt as labelled rows when the plan has sections, else as short paragraphs. Copying always takes `prompt`. */
function PromptText({ shot }: { shot: AiShortsShot }) {
  const sections = promptSections(shot);
  if (sections.length) {
    return (
      <dl
        className="select-text divide-y divide-border/70 rounded-xl border border-border bg-elevated px-3.5 sm:px-4"
        data-testid="shot-prompt"
      >
        {sections.map((section, index) => (
          <div
            key={`${section.label}-${index}`}
            className="grid gap-0.5 py-2.5 @md:grid-cols-[5.5rem_minmax(0,1fr)] @md:gap-3"
            data-testid="prompt-section"
          >
            <dt className="text-[0.6875rem] font-semibold uppercase leading-5 tracking-wide text-muted-foreground">
              {section.label}
            </dt>
            <dd className="min-w-0 break-words text-[0.875rem] leading-relaxed text-foreground">{section.text}</dd>
          </div>
        ))}
      </dl>
    );
  }

  const paragraphs = promptParagraphs(shot.prompt);
  if (!paragraphs.length) return <UnavailableNote>No prompt was returned for this part.</UnavailableNote>;
  return (
    <div className="select-text space-y-2.5 rounded-xl border border-border bg-elevated p-3.5 sm:p-4" data-testid="shot-prompt">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="max-w-[75ch] break-words text-[0.875rem] leading-relaxed text-foreground">
          {paragraph}
        </p>
      ))}
    </div>
  );
}

/** The quote's lines during this part, added in the editor, never in the Flow prompt. */
function OnScreen({
  plan,
  shot,
  range,
  first,
}: {
  plan: AiShortsPlan;
  shot: AiShortsShot;
  range: SecondsRange;
  first: boolean;
}) {
  const overlay = partOverlay(plan, shot.part);
  const planned = asArray(plan.text_overlay_plan).length > 0;
  const lines = overlay?.lines ?? [];

  return (
    <div className="space-y-2 rounded-xl border border-dashed border-border px-3.5 py-3" data-testid="shot-overlay">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Type className="size-3.5 shrink-0" aria-hidden="true" />
          On screen <span className="tabular">{overlay?.seconds ?? rangeLabel(range)}</span>
        </p>
        {lines.length ? (
          <CopyButton
            value={lines.join("\n")}
            label="Copy text"
            size="xs"
            variant="ghost"
            aria-label={`Copy on-screen text for Part ${shot.part}`}
            successMessage={`Part ${shot.part} on-screen text copied.`}
          />
        ) : null}
      </div>
      {lines.length ? (
        <ul className="space-y-0.5">
          {lines.map((line, index) => (
            <li key={index} className="break-words font-display text-[0.9375rem] font-semibold leading-snug text-foreground">
              {line}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">
          {planned ? "No text during this part." : "No on-screen text plan was returned."}
        </p>
      )}
      {/* A Short is judged in its first second, so the rule sits with the first part, whatever the plan says. */}
      {first ? (
        <p role="note" aria-label="First-frame rule" className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">First frame:</span> add the words in your editor, exactly as
          written, not in Flow. The first line must be on screen from the very first frame, large and high-contrast. No
          typing animation and no fade-in: a Short is judged in its first second.
        </p>
      ) : null}
    </div>
  );
}

function PartCard({
  plan,
  shot,
  range,
  first,
  adjustments,
}: {
  plan: AiShortsPlan;
  shot: AiShortsShot;
  range: SecondsRange;
  first: boolean;
  adjustments: string[];
}) {
  const headingId = useId();
  const title = String(shot.title ?? "").trim();

  return (
    <article
      aria-labelledby={headingId}
      className="@container rounded-2xl border border-border bg-card shadow-card"
      data-testid="shot-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 p-4 sm:p-5">
        <div className="flex min-w-0 flex-1 basis-56 items-start gap-3">
          <span
            className="numeric grid size-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-sm font-semibold text-brand ring-1 ring-inset ring-brand-border"
            aria-hidden="true"
          >
            {shot.part}
          </span>
          <div className="min-w-0 space-y-0.5 pt-0.5">
            <h3 id={headingId} className="font-display text-base font-semibold leading-snug tracking-tight text-foreground">
              {shotHeading(shot, range)}
            </h3>
            {title ? <p className="break-words text-[0.8125rem] leading-relaxed text-muted-foreground">{title}</p> : null}
          </div>
        </div>
        <CopyButton
          value={shot.prompt}
          label="Copy prompt"
          variant="default"
          aria-label={`Copy prompt for Part ${shot.part}`}
          successMessage={`Part ${shot.part} prompt copied.`}
          disabled={!String(shot.prompt ?? "").trim()}
        />
      </div>

      <div className="space-y-3 px-4 pb-4 sm:px-5 sm:pb-5">
        <PromptText shot={shot} />
        {shot.continuity ? (
          <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
            <Link2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 break-words">
              <span className="font-medium text-foreground">Carries over:</span> {shot.continuity}
            </span>
          </p>
        ) : null}
        <OnScreen plan={plan} shot={shot} range={range} first={first} />
        {adjustments.length ? (
          <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground" data-testid="shot-adjustments">
            <Wand2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 break-words">
              <span className="font-medium">Adjusted automatically:</span> {adjustments.join("; ")}
            </span>
          </p>
        ) : null}
      </div>
    </article>
  );
}

/** What the prompts keep out of the frame, folded away: it is already in them. */
function AvoidList({ text }: { text: string }) {
  const [open, setOpen] = useState(false);

  if (!text) return <UnavailableNote>No avoid list was returned for this plan.</UnavailableNote>;
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-2xl border border-border bg-card shadow-card" data-testid="avoid-list">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-5">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="-mx-1 inline-flex min-w-0 items-center gap-2 rounded-lg px-1 py-0.5 text-left text-sm font-semibold text-foreground hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Ban className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            Avoid list
            <ChevronDown
              className={cn("size-4 shrink-0 text-muted-foreground transition-transform duration-200", open && "rotate-180")}
              aria-hidden="true"
            />
          </button>
        </CollapsibleTrigger>
        <CopyButton value={text} label="Copy avoid list" size="xs" successMessage="Avoid list copied." />
      </div>
      <CollapsibleContent className="space-y-2 px-4 pb-4 sm:px-5">
        <p className="select-text break-words rounded-xl border border-border bg-elevated p-3.5 text-[0.8125rem] leading-relaxed text-foreground">
          {text}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          What the prompts keep out of the frame. Copy it on its own where a tool asks for a negative prompt.
        </p>
      </CollapsibleContent>
    </Collapsible>
  );
}

/**
 * One card per 8-second part: the prompt to paste into Flow, the quote's
 * words for that part, and what the planner fixed by itself. The first part
 * is Text to video; each later one extends the clip before it.
 */
export function PromptsTab({ plan, shots }: { plan: AiShortsPlan; shots: AiShortsShot[] }) {
  const ranges = shotRanges(shots);
  const { byPart } = planAdjustments(plan.checks);

  return (
    <div className="space-y-4" data-testid="prompts-tab">
      <SceneSummary plan={plan} />
      {shots.length ? (
        shots.map((shot, index) => (
          <PartCard
            key={shot.part}
            plan={plan}
            shot={shot}
            range={ranges[index]!}
            first={index === 0}
            adjustments={byPart.get(shot.part) ?? []}
          />
        ))
      ) : (
        <UnavailableNote>No prompts were returned for this plan.</UnavailableNote>
      )}
      <AvoidList text={String(plan.negative_prompt ?? "").trim()} />
    </div>
  );
}
