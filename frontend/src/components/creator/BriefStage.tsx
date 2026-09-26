import { ScrollText } from "lucide-react";
import { EvidenceChip, provenanceLabel, SourceLegend } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { EmptyState } from "@/components/common/States";
import { PROVENANCE_FIELDS } from "@/lib/creatorConstants";
import { asObject, cn } from "@/lib/utils";
import type { CreatorBrief } from "@/api/types";
import type { CreatorFormValues } from "@/schemas/creator";

/**
 * Shows, field by field, whether a brief value came from the creator or was
 * inferred by the engine. This is the product's central honesty guarantee, so
 * it is rendered as a set of claims rather than prose.
 */
export function BriefStage({
  brief,
  submitted,
}: {
  brief: CreatorBrief | null;
  submitted: CreatorFormValues | null;
}) {
  if (!brief) {
    return (
      <EmptyState
        icon={ScrollText}
        title="No creator brief yet"
        description="Run Analyze to see which brief values you supplied and which the engine inferred."
      />
    );
  }

  const provenance = asObject(brief.field_provenance);

  const rows = PROVENANCE_FIELDS.map(([field, label]) => {
    const submittedValue = String(
      (submitted as Record<string, unknown> | null)?.[field] ?? "",
    ).trim();
    const value = String((brief as Record<string, unknown>)[field] ?? submittedValue).trim();
    const rawSource = String(
      asObject(provenance[field]).source ??
        (submittedValue ? "creator_supplied" : value ? "inferred" : "unknown"),
    );
    const source = provenanceLabel(rawSource);
    return { field, label, value, rawSource, sourceLabel: source.label, tone: source.tone };
  });

  const supplied = rows.filter((row) => row.rawSource === "creator_supplied").length;
  const inferred = rows.filter((row) => row.rawSource === "inferred").length;
  const other = rows.length - supplied - inferred;

  return (
    <div className="space-y-5">
      <Panel
        icon={ScrollText}
        title="Creator brief provenance"
        description="Inferred values are analysis suggestions. Review them before publishing; they never overwrite what you entered."
      >
        <div className="mb-5 space-y-2.5">
          <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
            <span className="h-full bg-tone-ok" style={{ width: `${(supplied / rows.length) * 100}%` }} />
            <span className="h-full bg-tone-warn" style={{ width: `${(inferred / rows.length) * 100}%` }} />
            <span className="h-full bg-muted-foreground/30" style={{ width: `${(other / rows.length) * 100}%` }} />
          </div>
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              <strong className="font-semibold text-tone-ok">{supplied}</strong> creator-entered
            </span>
            <span>
              <strong className="font-semibold text-tone-warn">{inferred}</strong> inferred
            </span>
            <span>
              <strong className="font-semibold text-foreground">{other}</strong> unknown or unavailable
            </span>
          </p>
        </div>

        <ul className="grid gap-2.5 md:grid-cols-2">
          {rows.map((row) => (
            <li
              key={row.field}
              className={cn(
                "flex flex-col gap-2 rounded-xl border p-3.5",
                row.tone === "ok" ? "border-tone-ok-border/70 bg-tone-ok-bg/40" : "border-border bg-elevated",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-[0.8125rem] font-medium text-foreground">{row.label}</p>
                <EvidenceChip tone={row.tone} className="shrink-0">
                  {row.sourceLabel}
                </EvidenceChip>
              </div>
              <p className="break-words text-[0.8125rem] leading-relaxed text-muted-foreground">
                {row.value || "Not provided"}
              </p>
            </li>
          ))}
        </ul>
      </Panel>

      <SourceLegend />
    </div>
  );
}
