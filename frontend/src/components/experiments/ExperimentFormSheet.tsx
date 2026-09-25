import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FlaskConical, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { FormField, FormSection } from "@/components/common/FormField";
import { OptionSelect } from "@/components/common/OptionSelect";
import { ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useCreateExperiment } from "@/hooks/useExperiments";
import {
  EXPERIMENT_METRIC_OPTIONS,
  EXPERIMENT_MODE_OPTIONS,
  EXPERIMENT_VARIABLE_OPTIONS,
  EXPERIMENT_WINDOW_OPTIONS,
  experimentFormDefaults,
  experimentFormSchema,
  experimentPayload,
  type ExperimentFormValues,
} from "@/schemas/experiment";
import type { LabelledOption } from "@/lib/labels";
import type { Experiment } from "@/api/experimentTypes";

type SelectName = "mode" | "variable" | "success_metric" | "observation_window";

/** Creates a draft comparison. Nothing is measured until videos are assigned. */
export function ExperimentFormSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (experiment: Experiment) => void;
}) {
  const form = useForm<ExperimentFormValues>({
    resolver: zodResolver(experimentFormSchema),
    defaultValues: experimentFormDefaults,
    mode: "onBlur",
  });
  const create = useCreateExperiment();
  const errors = form.formState.errors;

  const submit = form.handleSubmit(async (values) => {
    try {
      const data = await create.mutateAsync(experimentPayload(values));
      toast.success("Comparison created as a draft.");
      form.reset(experimentFormDefaults);
      create.reset();
      onOpenChange(false);
      if (data.experiment) onCreated(data.experiment);
    } catch {
      /* Shown above the buttons with its request ID. */
    }
  });

  const select = (name: SelectName, label: string, options: LabelledOption[], hint?: string) => (
    <FormField id={`experiment-${name}`} label={label} hint={hint}>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <OptionSelect
            id={`experiment-${name}`}
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
      <SheetContent data-testid="experiment-form" className="sm:max-w-xl">
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
          <div className="relative overflow-hidden border-b border-border px-5 py-5 sm:px-7">
            <div
              className="pointer-events-none absolute -right-16 -top-24 size-64 rounded-full bg-brand-gradient opacity-15 blur-3xl"
              aria-hidden="true"
            />
            <div className="relative flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em] text-brand">
                  <FlaskConical className="size-3.5" aria-hidden="true" />
                  New comparison
                </p>
                <SheetTitle className="font-display text-xl font-semibold leading-snug tracking-tight text-foreground">
                  Test one decision at a time
                </SheetTitle>
                <SheetDescription className="text-xs leading-relaxed text-muted-foreground">
                  For example, a direct title against a question title. It starts as a draft; you assign your own
                  published videos to each side afterwards.
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
            <FormSection title="The question">
              <FormField id="experiment-name" label="Name" error={errors.name?.message}>
                <Input
                  id="experiment-name"
                  maxLength={160}
                  placeholder="e.g. Question titles vs statements"
                  aria-invalid={Boolean(errors.name)}
                  autoComplete="off"
                  {...form.register("name")}
                />
              </FormField>
              <FormField
                id="experiment-hypothesis"
                label="Hypothesis"
                error={errors.hypothesis?.message}
                hint="What association do you expect? It is tested, never assumed."
              >
                <Textarea
                  id="experiment-hypothesis"
                  maxLength={1000}
                  rows={3}
                  aria-invalid={Boolean(errors.hypothesis)}
                  {...form.register("hypothesis")}
                />
              </FormField>
              {select(
                "mode",
                "Comparison type",
                EXPERIMENT_MODE_OPTIONS,
                "Planned: you decide each video's side before publishing. Observational: you group videos that already exist.",
              )}
            </FormSection>

            <FormSection title="The two sides">
              {select("variable", "What changes", EXPERIMENT_VARIABLE_OPTIONS)}
              <FormField id="experiment-control" label="Control" error={errors.control_definition?.message}>
                <Input
                  id="experiment-control"
                  maxLength={1000}
                  placeholder="What you normally do"
                  aria-invalid={Boolean(errors.control_definition)}
                  autoComplete="off"
                  {...form.register("control_definition")}
                />
              </FormField>
              <FormField id="experiment-variant" label="Variant" error={errors.variant_definition?.message}>
                <Input
                  id="experiment-variant"
                  maxLength={1000}
                  placeholder="The one thing you change"
                  aria-invalid={Boolean(errors.variant_definition)}
                  autoComplete="off"
                  {...form.register("variant_definition")}
                />
              </FormField>
            </FormSection>

            <FormSection title="How it's measured">
              <div className="grid gap-4 sm:grid-cols-2">
                {select("success_metric", "Primary metric", EXPERIMENT_METRIC_OPTIONS)}
                {select("observation_window", "Comparable window", EXPERIMENT_WINDOW_OPTIONS)}
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Both sides are compared over the same completed window, from verified YouTube analytics. At least
                five videos per side are needed before any direction is reported.
              </p>
            </FormSection>
          </div>

          <div className="space-y-3 border-t border-border bg-card/60 px-5 py-4 sm:px-7">
            {create.isError ? (
              <ErrorState
                message={apiErrorMessage(create.error, "Could not create this comparison.")}
                requestId={apiRequestId(create.error)}
              />
            ) : null}
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
                Cancel
              </Button>
              <Button type="submit" variant="gradient" disabled={create.isPending}>
                {create.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                {create.isPending ? "Creating…" : "Create comparison"}
              </Button>
            </div>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
