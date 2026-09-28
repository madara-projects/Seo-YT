import { OpportunityBreakdownDisclosure, OpportunityBreakdownView } from "@/components/common/OpportunityBreakdown";
import { CardSkeleton, UnavailableNote } from "@/components/common/States";
import { useHistoryRun } from "@/hooks/useHistory";
import { asObject } from "@/lib/utils";
import { NO_STORED_BREAKDOWN, parseOpportunityBreakdown } from "@/lib/opportunityFormat";
import type { HistoryRunDetail } from "@/api/historyTypes";

/** The breakdown saved with a package, or null when it was saved before breakdowns were. */
function storedBreakdown(run: HistoryRunDetail | undefined) {
  const score = asObject(asObject(asObject(run?.package).opportunity_gap_analysis).opportunity_score);
  return parseOpportunityBreakdown(score.breakdown);
}

/** In the package detail: the saved score's inputs, missing data and confidence. */
export function HistoryOpportunityBreakdown({ run }: { run: HistoryRunDetail }) {
  return (
    <OpportunityBreakdownDisclosure
      breakdown={storedBreakdown(run)}
      className="rounded-xl border border-border bg-card p-3.5"
    />
  );
}

/**
 * On a History row: loads the package only when its score inputs are asked
 * for, since the list itself carries no package.
 */
export function RunOpportunityInputs({ runId, id }: { runId: number; id?: string }) {
  const run = useHistoryRun(runId);
  const breakdown = storedBreakdown(run.data);

  return (
    <div id={id} className="rounded-xl border border-border bg-card p-3.5">
      {run.isPending ? (
        <CardSkeleton rows={2} />
      ) : run.isError ? (
        <UnavailableNote>The score inputs could not be loaded.</UnavailableNote>
      ) : breakdown ? (
        <OpportunityBreakdownView breakdown={breakdown} />
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">{NO_STORED_BREAKDOWN}</p>
      )}
    </div>
  );
}
