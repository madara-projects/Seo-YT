import { useState } from "react";
import { Controller, type UseFormReturn } from "react-hook-form";
import {
  ChevronDown,
  Compass,
  Layers,
  ListChecks,
  Package,
  PenLine,
  ScrollText,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Telescope,
  Wand2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { IconBadge } from "@/components/common/IconBadge";
import { OptionSelect } from "@/components/common/OptionSelect";
import { Panel } from "@/components/common/Panel";
import type { CreatorFormValues } from "@/schemas/creator";
import {
  FORMAT_OPTIONS,
  LANGUAGE_OPTIONS,
  REGION_OPTIONS,
  TEMPLATE_TEXT,
  TITLE_STYLE_OPTIONS,
  VIDEO_LANGUAGE_OPTIONS,
  VOICE_OVER_OPTIONS,
} from "@/lib/creatorConstants";

type Form = UseFormReturn<CreatorFormValues>;

/** The optional brief fields, counted to show how much the creator supplied. */
const BRIEF_FIELDS = [
  "target_audience",
  "viewer_promise",
  "unique_angle",
  "proof",
  "video_format",
  "thumbnail_idea",
  "duration_seconds",
  "voice_over",
  "creator_intent",
  "exact_quote",
  "visual_requirements",
  "factual_claims",
  "claim_restrictions",
  "content_constraints",
] as const;

const OUTPUTS = [
  { icon: ScrollText, title: "Creator brief", body: "Which values you supplied and which were inferred." },
  { icon: Telescope, title: "Research", body: "Public YouTube observations and local signals, labelled." },
  { icon: Compass, title: "Recommended angle", body: "Plus hook, pacing and retention checks." },
  { icon: Package, title: "Upload-ready package", body: "Title, description, tags, hashtags and timing." },
  { icon: Layers, title: "Side-by-side options", body: "Title and thumbnail approaches to choose from." },
  { icon: ListChecks, title: "Decision & checklist", body: "A recorded choice and manual pre-publish checks." },
] as const;

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

function SelectField({
  form,
  name,
  label,
  options,
}: {
  form: Form;
  name: keyof CreatorFormValues;
  label: string;
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
    </div>
  );
}

function TextField({
  form,
  name,
  label,
  placeholder,
  hint,
  maxLength,
}: {
  form: Form;
  name: keyof CreatorFormValues;
  label: string;
  placeholder?: string;
  hint?: string;
  maxLength?: number;
}) {
  const error = form.formState.errors[name]?.message;
  const noteId = `${name}-note`;
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        aria-describedby={error || hint ? noteId : undefined}
        {...form.register(name)}
      />
      <FieldNote id={noteId} error={error as string | undefined} hint={hint} />
    </div>
  );
}

function AreaField({
  form,
  name,
  label,
  placeholder,
  hint,
  rows = 3,
}: {
  form: Form;
  name: keyof CreatorFormValues;
  label: string;
  placeholder?: string;
  hint?: string;
  rows?: number;
}) {
  const error = form.formState.errors[name]?.message;
  const noteId = `${name}-note`;
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Textarea
        id={name}
        rows={rows}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        aria-describedby={error || hint ? noteId : undefined}
        {...form.register(name)}
      />
      <FieldNote id={noteId} error={error as string | undefined} hint={hint} />
    </div>
  );
}

function BriefGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

