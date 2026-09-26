import { FlaskConical } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { OptionSelect } from "@/components/common/OptionSelect";
import { SelectableItem } from "@/components/common/SelectableItem";
import { ListPanel, RecordList } from "@/components/research/ListPanel";
import {
  experimentStatusLabel,
  modeLabel,
  observationWindowLabel,
  variableLabel,
} from "@/lib/experimentFormat";
import { EXPERIMENT_MODE_FILTERS, EXPERIMENT_STATUS_FILTERS } from "@/schemas/experiment";
import type { Experiment } from "@/api/experimentTypes";

export function ExperimentList({
  experiments,
  status,
  onStatusChange,
  mode,
  onModeChange,
  isPending,
  isFetching,
  error,
  selectedId,
  onSelect,
  onRefresh,
}: {
  experiments: Experiment[];
  status: string;
  onStatusChange: (value: string) => void;
  mode: string;
  onModeChange: (value: string) => void;
  isPending: boolean;
  isFetching: boolean;
  error: unknown;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}) {
  const filtered = Boolean(status || mode);
  return (
    <ListPanel
      icon={FlaskConical}
      title="Comparisons"
      description="Most recently changed first."
      refreshLabel="Refresh comparisons"
      onRefresh={onRefresh}
      isFetching={isFetching}
      toolbar={
        <div className="grid grid-cols-2 gap-2">
          <OptionSelect
            ariaLabel="Filter by status"
            value={status}
            onValueChange={onStatusChange}
            options={EXPERIMENT_STATUS_FILTERS}
          />
          <OptionSelect ariaLabel="Filter by type" value={mode} onValueChange={onModeChange} options={EXPERIMENT_MODE_FILTERS} />
        </div>
      }
      list={{
        isPending,
        error,
        errorFallback: "Saved comparisons are unavailable.",
        isEmpty: !experiments.length,
        empty: filtered
          ? "No comparison matches these filters."
          : "No comparisons yet. Start one with New experiment when you have a real question to test.",
      }}
    >
      <RecordList label="Saved comparisons">
        {experiments.map((experiment) => {
          const state = experimentStatusLabel(experiment.status);
          const kind = modeLabel(experiment.mode);
          const counts = experiment.assignment_counts ?? {};
          return (
            <li key={experiment.id}>
              <SelectableItem
                selected={experiment.id === selectedId}
                onSelect={() => onSelect(experiment.id)}
                data-testid="experiment-item"
              >
                <span className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-sm font-medium leading-snug text-foreground">{experiment.name}</span>
                  <EvidenceChip tone={state.tone} className="shrink-0">
                    {state.label}
                  </EvidenceChip>
                </span>
                <span className="mt-1.5 block text-xs text-muted-foreground">
                  {variableLabel(experiment.variable)} · {observationWindowLabel(experiment.observation_window)}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5">
                  <EvidenceChip tone={kind.tone}>{kind.label}</EvidenceChip>
                  <span className="numeric text-[0.6875rem] text-muted-foreground">
                    {counts.control ?? 0} control · {counts.variant ?? 0} variant
                    {counts.observational_reference
                      ? ` · ${counts.observational_reference} ${counts.observational_reference === 1 ? "reference" : "references"}`
                      : ""}
                  </span>
                </span>
              </SelectableItem>
            </li>
          );
        })}
      </RecordList>
    </ListPanel>
  );
}
