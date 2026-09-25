import { History, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { cn } from "@/lib/utils";
import { relativeTime } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { classificationLabel, formatLabel, languageLabel } from "@/lib/demandFormat";
import type { DemandSnapshot } from "@/api/researchTypes";

export function SnapshotList({
  snapshots,
  isPending,
  error,
  isFetching,
  selectedId,
  onSelect,
  onRefresh,
}: {
  snapshots: DemandSnapshot[];
  isPending: boolean;
  error: unknown;
  isFetching: boolean;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}) {
  return (
    <Panel
      // Stays in view beside a long inspector on wide screens.
      className="lg:sticky lg:top-24 lg:self-start"
      icon={History}
      title="Snapshots"
      description="Newest first."
      aside={
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onRefresh}
          disabled={isFetching}
          aria-label="Refresh snapshots"
        >
          <RefreshCw className={cn(isFetching && "animate-spin")} aria-hidden="true" />
        </Button>
      }
      contentClassName="px-3 pb-3 sm:px-3 sm:pb-3"
    >
      {isPending ? (
        <div className="px-2 pb-2">
          <CardSkeleton rows={4} />
        </div>
      ) : error ? (
        <div className="px-2 pb-2">
          <ErrorState
            message={apiErrorMessage(error, "Demand history is unavailable.")}
            requestId={apiRequestId(error)}
            onRetry={onRefresh}
          />
        </div>
      ) : snapshots.length ? (
        <ul className="max-h-[36rem] space-y-1 overflow-y-auto scrollbar-thin" aria-label="Demand snapshots">
          {snapshots.map((snapshot) => {
            const selected = snapshot.id === selectedId;
            const classification = classificationLabel(snapshot.classification);
            return (
              <li key={snapshot.id}>
                <button
                  type="button"
                  onClick={() => onSelect(snapshot.id)}
                  aria-current={selected ? "true" : undefined}
                  data-testid="demand-snapshot"
                  className={cn(
                    "relative w-full rounded-xl px-3 py-3 text-left transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected ? "bg-brand-soft/60 ring-1 ring-inset ring-brand-border" : "hover:bg-accent",
                  )}
                >
                  {selected ? (
                    <span
                      className="absolute inset-y-3 left-0 w-1 rounded-r-full bg-brand-gradient"
                      aria-hidden="true"
                    />
                  ) : null}
                  <span className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
                      {snapshot.topic || "Untitled topic"}
                    </span>
                    <EvidenceChip tone={classification.tone} className="shrink-0">
                      {classification.label}
                    </EvidenceChip>
                  </span>
                  <span
                    className="mt-1.5 block text-xs text-muted-foreground"
                    title={historyDate(snapshot.captured_at)}
                  >
                    {languageLabel(snapshot.language)} · {formatLabel(snapshot.format)} ·{" "}
                    {relativeTime(snapshot.captured_at)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="px-2 pb-2">
          <UnavailableNote>
            No demand snapshots yet. Research a topic above and its dated evidence will appear here.
          </UnavailableNote>
        </div>
      )}
    </Panel>
  );
}
