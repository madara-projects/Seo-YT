import { useState } from "react";
import { Controller, type UseFormReturn } from "react-hook-form";
import { ChevronDown, Sparkles, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
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

/**
 * Radix Select treats "" as "no value", so an explicit "Not specified" option
 * needs a sentinel that is mapped back to "" before it reaches the form.
 */
const NONE = "__none";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-[11px] font-medium text-tone-bad">
      {message}
    </p>
  );
}

function SelectField({
  form,
  name,
  label,
  options,
  hint,
}: {
  form: Form;
  name: keyof CreatorFormValues;
  label: string;
  options: { value: string; label: string }[];
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={name}>{label}</Label>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <Select
            value={field.value ? String(field.value) : NONE}
            onValueChange={(value) => field.onChange(value === NONE ? "" : value)}
          >
            <SelectTrigger id={name} aria-label={label}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value || NONE} value={option.value || NONE}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
      {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
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
  return (
    <div className="space-y-1.5">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        {...form.register(name)}
      />
      {hint && !error ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
      <FieldError message={error as string | undefined} />
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
  return (
    <div className="space-y-1.5">
      <Label htmlFor={name}>{label}</Label>
      <Textarea
        id={name}
        rows={rows}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        {...form.register(name)}
      />
      {hint && !error ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
      <FieldError message={error as string | undefined} />
    </div>
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

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Script or video idea</CardTitle>
          <CardDescription>
            The only required input. Everything else sharpens the brief and is optional — anything
            you leave blank is inferred and clearly labelled as such.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="script">Script</Label>
              <span
                className={cn(
                  "numeric text-[11px]",
                  script.length > 12000 ? "text-tone-bad" : "text-muted-foreground",
                )}
              >
                {script.length.toLocaleString()} / 12,000
              </span>
            </div>
            <Textarea
              id="script"
              rows={7}
              placeholder="Paste the script, or describe the video idea in a sentence or two…"
              aria-invalid={Boolean(scriptError)}
              aria-describedby="script-help"
              className="resize-y"
              {...form.register("script")}
            />
            <FieldError message={scriptError} />
            <p id="script-help" className="text-[11px] text-muted-foreground">
              Research queries are derived from this text.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
              <Wand2 className="h-3.5 w-3.5" aria-hidden="true" />
              Sample ideas
            </span>
            {Object.entries(TEMPLATE_TEXT).map(([key, template]) => (
              <Button
                key={key}
                type="button"
                variant="outline"
                size="sm"
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

          <div className="grid gap-4 sm:grid-cols-3">
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
        </CardContent>
      </Card>

      <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <Card>
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 rounded-t-xl p-5 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-expanded={advancedOpen}
            >
              <span className="space-y-1">
                <span className="block text-sm font-semibold">Creator brief (optional)</span>
                <span className="block text-xs text-muted-foreground">
                  Fifteen optional fields. Anything you supply is marked{" "}
                  <strong className="font-semibold text-tone-ok">Creator-entered</strong> instead of{" "}
                  <strong className="font-semibold text-tone-warn">Inferred</strong>.
                </span>
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                  advancedOpen && "rotate-180",
                )}
                aria-hidden="true"
              />
            </button>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <CardContent className="space-y-5 border-t border-border pt-5">
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

              <AreaField
                form={form}
                name="exact_quote"
                label="Exact quote"
                placeholder="Text that must be preserved word for word"
                hint="Quote fidelity is checked against this; it is never silently rewritten."
              />
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
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button type="button" size="lg" onClick={onSubmit} disabled={isPending} className="sm:w-auto">
          <Sparkles aria-hidden="true" />
          {isPending ? "Analyzing…" : "Generate SEO package"}
        </Button>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          One run spends YouTube API quota and several Gemini calls. Nothing is uploaded or
          published.
        </p>
      </div>
    </div>
  );
}
