import { Link } from "react-router-dom";
import { Clapperboard, Library, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { SelectableItem } from "@/components/common/SelectableItem";
import { ListBody, RecordList } from "@/components/research/ListPanel";
import { relativeTime } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { partsLabel, quoteExcerpt, sourceChip } from "@/lib/aiShortsFormat";
import { cn } from "@/lib/utils";
import type { AiShortsPlanSummary } from "@/api/aiShortsTypes";

/**
 * The newest saved plans. Choosing one loads it beside the form; each row also
 * opens its History package and can be deleted (after confirming).
 */
export function RecentPlans({
  plans,
  isPending,
  isFetching,
  error,
  selectedId,
  onSelect,
  onDelete,
  onRefresh,
}: {
  plans: AiShortsPlanSummary[];
  isPending: boolean;
  isFetching: boolean;
  error: unknown;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDelete: (plan: AiShortsPlanSummary) => void;
  onRefresh: () => void;
}) {
  return (
    <Panel
      icon={Clapperboard}
      title="Recent AI Shorts"
      description="Saved automatically, newest first."
      aside={
        <Button variant="ghost" size="icon-sm" onClick={onRefresh} disabled={isFetching} aria-label="Refresh recent AI Shorts">
          <RefreshCw className={cn(isFetching && "animate-spin")} aria-hidden="true" />
        </Button>
      }
      contentClassName="px-3 pb-3 sm:px-3 sm:pb-3"
    >
      <ListBody
        isPending={isPending}
        error={error}
        errorFallback="Recent AI Shorts are unavailable."
        onRetry={onRefresh}
        isEmpty={!plans.length}
        empty="No AI Shorts yet. Write the first from a quote and it will appear here."
      >
        <RecordList label="Recent AI Shorts">
          {plans.map((plan) => {
            const excerpt = quoteExcerpt(plan.quote);
            const draft = plan.generation_source === "fallback";
            return (
              <li key={plan.id} className="flex items-start gap-1" data-testid="ai-shorts-plan">
                <SelectableItem
                  selected={plan.id === selectedId}
                  onSelect={() => onSelect(plan.id)}
                  className="min-w-0 flex-1"
                >
                  <span className="line-clamp-2 text-sm font-medium leading-snug text-foreground">“{excerpt}”</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                    <span className="numeric">{partsLabel(plan.parts, plan.total_seconds)}</span>
                    <EvidenceChip tone={sourceChip(plan.generation_source).tone}>{draft ? "Draft" : "Gemini"}</EvidenceChip>
                  </span>
                  <span className="mt-1 block text-[0.6875rem] text-muted-foreground" title={historyDate(plan.created_at)}>
                    {relativeTime(plan.created_at)}
                  </span>
                </SelectableItem>
                {/* Beside the row, not inside it: a button can't hold other controls. */}
                <span className="flex shrink-0 flex-col gap-0.5 pt-1.5">
                  {plan.analysis_run_id ? (
                    <Button asChild variant="ghost" size="icon-sm" title="Open in History">
                      <Link to={`/history?run=${plan.analysis_run_id}`} aria-label={`Open in History: ${excerpt}`}>
                        <Library aria-hidden="true" />
                      </Link>
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Delete"
                    aria-label={`Delete: ${excerpt}`}
                    onClick={() => onDelete(plan)}
                    className="hover:text-tone-bad"
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </span>
              </li>
            );
          })}
        </RecordList>
      </ListBody>
    </Panel>
  );
}