export function IdeaStage({
  form,
  onSubmit,
  isPending,
}: {
  form: Form;
  onSubmit: () => void;
  isPending: boolean;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const script = form.watch("script") ?? "";
  const scriptError = form.formState.errors.script?.message;
  const briefValues = form.watch(BRIEF_FIELDS);
  const filledBrief = briefValues.filter((value) => String(value ?? "").trim()).length;
  const overLimit = script.length > 12000;

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_21.25rem]">
      <div className="min-w-0 space-y-5">
        <Card className="overflow-hidden">
          <div className="flex items-start gap-3 p-5 pb-4 sm:px-6 sm:pt-6">
            <IconBadge icon={PenLine} />
            <div className="space-y-1 pt-0.5">
              <h2 className="font-display text-base font-semibold tracking-tight text-foreground">
                Script or video idea
              </h2>
              <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                The only required input. Everything else sharpens the brief and is optional —
                anything you leave blank is inferred and clearly labelled as such.
              </p>
            </div>
          </div>

          <div className="space-y-5 px-5 pb-5 sm:px-6 sm:pb-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="script">Script</Label>
                <span
                  className={cn(
                    "numeric text-[0.6875rem]",
                    overLimit ? "font-semibold text-tone-bad" : "text-muted-foreground",
                  )}
                >
                  {script.length.toLocaleString()} / 12,000
                </span>
              </div>
              <Textarea
                id="script"
                rows={8}
                placeholder="Paste the script, or describe the video idea in a sentence or two…"
                aria-invalid={Boolean(scriptError)}
                aria-describedby={scriptError ? "script-note script-help" : "script-help"}
                className="min-h-47.5 resize-y bg-elevated text-[0.9375rem]"
                {...form.register("script")}
              />
              <FieldNote id="script-note" error={scriptError} />
              <p id="script-help" className="text-xs text-muted-foreground">
                Research queries are derived from this text.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Wand2 className="size-3.5" aria-hidden="true" />
                Sample ideas
              </span>
              {Object.entries(TEMPLATE_TEXT).map(([key, template]) => (
                <Button
                  key={key}
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full"
                  onClick={() =>
                    form.setValue("script", template.text, {
                      shouldDirty: true,
                      shouldValidate: true,
                    })
                  }
                >
                  {template.label}
                </Button>
              ))}
            </div>

            <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
              <SelectField
                form={form}
                name="video_language"
                label="Spoken language"
                options={VIDEO_LANGUAGE_OPTIONS}
              />
              <SelectField
                form={form}
                name="language"
                label="Output language"
                options={LANGUAGE_OPTIONS}
              />
              <SelectField form={form} name="region" label="Target region" options={REGION_OPTIONS} />
            </div>
          </div>
        </Card>

        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <Card className="overflow-hidden">
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 p-5 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-6"
                aria-expanded={advancedOpen}
              >
                <span className="flex min-w-0 items-start gap-3">
                  <IconBadge icon={SlidersHorizontal} tone="neutral" />
                  <span className="min-w-0 space-y-1 pt-0.5">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-display text-base font-semibold text-foreground">
                        Creator brief (optional)
                      </span>
                      {filledBrief ? (
                        <span className="rounded-full bg-tone-ok-bg px-2 py-0.5 text-[0.6875rem] font-medium text-tone-ok">
                          {filledBrief} filled
                        </span>
                      ) : null}
                    </span>
                    <span className="block text-[0.8125rem] leading-relaxed text-muted-foreground">
                      Fifteen optional fields. Anything you supply is marked{" "}
                      <strong className="font-semibold text-tone-ok">Creator-entered</strong> instead of{" "}
                      <strong className="font-semibold text-tone-warn">Inferred</strong>.
                    </span>
                  </span>
                </span>
                <ChevronDown
                  className={cn(
                    "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
                    advancedOpen && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
            </CollapsibleTrigger>

            <CollapsibleContent>
              <div className="space-y-7 border-t border-border p-5 sm:p-6">
                <BriefGroup title="Audience & promise">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <TextField
                      form={form}
                      name="target_audience"
                      label="Target audience"
                      placeholder="Who is this video for?"
                      maxLength={200}
                    />
                    <TextField
                      form={form}
                      name="viewer_promise"
                      label="Viewer promise"
                      placeholder="What will they get, learn, feel, or see?"
                      maxLength={300}
                    />
                    <TextField
                      form={form}
                      name="unique_angle"
                      label="Unique angle"
                      placeholder="What makes this different?"
                      maxLength={300}
                    />
                    <TextField
                      form={form}
                      name="proof"
                      label="Proof or footage"
                      placeholder="Result, experience, or footage you have"
                      maxLength={300}
                    />
                  </div>
                </BriefGroup>

                <BriefGroup title="Format & style">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <SelectField
                      form={form}
                      name="video_format"
                      label="Video format"
                      options={FORMAT_OPTIONS}
                    />
                    <SelectField
                      form={form}
                      name="title_style"
                      label="Title style"
                      options={TITLE_STYLE_OPTIONS}
                    />
                    <TextField
                      form={form}
                      name="thumbnail_idea"
                      label="Thumbnail direction"
                      placeholder="Optional thumbnail idea"
                      maxLength={200}
                    />
                    <TextField
                      form={form}
                      name="duration_seconds"
                      label="Intended duration (seconds)"
                      placeholder="e.g. 45"
                      hint="Used for pacing checks."
                    />
                    <SelectField
                      form={form}
                      name="voice_over"
                      label="Voice-over"
                      options={VOICE_OVER_OPTIONS}
                    />
                    <TextField
                      form={form}
                      name="creator_intent"
                      label="Creator intent"
                      placeholder="What do you want this video to do?"
                      maxLength={500}
                    />
                  </div>
                </BriefGroup>

                <BriefGroup title="Source fidelity">
                  <AreaField
                    form={form}
                    name="exact_quote"
                    label="Exact quote"
                    placeholder="Text that must be preserved word for word"
                    hint="Quote fidelity is checked against this; it is never silently rewritten."
                  />
                </BriefGroup>

                <BriefGroup title="Guardrails">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <AreaField
                      form={form}
                      name="visual_requirements"
                      label="Visual requirements"
                      rows={2}
                    />
                    <AreaField form={form} name="factual_claims" label="Factual claims" rows={2} />
                    <AreaField
                      form={form}
                      name="claim_restrictions"
                      label="Claim restrictions"
                      rows={2}
                      hint="Claims the package must not make."
                    />
                    <AreaField
                      form={form}
                      name="content_constraints"
                      label="Content constraints"
                      rows={2}
                    />
                  </div>
                </BriefGroup>
              </div>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-card sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <p className="max-w-md text-[0.8125rem] leading-relaxed text-muted-foreground">
            One run spends YouTube API quota and several Gemini calls. Nothing is uploaded or
            published.
          </p>
          <Button
            type="button"
            variant="gradient"
            size="xl"
            onClick={onSubmit}
            disabled={isPending}
            className="shrink-0"
          >
            <Sparkles aria-hidden="true" />
            {isPending ? "Analyzing…" : "Generate SEO package"}
          </Button>
        </div>
      </div>

      <aside className="space-y-5 xl:sticky xl:top-24 xl:self-start">
        <Panel
          icon={Sparkles}
          iconTone="gradient"
          title="What you'll get"
          description="One run produces a reviewed package across eight stages."
        >
          <ul className="space-y-3">
            {OUTPUTS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span
                  className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground"
                  aria-hidden="true"
                >
                  <Icon className="size-3.5" />
                </span>
                <span className="min-w-0">
                  <span className="block text-[0.8125rem] font-medium text-foreground">{title}</span>
                  <span className="block text-xs leading-relaxed text-muted-foreground">{body}</span>
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel
          icon={ShieldCheck}
          iconTone="ok"
          title="Honest by design"
          description="Every value is labelled by where it came from, and guesses never pose as measurements."
        >
          <div className="flex flex-wrap gap-1.5">
            <EvidenceChip tone="ok">Creator-entered</EvidenceChip>
            <EvidenceChip tone="info">Public observation</EvidenceChip>
            <EvidenceChip tone="warn">Heuristic</EvidenceChip>
            <EvidenceChip tone="neutral">Unavailable</EvidenceChip>
          </div>
        </Panel>
      </aside>
    </div>
  );
}
