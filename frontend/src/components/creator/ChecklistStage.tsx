import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { EmptyState } from "@/components/common/States";
import { cn } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import { CHECKLIST_ITEMS, type ChecklistKey, type ChecklistState } from "@/lib/creatorConstants";
import type { PackageOption } from "@/api/types";

export function ChecklistStage({
  selected,
  checklist,
  onToggle,
  onExport,
}: {
  selected: PackageOption | null;
  checklist: ChecklistState;
  onToggle: (key: ChecklistKey, checked: boolean) => void;
  onExport: () => void;
}) {
  if (!selected) {
    return (
      <EmptyState
        title="No package selected"
        description="Run Analyze and select a package before completing manual upload checks."
      />
    );
  }

  const completed = CHECKLIST_ITEMS.filter((item) => checklist[item.key]).length;
  const total = CHECKLIST_ITEMS.length;
  const allDone = completed === total;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
          <CardTitle>Manual pre-publish checklist</CardTitle>
          <EvidenceChip tone={allDone ? "ok" : "warn"}>
            {completed} / {total} confirmed
          </EvidenceChip>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs font-bold text-foreground">Selected: {selected.label}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{selected.title}</p>
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              Changing the selected package resets these acknowledgments so the new choice is
              reviewed.
            </p>
          </div>

          <ul className="space-y-2">
            {CHECKLIST_ITEMS.map((item) => {
              const checked = Boolean(checklist[item.key]);
              return (
                <li key={item.key}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                      checked
                        ? "border-tone-ok-border bg-tone-ok-bg/40"
                        : "border-border hover:bg-muted/50",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => onToggle(item.key, value === true)}
                      className="mt-0.5"
                      aria-label={item.label}
                    />
                    <span className="space-y-1">
                      <span className="block text-xs font-semibold leading-relaxed text-foreground">
                        {item.label}
                      </span>
                      <span className="block text-[11px] leading-relaxed text-muted-foreground">
                        {item.source}. Checking this is your acknowledgment, not an automated
                        YouTube validation.
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>

          <div
            className={cn(
              "rounded-lg border p-3",
              allDone
                ? "border-tone-ok-border bg-tone-ok-bg"
                : "border-tone-warn-border bg-tone-warn-bg",
            )}
          >
            <p className="text-xs font-bold text-foreground">
              {allDone ? "Manual review completed" : "Manual review still required"}
            </p>
            <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
              {allDone
                ? "You can copy the package and publish manually in YouTube Studio. Performance is still not guaranteed."
                : "Confirm every item before using this package in YouTube Studio."}
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <CopyButton
          value={copyValue(selected, "upload-package")}
          label="Copy selected upload package"
          variant="default"
        />
        <Button variant="outline" onClick={onExport}>
          <Download aria-hidden="true" />
          Export full analysis and local decision
        </Button>
      </div>
    </div>
  );
}
