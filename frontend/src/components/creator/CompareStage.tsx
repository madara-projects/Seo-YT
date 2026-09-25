import { Check, Layers, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { EmptyState } from "@/components/common/States";
import { cn, displayValue, formatNumber } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import { ThumbnailMock } from "./ThumbnailMock";
import type { PackageOption, SelectionStatus } from "@/api/types";

function Fact({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="min-w-0 space-y-0.5">
      <p className="text-[0.6875rem] text-muted-foreground">{label}</p>
      <p className="break-words text-[0.8125rem] font-semibold text-foreground">{value}</p>
      <p className="text-[0.65625rem] text-muted-foreground">{note}</p>
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
        icon={Layers}
        title="Nothing to compare yet"
        description="Run Analyze to create comparable package options."
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-2xl text-[0.8125rem] leading-relaxed text-muted-foreground">
          Scores and best-for labels are local heuristics or generated suggestions. They are not
          measured CTR, reach, or performance predictions.
        </p>
        <EvidenceChip
          tone={selectionStatus === "error" ? "bad" : selectionStatus === "saved" ? "ok" : "warn"}
        >
          {selectionStatus === "saved" ? "Selection saved" : "Choose to save"}
        </EvidenceChip>
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {options.map((option) => {
          const selected = option.id === selectedId;
          return (
            <article
              key={option.id}
              data-testid="package-option-card"
              data-package-id={option.id}
              className={cn(
                "group relative flex flex-col overflow-hidden rounded-2xl bg-card shadow-card transition-shadow",
                selected
                  ? "border-gradient shadow-elevated"
                  : "border border-border hover:shadow-elevated",
              )}
            >
              <div className="relative p-3 pb-0">
                <ThumbnailMock text={option.thumbnailText} />
                <div className="absolute left-5 top-5 flex flex-wrap gap-1.5">
                  <Badge variant="solid" className="bg-black/70 text-white backdrop-blur">
                    {option.label}
                  </Badge>
                  {option.primary ? (
                    <Badge variant="solid" className="bg-white/90 text-black">
                      Primary
                    </Badge>
                  ) : null}
                </div>
                {selected ? (
                  <span
                    className="absolute right-5 top-5 grid size-7 place-items-center rounded-full bg-white text-black shadow-card"
                    aria-hidden="true"
                  >
                    <Check className="size-4" strokeWidth={3} />
                  </span>
                ) : null}
              </div>

              <div className="flex flex-1 flex-col gap-4 p-4">
                <div className="space-y-2">
                  <EvidenceChip tone={option.source === "AI suggestion" ? "info" : "warn"}>
                    {option.source}
                  </EvidenceChip>
                  <h3 className="font-display text-base font-semibold leading-snug text-foreground">
                    {option.title}
                  </h3>
                </div>

                <div className="grid grid-cols-2 gap-3 rounded-xl border border-border/80 bg-elevated p-3">
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
                  <p className="text-xs font-medium text-foreground">Why suggested</p>
                  <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                    {option.whySuggested}
                  </p>
                </div>

                <div className="space-y-1">
                  <p className="text-xs font-medium text-foreground">Thumbnail direction</p>
                  <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                    {displayValue(option.thumbnailVisual)}
                    {option.thumbnailText ? ` · Text: ${option.thumbnailText}` : ""}
                  </p>
                </div>

                <p className="mt-auto flex gap-2 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3 py-2.5 text-[0.6875rem] leading-relaxed text-foreground">
                  <ShieldAlert className="mt-px size-3.5 shrink-0 text-tone-warn" aria-hidden="true" />
                  <span>
                    Misleading-risk check: {option.misleadingRisk}. This is a generated or local
                    assessment and must be manually reviewed.
                  </span>
                </p>
              </div>

              <div className="flex gap-2 border-t border-border p-4">
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
