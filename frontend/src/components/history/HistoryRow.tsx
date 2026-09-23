import { Link2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { cn, displayValue } from "@/lib/utils";
import { historyDate, runTitle } from "@/lib/historyFormat";
import type { HistoryRun } from "@/api/historyTypes";

function Score({ label, value, suffix }: { label: string; value: unknown; suffix: string }) {
  return (
    <div className="min-w-[5.5rem]">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="numeric text-sm font-bold text-foreground">
        {displayValue(value, "Unavailable")}
        {value === null || value === undefined || value === "" ? "" : suffix}
      </p>
    </div>
  );
}

export function HistoryRow({
  run,
  selected,
  isOpen,
  onToggleSelect,
  onOpen,
  onLink,
  onDelete,
}: {
  run: HistoryRun;
  selected: boolean;
  isOpen: boolean;
  onToggleSelect: (checked: boolean) => void;
  onOpen: () => void;
  onLink: () => void;
  onDelete: () => void;
}) {
  const title = runTitle(run);
  const isLinked = Boolean(run.linked_youtube_video_id);
  const angle = run.content_angle || run.intent || "General";

  return (
    <article
      data-history-run={run.id}
      data-testid="history-row"
      className={cn(
        "flex flex-col gap-3 border-b border-border p-4 transition-colors last:border-b-0 sm:flex-row sm:items-center",
        selected && "bg-primary/5",
        isOpen && "bg-muted/50",
      )}
    >
      <Checkbox
        checked={selected}
        onCheckedChange={(value) => onToggleSelect(value === true)}
        aria-label={`Select ${title}`}
        className="shrink-0"
      />

      <div className="min-w-0 flex-1 space-y-1.5">
        <button
          type="button"
          onClick={onOpen}
          title={title}
          className="block max-w-full truncate text-left text-sm font-semibold text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {title}
        </button>
        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
          <span>{historyDate(run.created_at)}</span>
          <span aria-hidden="true">·</span>
          <span>{angle}</span>
          {run.selected_package_id ? (
            <EvidenceChip tone="ok">Selected package</EvidenceChip>
          ) : (
            <EvidenceChip tone="neutral">Selection unknown</EvidenceChip>
          )}
          {isLinked ? <EvidenceChip tone="ok">YouTube linked</EvidenceChip> : null}
        </div>
      </div>

      <div className="flex gap-4 sm:gap-5" aria-label="Package scores">
        <Score label="Opportunity" value={run.opportunity_score} suffix="/100" />
        <Score label="Title quality" value={run.title_score} suffix="/10" />
      </div>

      <div className="flex shrink-0 flex-wrap gap-1.5">
        <Button size="sm" onClick={onOpen}>
          View package
        </Button>
        <Button size="sm" variant="outline" onClick={onLink}>
          <Link2 aria-hidden="true" />
          {isLinked ? "Change link" : "Link video"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onDelete}
          aria-label={`Delete ${title}`}
          className="text-tone-bad hover:bg-tone-bad-bg hover:text-tone-bad"
        >
          <Trash2 aria-hidden="true" />
          Delete
        </Button>
      </div>
    </article>
  );
}
