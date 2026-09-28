import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { cn } from "@/lib/utils";
import {
  NO_STORED_BREAKDOWN,
  OPPORTUNITY_INPUT_WEIGHTS,
  OPPORTUNITY_STATEMENT,
  confidenceLabel,
  contributionText,
  sourceLabel,
  weightText,
} from "@/lib/opportunityFormat";
import type { OpportunityBreakdown } from "@/api/opportunityTypes";

/**
 * What an Opportunity Score is made of: each input's value, weight,
 * contribution and source, what data was missing, and how complete the
 * inputs were. The score is a local heuristic, and this says so.
 */
export function OpportunityBreakdownView({
  breakdown,
  showConfidence = true,
}: {
  breakdown: OpportunityBreakdown;
  showConfidence?: boolean;
}) {
  const confidence = confidenceLabel(breakdown.confidence);
  // An unmeasured score has no inputs worth showing: they were never measured.
  const scored = breakdown.score !== null;

  return (
    <div className="space-y-3 text-xs leading-relaxed text-muted-foreground">
      <p>{breakdown.statement}</p>
      {showConfidence ? <EvidenceChip tone={confidence.tone}>{confidence.label}</EvidenceChip> : null}
      {breakdown.confidence_reason ? <p>{breakdown.confidence_reason}</p> : null}

      {scored ? (
        <>
          <ul aria-label="Score inputs" className="space-y-2">
            {breakdown.inputs.map((input) => {
              const source = sourceLabel(input.source);
              return (
                <li
                  key={input.key}
                  data-testid="opportunity-input"
                  className="rounded-lg border border-border/80 bg-elevated px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <span className="font-medium text-foreground">{input.name}</span>
                    <EvidenceChip tone={source.tone}>{source.label}</EvidenceChip>
                  </div>
                  <p className="numeric mt-1 text-foreground">{contributionText(input)}</p>
                  {input.basis ? <p className="mt-0.5">{input.basis}</p> : null}
                </li>
              );
            })}
          </ul>
          <p className="numeric font-semibold text-foreground">Total: {breakdown.score?.toFixed(1)} / 100</p>
        </>
      ) : null}

      {breakdown.warnings.length ? (
        <div className="space-y-1">
          <p className="font-medium text-foreground">Missing data</p>
          <ul aria-label="Missing data" className="list-disc space-y-1 pl-4">
            {breakdown.warnings.map((warning, index) => (
              <li key={`${index}-${warning}`}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>No inputs were missing data.</p>
      )}
    </div>
  );
}

function DisclosureTrigger({ open, label }: { open: boolean; label: string }) {
  return (
    <CollapsibleTrigger asChild>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md text-xs font-medium text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {label}
        <ChevronDown className={cn("size-3.5 transition-transform duration-200", open && "rotate-180")} aria-hidden="true" />
      </button>
    </CollapsibleTrigger>
  );
}

/**
 * The confidence beside a score, and its breakdown one click away. A package
 * without a stored breakdown says so instead of guessing one.
 */
export function OpportunityBreakdownDisclosure({
  breakdown,
  missingText = NO_STORED_BREAKDOWN,
  className,
}: {
  breakdown: OpportunityBreakdown | null;
  missingText?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const confidence = breakdown ? confidenceLabel(breakdown.confidence) : null;
  const warnings = breakdown?.warnings.length ?? 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        {confidence ? <EvidenceChip tone={confidence.tone}>{confidence.label}</EvidenceChip> : null}
        {warnings ? (
          <EvidenceChip tone="neutral">
            {warnings} missing-data {warnings === 1 ? "note" : "notes"}
          </EvidenceChip>
        ) : null}
        <DisclosureTrigger open={open} label="Why this score?" />
      </div>
      <CollapsibleContent>
        {breakdown ? (
          <OpportunityBreakdownView breakdown={breakdown} showConfidence={false} />
        ) : (
          <p className="text-xs leading-relaxed text-muted-foreground">{missingText}</p>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}

/** For an average of many scores: the five inputs and weights it is built from. */
export function OpportunityWeightsNote() {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="space-y-2">
      <DisclosureTrigger open={open} label="What it averages" />
      <CollapsibleContent className="space-y-2 text-xs leading-relaxed text-muted-foreground">
        <p>{OPPORTUNITY_STATEMENT}</p>
        <ul aria-label="Score inputs and weights" className="space-y-1">
          {OPPORTUNITY_INPUT_WEIGHTS.map((input) => (
            <li key={input.name} className="flex items-baseline justify-between gap-2">
              <span>
                <span className="font-medium text-foreground">{input.name}</span>
                <span className="block">{input.detail}</span>
              </span>
              <span className="numeric shrink-0 font-semibold text-foreground">{weightText(input.weight)}</span>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}
