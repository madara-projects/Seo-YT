import { CheckCircle2, ClipboardCheck, Download, ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { EmptyState } from "@/components/common/States";
import { cn } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import { CHECKLIST_ITEMS, type ChecklistKey, type ChecklistState } from "@/lib/creatorConstants";
import type { PackageOption } from "@/api/types";

/** A progress ring; the count beside it is the accessible value. */
function ProgressRing({ value, total }: { value: number; total: number }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const ratio = total ? value / total : 0;
  return (
    <svg viewBox="0 0 64 64" className="size-16 shrink-0 -rotate-90" aria-hidden="true">
      <defs>
        <linearGradient id="checklist-ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--grad-1)" />
          <stop offset="1" stopColor="var(--grad-2)" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--muted)" strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={radius}
        fill="none"
        stroke={value === total ? "var(--tone-ok)" : "url(#checklist-ring)"}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - ratio)}
        className="transition-[stroke-dashoffset] duration-500"
      />
    </svg>
  );
}

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
        icon={ClipboardCheck}
        title="No package selected"
        description="Run Analyze and select a package before completing manual upload checks."
      />
    );
  }

  const completed = CHECKLIST_ITEMS.filter((item) => checklist[item.key]).length;
  const total = CHECKLIST_ITEMS.length;
  const allDone = completed === total;

  return (
    <div className="space-y-5">
      <Panel
        icon={ListChecks}
        title="Manual pre-publish checklist"
        aside={
          <EvidenceChip tone={allDone ? "ok" : "warn"}>
            {completed} / {total} confirmed
          </EvidenceChip>
        }
      >
        <div className="space-y-5">
          <div className="flex items-center gap-4 rounded-2xl border border-border bg-elevated p-4">
            <ProgressRing value={completed} total={total} />
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Selected: {selected.label}</p>
              <p className="mt-0.5 font-display text-base font-semibold leading-snug text-foreground">
                {selected.title}
              </p>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Changing the selected package resets these acknowledgments so the new choice is
                reviewed.
              </p>
            </div>
          </div>

          <ul className="grid gap-2.5 md:grid-cols-2">
            {CHECKLIST_ITEMS.map((item) => {
              const checked = Boolean(checklist[item.key]);
              return (
                <li key={item.key}>
                  <label
                    className={cn(
                      "flex h-full cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-colors",
                      checked
                        ? "border-tone-ok-border bg-tone-ok-bg/50"
                        : "border-border bg-card hover:border-foreground/20 hover:bg-accent/50",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => onToggle(item.key, value === true)}
                      className="mt-0.5"
                      aria-label={item.label}
                    />
                    <span className="space-y-1">
                      <span className="block text-[13px] font-medium leading-relaxed text-foreground">
                        {item.label}
                      </span>
                      <span className="block text-xs leading-relaxed text-muted-foreground">
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
              "flex items-start gap-3 rounded-xl border p-4",
              allDone
                ? "border-tone-ok-border bg-tone-ok-bg"
                : "border-tone-warn-border bg-tone-warn-bg",
            )}
          >
            <CheckCircle2
              className={cn("mt-0.5 size-4 shrink-0", allDone ? "text-tone-ok" : "text-tone-warn")}
              aria-hidden="true"
            />
            <div>
              <p className="text-[13px] font-semibold text-foreground">
                {allDone ? "Manual review completed" : "Manual review still required"}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                {allDone
                  ? "You can copy the package and publish manually in YouTube Studio. Performance is still not guaranteed."
                  : "Confirm every item before using this package in YouTube Studio."}
              </p>
            </div>
          </div>
        </div>
      </Panel>

      <div className="flex flex-wrap gap-2">
        <CopyButton
          value={copyValue(selected, "upload-package")}
          label="Copy selected upload package"
          variant={allDone ? "gradient" : "default"}
          size="default"
        />
        <Button variant="outline" onClick={onExport}>
          <Download aria-hidden="true" />
          Export full analysis and local decision
        </Button>
      </div>
    </div>
  );
}
