import { ChevronLeft, ChevronRight, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { OptionSelect } from "@/components/common/OptionSelect";
import { SelectableItem } from "@/components/common/SelectableItem";
import { ListPanel, RecordList } from "@/components/research/ListPanel";
import { relativeTime } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { ideaFormatLabel, ideaLanguageLabel, ideaRegionLabel, ideaStatusLabel } from "@/lib/ideaFormat";
import { IDEA_STATUS_FILTERS } from "@/schemas/idea";
import { IDEAS_PAGE_SIZE } from "@/hooks/useIdeas";
import type { IdeaSummary } from "@/api/ideaTypes";

export function IdeaList({
  ideas,
  total,
  offset,
  status,
  onStatusChange,
  onOffsetChange,
  isPending,
  isFetching,
  error,
  selectedId,
  onSelect,
  onRefresh,
}: {
  ideas: IdeaSummary[];
  total: number;
  offset: number;
  status: string;
  onStatusChange: (status: string) => void;
  onOffsetChange: (offset: number) => void;
  isPending: boolean;
  isFetching: boolean;
  error: unknown;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}) {
  const first = ideas.length ? offset + 1 : 0;
  const last = offset + ideas.length;

  return (
    <ListPanel
      icon={Lightbulb}
      title="Backlog"
      description="Newest first."
      refreshLabel="Refresh ideas"
      onRefresh={onRefresh}
      isFetching={isFetching}
      list={{
        isPending,
        error,
        errorFallback: "The idea backlog is unavailable.",
        isEmpty: !ideas.length,
        empty: status
          ? "No ideas have this status."
          : "No ideas yet. Add one with New idea and it will appear here.",
      }}
      toolbar={
        <OptionSelect
          ariaLabel="Filter ideas by status"
          value={status}
          onValueChange={onStatusChange}
          options={IDEA_STATUS_FILTERS}
        />
      }
      footer={
        total > IDEAS_PAGE_SIZE ? (
          <div className="mt-2 flex items-center justify-between gap-2 border-t border-border px-2 pt-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOffsetChange(Math.max(0, offset - IDEAS_PAGE_SIZE))}
              disabled={offset <= 0 || isFetching}
            >
              <ChevronLeft aria-hidden="true" />
              Previous
            </Button>
            <p className="numeric text-xs text-muted-foreground" aria-live="polite">
              {first}–{last} of {total}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOffsetChange(offset + IDEAS_PAGE_SIZE)}
              disabled={offset + IDEAS_PAGE_SIZE >= total || isFetching}
            >
              Next
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        ) : null
      }
    >
      <RecordList label="Saved ideas">
        {ideas.map((idea) => {
          const statusLabel = ideaStatusLabel(idea.status);
          return (
            <li key={idea.id}>
              <SelectableItem
                selected={idea.id === selectedId}
                onSelect={() => onSelect(idea.id)}
                data-testid="idea-item"
              >
                <span className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
                    {idea.topic || "Untitled idea"}
                  </span>
                  <EvidenceChip tone={statusLabel.tone} className="shrink-0">
                    {statusLabel.label}
                  </EvidenceChip>
                </span>
                <span className="mt-1.5 block text-xs text-muted-foreground">
                  {ideaFormatLabel(idea.format)} · {ideaLanguageLabel(idea.language)} · {ideaRegionLabel(idea.region)}
                </span>
                <span
                  className="mt-1 block text-[0.6875rem] text-muted-foreground"
                  title={idea.last_researched_at ? historyDate(idea.last_researched_at) : undefined}
                >
                  {idea.last_researched_at
                    ? `Researched ${relativeTime(idea.last_researched_at)}`
                    : "Not researched yet"}
                  {idea.analysis_run_id ? ` · Package run #${idea.analysis_run_id}` : ""}
                </span>
              </SelectableItem>
            </li>
          );
        })}
      </RecordList>
    </ListPanel>
  );
}
