import { History } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { SelectableItem } from "@/components/common/SelectableItem";
import { ListPanel, RecordList } from "@/components/research/ListPanel";
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
    <ListPanel
      icon={History}
      title="Snapshots"
      description="Newest first."
      refreshLabel="Refresh snapshots"
      onRefresh={onRefresh}
      isFetching={isFetching}
      list={{
        isPending,
        error,
        errorFallback: "Demand history is unavailable.",
        isEmpty: !snapshots.length,
        empty: "No demand snapshots yet. Research a topic above and its dated evidence will appear here.",
      }}
    >
      <RecordList label="Demand snapshots">
        {snapshots.map((snapshot) => {
          const classification = classificationLabel(snapshot.classification);
          return (
            <li key={snapshot.id}>
              <SelectableItem
                selected={snapshot.id === selectedId}
                onSelect={() => onSelect(snapshot.id)}
                data-testid="demand-snapshot"
              >
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
              </SelectableItem>
            </li>
          );
        })}
      </RecordList>
    </ListPanel>
  );
}
