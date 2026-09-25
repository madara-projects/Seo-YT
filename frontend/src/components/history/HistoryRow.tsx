import { Eye, Link2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Meter } from "@/components/common/Meter";
import { cn, displayValue } from "@/lib/utils";
import { initialOf, toFiniteNumber } from "@/lib/format";
import { historyDate, runTitle } from "@/lib/historyFormat";
import type { HistoryRun } from "@/api/historyTypes";

function Score({
  label,
  value,
  suffix,
  max,
}: {
  label: string;
  value: unknown;
  suffix: string;
  max: number;
}) {
  const number = toFiniteNumber(value);
  return (
    <div className="w-24 space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[0.6875rem] text-muted-foreground">{label}</p>
      </div>
      <p className="numeric text-sm font-semibold text-foreground">
        {displayValue(value, "Unavailable")}
        {value === null || value === undefined || value === "" ? "" : suffix}
      </p>
      <Meter value={number} max={max} label={`${label} score`} size="sm" />
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
        "group relative flex flex-col gap-4 border-b border-border px-4 py-4 transition-colors last:border-b-0 sm:px-5 lg:flex-row lg:items-center lg:gap-6",
        selected ? "bg-brand-soft/40" : "hover:bg-accent/40",
        isOpen && "bg-accent/60",
      )}
    >
      {isOpen ? (
        <span className="absolute inset-y-3 left-0 w-1 rounded-r-full bg-brand-gradient" aria-hidden="true" />
      ) : null}

      <div className="flex min-w-0 flex-1 items-start gap-3.5">
        <Checkbox
          checked={selected}
          onCheckedChange={(value) => onToggleSelect(value === true)}
          aria-label={`Select ${title}`}
          className="mt-3"
        />
        <span
          className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-soft font-display text-base font-semibold text-brand ring-1 ring-inset ring-brand-border"
          aria-hidden="true"
        >
          {initialOf(title)}
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <button
            type="button"
            onClick={onOpen}
            title={title}
            className="block max-w-full truncate rounded-md text-left text-[0.9375rem] font-semibold text-foreground transition-colors hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {title}
          </button>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
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
      </div>

      <div
        role="group"
        aria-label="Package scores"
        className="flex gap-5 pl-[4.35rem] lg:pl-0"
      >
        <Score label="Opportunity" value={run.opportunity_score} suffix="/100" max={100} />
        <Score label="Title quality" value={run.title_score} suffix="/10" max={10} />
      </div>

      <div className="flex shrink-0 flex-wrap gap-1.5 pl-[4.35rem] lg:pl-0">
        <Button size="sm" onClick={onOpen}>
          <Eye aria-hidden="true" />
          View package
        </Button>
        <Button size="sm" variant="outline" onClick={onLink}>
          <Link2 aria-hidden="true" />
          {isLinked ? "Change link" : "Link video"}
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete} aria-label={`Delete ${title}`}>
          <Trash2 aria-hidden="true" />
          Delete
        </Button>
      </div>
    </article>
  );
}
