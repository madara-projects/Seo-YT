import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { useMutationState } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Search, Telescope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { FormField } from "@/components/common/FormField";
import { OptionSelect } from "@/components/common/OptionSelect";
import { Panel } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useResearchDemand } from "@/hooks/useDemand";
import { mutationKeys } from "@/hooks/queryKeys";
import { formatDuration, useElapsedSeconds } from "@/hooks/useElapsed";
import {
  DEMAND_FORMAT_OPTIONS,
  DEMAND_LANGUAGE_OPTIONS,
  DEMAND_REGION_OPTIONS,
  demandFormDefaults,
  demandFormSchema,
  type DemandFormValues,
} from "@/schemas/demand";
import type { LabelledOption } from "@/lib/labels";
import type { DemandSnapshot } from "@/api/researchTypes";

function ChoiceField({
  form,
  name,
  label,
  options,
}: {
  form: UseFormReturn<DemandFormValues>;
  name: "language" | "format" | "region";
  label: string;
  options: readonly LabelledOption[];
}) {
  const id = `demand-${name}`;
  return (
    <FormField id={id} label={label}>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <OptionSelect id={id} ariaLabel={label} value={field.value} onValueChange={field.onChange} options={options} />
        )}
      />
    </FormField>
  );
}

export function DemandForm({ onResearched }: { onResearched: (snapshot: DemandSnapshot) => void }) {
  const form = useForm<DemandFormValues>({
    resolver: zodResolver(demandFormSchema),
    defaultValues: demandFormDefaults,
    mode: "onBlur",
  });
  const research = useResearchDemand();
  // A research run started before the page was left is still in the mutation
  // cache: it keeps the button disabled, so the same quota isn't spent twice.
  const running = useMutationState({
    filters: { mutationKey: mutationKeys.demandResearch, status: "pending" },
    select: (mutation) => mutation.state.submittedAt,
  });
  const inFlight = running.length > 0;
  const elapsed = useElapsedSeconds(inFlight, inFlight ? Math.max(...running) : undefined);
  const topicError = form.formState.errors.topic?.message;
  const audienceError = form.formState.errors.audience_context?.message;

  // Per-call callbacks don't run once the form has unmounted, so a run that
  // finishes after the creator has moved on never pulls them back here. A
  // failure is shown below the form with its request ID.
  const submit = form.handleSubmit((values) => {
    if (inFlight) return;
    research.mutate(values, {
      onSuccess: (data) => {
        if (data.research?.id) onResearched(data.research);
      },
    });
  });

  return (
    <Panel
      icon={Telescope}
      title="Research a topic"
      description="Check observed interest before you commit production time. The result is dated and never changes, so you can compare topics fairly later."
      aside={<EvidenceChip tone="info">Observed evidence only</EvidenceChip>}
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <FormField id="demand-topic" label="Topic or phrase" error={topicError} className="sm:col-span-2 xl:col-span-4">
            <Input
              id="demand-topic"
              placeholder="e.g. painful love quotes"
              maxLength={300}
              aria-invalid={Boolean(topicError)}
              autoComplete="off"
              className="text-[0.9375rem]"
              {...form.register("topic")}
            />
          </FormField>
          <ChoiceField form={form} name="language" label="Language" options={DEMAND_LANGUAGE_OPTIONS} />
          <ChoiceField form={form} name="format" label="Format" options={DEMAND_FORMAT_OPTIONS} />
          <ChoiceField form={form} name="region" label="Region" options={DEMAND_REGION_OPTIONS} />
          <FormField id="demand-audience" label="Audience context" error={audienceError}>
            <Input
              id="demand-audience"
              placeholder="Optional"
              maxLength={500}
              aria-invalid={Boolean(audienceError)}
              {...form.register("audience_context")}
            />
          </FormField>
        </div>

        {research.isError ? (
          <ErrorState
            message={apiErrorMessage(research.error, "Demand research failed.")}
            requestId={apiRequestId(research.error)}
          />
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
            {inFlight
              ? `Searching YouTube and scoring the results… ${formatDuration(elapsed)}`
              : "Runs live YouTube searches, which spend API quota. Nothing is invented: there is no search-volume data, only what was observed."}
          </p>
          <Button type="submit" variant="gradient" disabled={inFlight} className="shrink-0">
            {inFlight ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : (
              <Search aria-hidden="true" />
            )}
            {inFlight ? "Researching…" : "Research demand"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}
