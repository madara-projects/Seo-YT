import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceChip, provenanceLabel, SourceLegend } from "@/components/common/EvidenceChip";
import { EmptyState } from "@/components/common/States";
import { PROVENANCE_FIELDS } from "@/lib/creatorConstants";
import { asObject } from "@/lib/utils";
import type { CreatorBrief } from "@/api/types";
import type { CreatorFormValues } from "@/schemas/creator";

/**
 * Shows, field by field, whether a brief value came from the creator or was
 * inferred by the engine. This is the product's central honesty guarantee, so
 * it is rendered as a table of claims rather than prose.
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
        title="No creator brief yet"
        description="Run Analyze to see which brief values you supplied and which the engine inferred."
      />
    );
  }

  const provenance = asObject(brief.field_provenance);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Creator brief provenance</CardTitle>
          <CardDescription>
            Inferred values are analysis suggestions. Review them before publishing; they never
            overwrite what you entered.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border">
            {PROVENANCE_FIELDS.map(([field, label]) => {
              const submittedValue = String(
                (submitted as Record<string, unknown> | null)?.[field] ?? "",
              ).trim();
              const value = String(
                (brief as Record<string, unknown>)[field] ?? submittedValue ?? "",
              ).trim();

              const rawSource = String(
                asObject(provenance[field]).source ??
                  (submittedValue ? "creator_supplied" : value ? "inferred" : "unknown"),
              );
              const { label: sourceLabel, tone } = provenanceLabel(rawSource);

              return (
                <li
                  key={field}
                  className="flex flex-col gap-1.5 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
                >
                  <div className="min-w-0 space-y-0.5">
                    <p className="text-xs font-semibold text-foreground">{label}</p>
                    <p className="break-words text-xs text-muted-foreground">
                      {value || "Not provided"}
                    </p>
                  </div>
                  <EvidenceChip tone={tone} className="shrink-0 self-start">
                    {sourceLabel}
                  </EvidenceChip>
                </li>
              );
            })}
          </ul>
        </CardContent>
      </Card>

      <SourceLegend />
    </div>
  );
}
