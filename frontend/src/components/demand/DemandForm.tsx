import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Search, Telescope } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useResearchDemand } from "@/hooks/useDemand";
import { formatDuration, useElapsedSeconds } from "@/hooks/useElapsed";
import {
  DEMAND_FORMAT_OPTIONS,
  DEMAND_LANGUAGE_OPTIONS,
  DEMAND_REGION_OPTIONS,
  demandFormDefaults,
  demandFormSchema,
  type DemandFormValues,
} from "@/schemas/demand";
import type { DemandSnapshot } from "@/api/researchTypes";

/** Radix Select treats "" as "no value", so "any" needs a sentinel. */
const ANY = "__any";

function OptionSelect({
  form,
  name,
  label,
  options,
}: {
  form: UseFormReturn<DemandFormValues>;
  name: "language" | "format" | "region";
  label: string;
  options: { value: string; label: string }[];
}) {
  const id = `demand-${name}`;
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <Select
            value={field.value || ANY}
            onValueChange={(value) => field.onChange(value === ANY ? "" : value)}
          >
            <SelectTrigger id={id} aria-label={label}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value || ANY} value={option.value || ANY}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </div>
  );
}

export function DemandForm({ onResearched }: { onResearched: (snapshot: DemandSnapshot) => void }) {
  const form = useForm<DemandFormValues>({
    resolver: zodResolver(demandFormSchema),
    defaultValues: demandFormDefaults,
    mode: "onBlur",
  });
  const research = useResearchDemand();
  const elapsed = useElapsedSeconds(research.isPending);
  const topicError = form.formState.errors.topic?.message;
  const audienceError = form.formState.errors.audience_context?.message;

  const submit = form.handleSubmit(async (values) => {
    try {
      const data = await research.mutateAsync(values);
      if (data.research?.id) {
        toast.success("Demand snapshot saved.");
        onResearched(data.research);
      }
    } catch {
      /* Shown below the form with its request ID. */
    }
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
          <div className="space-y-2 sm:col-span-2 xl:col-span-4">
            <Label htmlFor="demand-topic">Topic or phrase</Label>
            <Input
              id="demand-topic"
              placeholder="e.g. painful love quotes"
              maxLength={300}
              aria-invalid={Boolean(topicError)}
              autoComplete="off"
              className="text-[0.9375rem]"
              {...form.register("topic")}
            />
            {topicError ? (
              <p role="alert" className="text-xs font-medium text-tone-bad">
                {topicError}
              </p>
            ) : null}
          </div>
          <OptionSelect form={form} name="language" label="Language" options={DEMAND_LANGUAGE_OPTIONS} />
          <OptionSelect form={form} name="format" label="Format" options={DEMAND_FORMAT_OPTIONS} />
          <OptionSelect form={form} name="region" label="Region" options={DEMAND_REGION_OPTIONS} />
          <div className="space-y-2">
            <Label htmlFor="demand-audience">Audience context</Label>
            <Input
              id="demand-audience"
              placeholder="Optional"
              maxLength={500}
              aria-invalid={Boolean(audienceError)}
              {...form.register("audience_context")}
            />
            {audienceError ? (
              <p role="alert" className="text-xs font-medium text-tone-bad">
                {audienceError}
              </p>
            ) : null}
          </div>
        </div>

        {research.isError ? (
          <ErrorState
            message={apiErrorMessage(research.error, "Demand research failed.")}
            requestId={apiRequestId(research.error)}
          />
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
            {research.isPending
              ? `Searching YouTube and scoring the results… ${formatDuration(elapsed)}`
              : "Runs live YouTube searches, which spend API quota. Nothing is invented: there is no search-volume data, only what was observed."}
          </p>
          <Button type="submit" variant="gradient" disabled={research.isPending} className="shrink-0">
            {research.isPending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : (
              <Search aria-hidden="true" />
            )}
            {research.isPending ? "Researching…" : "Research demand"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}
