import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { EmptyState } from "@/components/common/States";
import { cn, displayValue, formatNumber } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import type { PackageOption, SelectionStatus } from "@/api/types";

function Fact({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xs font-bold text-foreground">{value}</p>
      <p className="text-[10px] text-muted-foreground">{note}</p>
    </div>
  );
}

export function CompareStage({
  options,
  selectedId,
  selectionStatus,
  onSelect,
}: {
  options: PackageOption[];
  selectedId: string | null;
  selectionStatus: SelectionStatus;
  onSelect: (packageId: string) => void;
}) {
  if (!options.length) {
    return (
      <EmptyState
        title="Nothing to compare yet"
        description="Run Analyze to create comparable package options."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
          Scores and best-for labels are local heuristics or generated suggestions. They are not
          measured CTR, reach, or performance predictions.
        </p>
        <EvidenceChip
          tone={selectionStatus === "error" ? "bad" : selectionStatus === "saved" ? "ok" : "warn"}
        >
          {selectionStatus === "saved" ? "Selection saved" : "Choose to save"}
        </EvidenceChip>
      </div>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {options.map((option) => {
          const selected = option.id === selectedId;
          return (
            <article
              key={option.id}
              data-testid="package-option-card"
              data-package-id={option.id}
              className={cn(
                "flex flex-col rounded-xl border bg-card transition-colors",
                selected ? "border-primary ring-1 ring-primary/30" : "border-border",
              )}
            >
              <div className="flex items-start justify-between gap-2 p-4 pb-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-bold text-foreground">{option.label}</span>
                  {option.primary ? <EvidenceChip tone="info">Primary</EvidenceChip> : null}
                </div>
                <EvidenceChip tone={option.source === "AI suggestion" ? "info" : "warn"}>
                  {option.source}
                </EvidenceChip>
              </div>

              <div className="flex-1 space-y-3 px-4">
                <h3 className="text-sm font-bold leading-snug text-foreground">{option.title}</h3>

                <div className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-muted/30 p-3">
                  <Fact
                    label="Title quality"
                    value={
                      option.titleQualityScore === null
                        ? "Unavailable"
                        : `${formatNumber(option.titleQualityScore)} / 10`
                    }
                    note="Local heuristic"
                  />
                  <Fact label="Approach" value={displayValue(option.approach)} note="Generated" />
                  <Fact
                    label="Package intent"
                    value={displayValue(option.packageIntent)}
                    note="Generated"
                  />
                  <Fact label="Best for" value={displayValue(option.bestFor)} note="Generated" />
                </div>

                <div className="space-y-1">
                  <p className="text-[11px] font-semibold text-foreground">Why suggested</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {option.whySuggested}
                  </p>
                </div>

                <div className="space-y-1">
                  <p className="text-[11px] font-semibold text-foreground">Thumbnail direction</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {displayValue(option.thumbnailVisual)}
                    {option.thumbnailText ? ` · Text: ${option.thumbnailText}` : ""}
                  </p>
                </div>

                <p className="rounded-md border border-tone-warn-border bg-tone-warn-bg px-2.5 py-2 text-[10px] leading-relaxed text-foreground">
                  Misleading-risk check: {option.misleadingRisk}. This is a generated or local
                  assessment and must be manually reviewed.
                </p>
              </div>

              <div className="flex gap-2 p-4 pt-3">
                <CopyButton
                  value={copyValue(option, "title")}
                  label="Copy title"
                  className="flex-1"
                />
                <Button
                  size="sm"
                  variant={selected ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => onSelect(option.id)}
                  data-testid={`select-${option.id}`}
                  aria-pressed={selected}
                >
                  {selected ? "Selected" : "Select"}
                </Button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
