import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Lightbulb, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { FormField, FormSection } from "@/components/common/FormField";
import { OptionSelect } from "@/components/common/OptionSelect";
import { ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useCreateIdea } from "@/hooks/useIdeas";
import {
  IDEA_FORMAT_OPTIONS,
  IDEA_LANGUAGE_OPTIONS,
  IDEA_REGION_OPTIONS,
  ideaFormDefaults,
  ideaFormSchema,
  ideaPayload,
  type IdeaFormValues,
} from "@/schemas/idea";
import type { LabelledOption } from "@/lib/labels";
import type { Idea } from "@/api/ideaTypes";

/**
 * Adds an idea to the backlog. Saving only stores it: nothing is researched or
 * generated, and no quota is spent, until the creator asks from the idea.
 * Closing without saving keeps the draft for next time.
 */
export function IdeaFormSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (idea: Idea) => void;
}) {
  const form = useForm<IdeaFormValues>({
    resolver: zodResolver(ideaFormSchema),
    defaultValues: ideaFormDefaults,
    mode: "onBlur",
  });
  const create = useCreateIdea();
  const errors = form.formState.errors;

  // A failure is shown above the buttons with its request ID.
  const submit = form.handleSubmit((values) => {
    // Per-call callbacks don't run once the sheet has unmounted, so a save that
    // finishes after the creator has left never pulls them back to this page.
    create.mutate(ideaPayload(values), {
      onSuccess: (data) => {
        toast.success("Idea saved to your backlog.");
        form.reset(ideaFormDefaults);
        create.reset();
        onOpenChange(false);
        if (data.idea) onCreated(data.idea);
      },
    });
  });

  const text = (name: keyof IdeaFormValues, max: number, placeholder?: string) => (
    <Input
      id={`idea-${name}`}
      maxLength={max}
      placeholder={placeholder}
      aria-invalid={Boolean(errors[name])}
      autoComplete="off"
      {...form.register(name)}
    />
  );

  const select = (name: "format" | "language" | "region", label: string, options: readonly LabelledOption[]) => (
    <FormField id={`idea-${name}`} label={label}>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <OptionSelect
            id={`idea-${name}`}
            ariaLabel={label}
            value={field.value}
            onValueChange={field.onChange}
            options={options}
          />
        )}
      />
    </FormField>
  );

  return (
    <Sheet open={open} onOpenChange={(next) => (create.isPending ? undefined : onOpenChange(next))}>
      <SheetContent data-testid="idea-form" className="sm:max-w-xl">
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
          <div className="relative overflow-hidden border-b border-border px-5 py-5 sm:px-7">
            <div
              className="pointer-events-none absolute -right-16 -top-24 size-64 rounded-full bg-brand-gradient opacity-15 blur-3xl"
              aria-hidden="true"
            />
            <div className="relative flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em] text-brand">
                  <Lightbulb className="size-3.5" aria-hidden="true" />
                  New idea
                </p>
                <SheetTitle className="font-display text-xl font-semibold leading-snug tracking-tight text-foreground">
                  Add an original idea
                </SheetTitle>
                <SheetDescription className="text-xs leading-relaxed text-muted-foreground">
                  Saving only stores the idea in your backlog. Nothing is researched or generated, and no
                  quota is spent, until you ask.
                </SheetDescription>
              </div>
              <SheetClose asChild>
                <Button variant="ghost" size="icon" aria-label="Close" className="-mr-2 -mt-1" disabled={create.isPending}>
                  <X aria-hidden="true" />
                </Button>
              </SheetClose>
            </div>
          </div>

          <div className="flex-1 space-y-7 overflow-y-auto px-5 py-6 scrollbar-thin sm:px-7">
            <FormSection title="The idea">
              <FormField id="idea-topic" label="Topic" error={errors.topic?.message}>
                {text("topic", 300, "What is the video actually about?")}
              </FormField>
              <FormField
                id="idea-notes"
                label="Notes or script outline"
                optional
                error={errors.notes?.message}
                hint="Scenes, spoken lines, proof or constraints. Research and generation read these."
              >
                <Textarea id="idea-notes" maxLength={5000} rows={4} aria-invalid={Boolean(errors.notes)} {...form.register("notes")} />
              </FormField>
            </FormSection>

            <FormSection title="Format">
              <div className="grid gap-4 sm:grid-cols-2">
                {select("format", "Format", IDEA_FORMAT_OPTIONS)}
                {select("language", "Language", IDEA_LANGUAGE_OPTIONS)}
                {select("region", "Region", IDEA_REGION_OPTIONS)}
                <FormField
                  id="idea-target_duration_seconds"
                  label="Target duration (seconds)"
                  optional
                  error={errors.target_duration_seconds?.message}
                >
                  <Input
                    id="idea-target_duration_seconds"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={86400}
                    placeholder="e.g. 45"
                    aria-invalid={Boolean(errors.target_duration_seconds)}
                    {...form.register("target_duration_seconds")}
                  />
                </FormField>
              </div>
            </FormSection>

            <FormSection title="Angles" description="Optional. How different viewers would come to this video.">
              <FormField id="idea-search_angle" label="Search angle" hint="What someone would type to find it." error={errors.search_angle?.message}>
                {text("search_angle", 500)}
              </FormField>
              <FormField id="idea-browse_angle" label="Browse angle" hint="Why it would stand out in a feed." error={errors.browse_angle?.message}>
                {text("browse_angle", 500)}
              </FormField>
              <FormField
                id="idea-audience_angle"
                label="Existing audience angle"
                hint="Why your current viewers would click."
                error={errors.audience_angle?.message}
              >
                {text("audience_angle", 500)}
              </FormField>
            </FormSection>

            <FormSection title="Production plan" description="Optional. Only what you actually plan to show or say.">
              <FormField id="idea-visual_or_background" label="Visual or background" error={errors.visual_or_background?.message}>
                {text("visual_or_background", 1000)}
              </FormField>
              <FormField
                id="idea-on_screen_text"
                label="On-screen text"
                hint="The exact wording, if you know it."
                error={errors.on_screen_text?.message}
              >
                <Textarea
                  id="idea-on_screen_text"
                  maxLength={2000}
                  rows={3}
                  aria-invalid={Boolean(errors.on_screen_text)}
                  {...form.register("on_screen_text")}
                />
              </FormField>
              <FormField id="idea-emotion_or_intent" label="Emotion or intent" error={errors.emotion_or_intent?.message}>
                {text("emotion_or_intent", 300)}
              </FormField>
            </FormSection>
          </div>

          <div className="space-y-3 border-t border-border bg-card/60 px-5 py-4 sm:px-7">
            {create.isError ? (
              <ErrorState
                message={apiErrorMessage(create.error, "Could not save this idea.")}
                requestId={apiRequestId(create.error)}
              />
            ) : null}
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
                Cancel
              </Button>
              <Button type="submit" variant="gradient" disabled={create.isPending}>
                {create.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                {create.isPending ? "Saving…" : "Save idea"}
              </Button>
            </div>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
