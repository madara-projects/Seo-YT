import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, SourceLegend } from "@/components/common/EvidenceChip";
import { EmptyState } from "@/components/common/States";
import { asArray, asObject, displayValue, formatNumber } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import type { AnalyzeResponse, PackageOption, SelectionStatus } from "@/api/types";

export function DecisionStage({
  data,
  selected,
  selectionStatus,
  onExport,
}: {
  data: AnalyzeResponse | null;
  selected: PackageOption | null;
  selectionStatus: SelectionStatus;
  onExport: () => void;
}) {
  if (!data || !selected) {
    return (
      <EmptyState
        title="No decision to review yet"
        description="Run Analyze and select a package before reviewing the final decision."
      />
    );
  }

  const publicCount = asArray(data.youtube_results).length;
  const opportunity = asObject(asObject(data.opportunity_gap_analysis).opportunity_score);
  const publicSentence = publicCount
    ? `${formatNumber(publicCount)} public YouTube result${publicCount === 1 ? " was" : "s were"} returned as context.`
    : "No public YouTube result was returned.";

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-primary/40 bg-primary/5 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <EvidenceChip tone={selectionStatus === "saved" ? "ok" : "warn"}>
            {selectionStatus === "saved" ? "Recorded in History" : "Selected for preview"}
          </EvidenceChip>
          <EvidenceChip tone="warn">Not published</EvidenceChip>
        </div>
        <h2 className="mt-3 text-lg font-bold leading-snug text-foreground">{selected.title}</h2>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {selected.label}. The recorded choice supports later attribution. It never changes or
          publishes a YouTube video.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Why it was suggested</CardTitle>
            <EvidenceChip tone={selected.source === "AI suggestion" ? "info" : "warn"}>
              {selected.source}
            </EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p>{selected.whySuggested}</p>
            <p>
              Approach: {selected.approach} · Intended use: {selected.bestFor}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Public context</CardTitle>
            <EvidenceChip tone={publicCount ? "info" : "warn"}>
              {publicCount ? "Public observation" : "Unavailable"}
            </EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p>{publicSentence}</p>
            <p>Public counts and patterns do not prove why another video performed.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Pre-publication scoring</CardTitle>
            <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p>
              Opportunity: {displayValue(opportunity.score)} / 100. Title quality:{" "}
              {selected.titleQualityScore === null
                ? "Unavailable"
                : `${formatNumber(selected.titleQualityScore)} / 10`}
              .
            </p>
            <p>
              These scores help compare packaging. They do not predict actual CTR, views, reach, or
              growth.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Unavailable before publishing</CardTitle>
            <EvidenceChip tone="neutral">Unavailable</EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p>
              Actual impressions, CTR, retention, views, and causal performance evidence are
              unavailable for this package.
            </p>
            <p>
              Link the published video in History and collect mature comparable snapshots before
              learning from results.
            </p>
          </CardContent>
        </Card>
      </div>

      <SourceLegend />

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
