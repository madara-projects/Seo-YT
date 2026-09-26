import { useEffect, useState } from "react";
import { Controller, type UseFormReturn } from "react-hook-form";
import { ArrowLeft, ChevronDown, Info, Loader2, Sparkles, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { OptionSelect } from "@/components/common/OptionSelect";
import { FormatPicker, formatConsequence } from "./FormatPicker";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import {
  LANGUAGE_OPTIONS,
  REGION_OPTIONS,
  TEMPLATE_TEXT,
  TITLE_STYLE_OPTIONS,
  VIDEO_LANGUAGE_OPTIONS,
  VOICE_OVER_OPTIONS,
} from "@/lib/creatorConstants";
import { rememberFormat, setupSummary, summaryParts } from "@/lib/creatorFormat";
import { isFormatChoice, type CreatorFormValues } from "@/schemas/creator";

type Form = UseFormReturn<CreatorFormValues>;
type FieldName = keyof CreatorFormValues;

const SCRIPT_LIMIT = 12000;

interface DetailField {
  name: FieldName;
  label: string;
  kind: "text" | "area" | "select";
  placeholder?: string;
  hint?: string;
  maxLength?: number;
  options?: { value: string; label: string }[];
}

interface DetailGroup {
  key: string;
  title: string;
  fields: DetailField[];
}

/** Visuals, voice and length: what a Short is mostly made of, so it leads for Shorts. */
function visualsGroup(short: boolean): DetailGroup {
  return {
    key: "visuals",
    title: short ? "Your Short" : "Visuals, voice and length",
    fields: [
      {
        name: "exact_quote",
        label: "On-screen quote or text",
        kind: "area",
        placeholder: "Text that must appear word for word",
        hint: "Kept exactly as written; the package never rewrites it.",
      },
      {
        name: "visual_requirements",
        label: "Background visuals",
        kind: "area",
        placeholder: "e.g. rain on a window, slow zoom on a candle",
      },
      { name: "voice_over", label: "Voice-over", kind: "select", options: VOICE_OVER_OPTIONS },
      {
        name: "duration_seconds",
        label: "Length (seconds)",
        kind: "text",
        placeholder: short ? "e.g. 30" : "e.g. 600",
        hint: "Used for pacing checks.",
      },
    ],
  };
}

const AUDIENCE_GROUP: DetailGroup = {
  key: "audience",
  title: "Audience and promise",
  fields: [
    { name: "target_audience", label: "Who is it for?", kind: "text", placeholder: "e.g. new parents, college students", maxLength: 200 },
    { name: "viewer_promise", label: "What will viewers get?", kind: "text", placeholder: "What they learn, feel or see", maxLength: 300 },
    { name: "unique_angle", label: "What makes it different?", kind: "text", placeholder: "Your take, or what others miss", maxLength: 300 },
    { name: "creator_intent", label: "What should this video do for you?", kind: "text", placeholder: "e.g. grow subscribers, promote a course", maxLength: 500 },
  ],
};

const PROOF_GROUP: DetailGroup = {
  key: "proof",
  title: "Proof and facts",
  fields: [
    { name: "proof", label: "Proof you can show", kind: "text", placeholder: "A result, experience or footage you have", maxLength: 300 },
    { name: "factual_claims", label: "Facts stated in the video", kind: "area" },
  ],
};

const PACKAGING_GROUP: DetailGroup = {
  key: "packaging",
  title: "Title and thumbnail",
  fields: [
    { name: "thumbnail_idea", label: "Thumbnail idea", kind: "text", placeholder: "What the thumbnail should show", maxLength: 200 },
    { name: "title_style", label: "Title style", kind: "select", options: TITLE_STYLE_OPTIONS },
  ],
};

const RULES_GROUP: DetailGroup = {
  key: "rules",
  title: "Rules",
  fields: [
    { name: "claim_restrictions", label: "Claims to avoid", kind: "area", hint: "The package must not make these claims." },
    { name: "content_constraints", label: "Other rules", kind: "area" },
  ],
};

/** The groups in the order that matters for the chosen format. */
function detailGroups(short: boolean): DetailGroup[] {
  const visuals = visualsGroup(short);
  return short
    ? [visuals, AUDIENCE_GROUP, PROOF_GROUP, PACKAGING_GROUP, RULES_GROUP]
    : [AUDIENCE_GROUP, PROOF_GROUP, PACKAGING_GROUP, visuals, RULES_GROUP];
}

const DETAIL_FIELDS = detailGroups(true).flatMap((group) => group.fields.map((field) => field.name));

function isFilled(name: FieldName, value: unknown): boolean {
  // Title style always has a value; only a change from the default is the creator's.
  if (name === "title_style") return Boolean(value) && value !== "balanced";
  return Boolean(String(value ?? "").trim());
}

/**
 * A field's error, or its hint while valid, with the id its control points
 * `aria-describedby` at, so a screen reader reads the message with the field.
 */
function FieldNote({ id, error, hint }: { id: string; error?: string; hint?: string }) {
  if (error) {
    return (
      <p id={id} role="alert" className="text-xs font-medium text-tone-bad">
        {error}
      </p>
    );
  }
  return hint ? (
    <p id={id} className="text-xs text-muted-foreground">
      {hint}
    </p>
  ) : null;
}

function DetailInput({ form, field }: { form: Form; field: DetailField }) {
  const error = form.formState.errors[field.name]?.message as string | undefined;
  const noteId = `${field.name}-note`;
  const describedBy = error || field.hint ? noteId : undefined;

  return (
    <div className={cn("space-y-2", field.kind === "area" && "sm:col-span-2")}>
      <Label htmlFor={field.name}>{field.label}</Label>
      {field.kind === "select" ? (
        <Controller
          control={form.control}
          name={field.name}
          render={({ field: control }) => (
            <OptionSelect
              id={field.name}
              ariaLabel={field.label}
              value={String(control.value ?? "")}
              onValueChange={control.onChange}
              options={field.options ?? []}
            />
          )}
        />
      ) : field.kind === "area" ? (
        <Textarea
          id={field.name}
          rows={2}
          placeholder={field.placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          {...form.register(field.name)}
        />
      ) : (
        <Input
          id={field.name}
          placeholder={field.placeholder}
          maxLength={field.maxLength}
          inputMode={field.name === "duration_seconds" ? "numeric" : undefined}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          {...form.register(field.name)}
        />
      )}
      <FieldNote id={noteId} error={error} hint={field.hint} />
    </div>
  );
}

function SelectField({
  form,
  name,
  label,
  hint,
  options,
}: {
  form: Form;
  name: FieldName;
  label: string;
  hint: string;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <OptionSelect
            id={name}
            ariaLabel={label}
            value={String(field.value ?? "")}
            onValueChange={field.onChange}
            options={options}
          />
        )}
      />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function Section({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("space-y-3 rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5", className)}>
      {title ? <h2 className="font-display text-base font-semibold tracking-tight text-foreground">{title}</h2> : null}
      {children}
    </section>
  );
}

/**
 * Why Generate can't run yet, in words, or null when it can. The button is
 * disabled rather than left to fail, so the reason is shown beside it.
 */
export function generateBlocker(values: Pick<CreatorFormValues, "script" | "format_choice">): string | null {
  const script = String(values.script ?? "");
  if (!script.trim()) return "Add your script or idea to generate a package.";
  if (!isFormatChoice(values.format_choice)) return "Choose what you're making first.";
  if (script.length > SCRIPT_LIMIT) return "Shorten the script to 12,000 characters or fewer.";
  return null;
}

/**
 * The Creator's first screen: what is being made, the script, language and
 * region, then optional details. On wide screens the form sits beside a
 * sticky "Your package" panel with the choices that decide the package and
 * the Generate button; narrower, it is one column with the action in a bar
 * at the bottom. Everything the old eight-step flow asked for is still here.
 */
export function SetupScreen({
  form,
  onSubmit,
  isPending,
  onBackToResults,
}: {
  form: Form;
  onSubmit: () => void;
  isPending: boolean;
  /** Set when a result exists, so editing can be abandoned without losing it. */
  onBackToResults?: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  // Tailwind's xl: wide enough for the form and a summary panel side by side.
  const wide = useMediaQuery("(min-width: 80rem)");
  const values = form.watch();
  const short = values.format_choice === "short";
  const groups = detailGroups(short);
  const filled = DETAIL_FIELDS.filter((name) => isFilled(name, values[name])).length;
  const errors = form.formState.errors;
  // An invalid optional field must be visible, so its group opens on its own.
  const detailsError = DETAIL_FIELDS.some((name) => errors[name]);
  const blocker = generateBlocker(values);
  const scriptError = errors.script?.message;
  const script = values.script ?? "";

  // The next package starts from the last format chosen.
  useEffect(() => {
    if (isFormatChoice(values.format_choice)) {
      rememberFormat({ format_choice: values.format_choice, long_type: values.long_type ?? "" });
    }
  }, [values.format_choice, values.long_type]);

  const languageFields = (stacked: boolean) => (
    <div className={cn("grid gap-4", stacked ? "" : "sm:grid-cols-3")}>
      <SelectField
        form={form}
        name="language"
        label="Output language"
        hint="For the title, description and tags."
        options={LANGUAGE_OPTIONS}
      />
      <SelectField
        form={form}
        name="video_language"
        label="Spoken language"
        hint="What is said or shown in the video."
        options={VIDEO_LANGUAGE_OPTIONS}
      />
      <SelectField form={form} name="region" label="Region" hint="Where most viewers are." options={REGION_OPTIONS} />
    </div>
  );

  const generate = (fullWidth: boolean) => (
    <Button
      type="button"
      variant="gradient"
      size="lg"
      onClick={onSubmit}
      disabled={Boolean(blocker) || isPending}
      aria-describedby="generate-reason"
      className={fullWidth ? "w-full" : "shrink-0"}
    >
      {isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
      {isPending ? "Generating…" : "Generate package"}
    </Button>
  );

  const reason = (
    <p id="generate-reason" className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
      {blocker ?? "Uses YouTube quota and a few Gemini calls. Nothing is uploaded or published."}
    </p>
  );

  const howItWorks = (
    <details className="group rounded-2xl border border-border bg-card px-4 py-3 text-[0.8125rem] sm:px-5">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-foreground [&::-webkit-details-marker]:hidden">
        <Info className="size-4 text-muted-foreground" aria-hidden="true" />
        How it works
        <ChevronDown className="ml-auto size-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="mt-3 max-w-prose space-y-2 leading-relaxed text-muted-foreground">
        <p>
          One run researches public YouTube results for your topic, then writes a title, description, tags and
          hashtags with a few options to compare. You choose one; nothing is uploaded or published.
        </p>
        <p>Every value says where it came from, and a guess never poses as a measurement:</p>
        <div className="flex flex-wrap gap-1.5">
          <EvidenceChip tone="ok">Your input</EvidenceChip>
          <EvidenceChip tone="info">Public observation</EvidenceChip>
          <EvidenceChip tone="warn">Heuristic or generated</EvidenceChip>
          <EvidenceChip tone="neutral">Unavailable</EvidenceChip>
        </div>
      </div>
    </details>
  );

  const main = (
    <div className="min-w-0 space-y-4">
      {onBackToResults ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border bg-elevated px-4 py-2.5">
          <p className="text-[0.8125rem] text-muted-foreground">
            Editing the inputs. Your last package is kept until you generate a new one.
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onBackToResults}>
            <ArrowLeft aria-hidden="true" />
            Back to results
          </Button>
        </div>
      ) : null}

      <Section>
        <FormatPicker form={form} showConsequence={!wide} />
      </Section>

      <Section title="Your script or idea">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="script">Script</Label>
            <span
              className={cn(
                "numeric text-[0.6875rem]",
                script.length > SCRIPT_LIMIT ? "font-semibold text-tone-bad" : "text-muted-foreground",
              )}
            >
              {script.length.toLocaleString()} / 12,000
            </span>
          </div>
          <Textarea
            id="script"
            rows={6}
            placeholder={
              short
                ? "Paste the quote or the few lines you'll say, or describe the Short in a sentence…"
                : "Paste the script, or describe the video in a sentence or two…"
            }
            aria-invalid={Boolean(scriptError)}
            aria-describedby={scriptError ? "script-note script-help" : "script-help"}
            className="min-h-36 resize-y bg-elevated text-[0.9375rem]"
            {...form.register("script")}
          />
          <FieldNote id="script-note" error={scriptError} />
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <p id="script-help" className="text-xs text-muted-foreground">
              The only required field. Research searches are built from this text.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Wand2 className="size-3.5" aria-hidden="true" />
                Try a sample
              </span>
              {Object.entries(TEMPLATE_TEXT).map(([key, template]) => (
                <Button
                  key={key}
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full"
                  onClick={() => form.setValue("script", template.text, { shouldDirty: true, shouldValidate: true })}
                >
                  {template.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {wide ? null : <Section title="Language and region">{languageFields(false)}</Section>}

      <Collapsible open={detailsOpen || detailsError} onOpenChange={setDetailsOpen}>
        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-5"
            >
              <span className="min-w-0 space-y-0.5">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-display text-base font-semibold text-foreground">More details (optional)</span>
                  <EvidenceChip tone={filled ? "ok" : "neutral"}>
                    {filled ? `${filled} filled` : "None filled"}
                  </EvidenceChip>
                </span>
                <span className="block max-w-prose text-[0.8125rem] leading-relaxed text-muted-foreground">
                  {short
                    ? "Quote text, visuals, voice-over and length first. Anything you add is labelled as yours; the rest is inferred."
                    : "Audience, proof, thumbnail and rules. Anything you add is labelled as yours; the rest is inferred."}
                </span>
              </span>
              <ChevronDown
                className={cn(
                  "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
                  (detailsOpen || detailsError) && "rotate-180",
                )}
                aria-hidden="true"
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="space-y-6 border-t border-border p-4 sm:p-5">
              {groups.map((group) => (
                <fieldset key={group.key} className="space-y-3" data-testid={`details-${group.key}`}>
                  <legend className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    {group.title}
                  </legend>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {group.fields.map((field) => (
                      <DetailInput key={field.name} form={form} field={field} />
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          </CollapsibleContent>
        </section>
      </Collapsible>

      {wide ? null : howItWorks}

      {wide ? null : (
        <div
          className="sticky bottom-0 z-10 -mx-4 border-t border-border bg-background/90 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-md sm:mx-0 sm:rounded-t-2xl sm:border-x sm:px-5"
          data-testid="setup-bar"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 space-y-0.5">
              <p className="truncate text-[0.8125rem] font-semibold text-foreground" data-testid="setup-summary">
                {setupSummary(values)}
              </p>
              {reason}
            </div>
            {generate(false)}
          </div>
        </div>
      )}
    </div>
  );

  if (!wide) return main;

  // xl and up: the form on the left, and beside it a panel that stays in view
  // with everything that decides the package and the one action.
  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_23rem] 2xl:grid-cols-[minmax(0,1fr)_26rem]">
      {main}
      <aside aria-label="Your package" className="sticky top-20 space-y-4" data-testid="setup-panel">
        <section className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="space-y-2">
            <h2 className="font-display text-base font-semibold tracking-tight text-foreground">Your package</h2>
            <p className="flex flex-wrap items-center gap-1.5" data-testid="setup-summary">
              {summaryParts(values).map((part, index) => (
                <span key={part} className="contents">
                  {index ? <span className="sr-only"> · </span> : null}
                  <EvidenceChip tone="ok">{part}</EvidenceChip>
                </span>
              ))}
            </p>
          </div>
          {languageFields(true)}
          {isFormatChoice(values.format_choice) ? (
            <p className="rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-muted-foreground" aria-live="polite">
              <span className="font-medium text-foreground">
                {values.format_choice === "auto" ? "Detected:" : "What this changes:"}
              </span>{" "}
              {formatConsequence(values.format_choice)}
            </p>
          ) : null}
          <div className="space-y-2 border-t border-border pt-4">
            {generate(true)}
            {reason}
          </div>
        </section>
        {howItWorks}
      </aside>
    </div>
  );
}
