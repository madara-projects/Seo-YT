import { Ban, Download, Globe, Gauge, Lightbulb, Stamp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, SourceLegend } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
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
        icon={Stamp}
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
    <div className="space-y-5">
      <section className="relative overflow-hidden rounded-3xl border-gradient p-6 shadow-elevated sm:p-8">
        <div
          className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-brand-gradient opacity-15 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceChip tone={selectionStatus === "saved" ? "ok" : "warn"}>
              {selectionStatus === "saved" ? "Recorded in History" : "Selected for preview"}
            </EvidenceChip>
            <EvidenceChip tone="warn">Not published</EvidenceChip>
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-brand">
            Your decision · {selected.label}
          </p>
          <h2 className="max-w-3xl font-display text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">
            {selected.title}
          </h2>
          <p className="max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
            The recorded choice supports later attribution. It never changes or publishes a YouTube
            video.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <CopyButton
              value={copyValue(selected, "upload-package")}
              label="Copy selected upload package"
              variant="gradient"
              size="default"
            />
            <Button variant="outline" onClick={onExport}>
              <Download aria-hidden="true" />
              Export full analysis and local decision
            </Button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel
          icon={Lightbulb}
          title="Why it was suggested"
          aside={
            <EvidenceChip tone={selected.source === "AI suggestion" ? "info" : "warn"}>
              {selected.source}
            </EvidenceChip>
          }
        >
          <div className="space-y-1.5 text-[13px] leading-relaxed text-muted-foreground">
            <p>{selected.whySuggested}</p>
            <p>
              Approach: {selected.approach} · Intended use: {selected.bestFor}
            </p>
          </div>
        </Panel>

        <Panel
          icon={Globe}
          iconTone={publicCount ? "info" : "neutral"}
          title="Public context"
          aside={
            <EvidenceChip tone={publicCount ? "info" : "warn"}>
              {publicCount ? "Public observation" : "Unavailable"}
            </EvidenceChip>
          }
        >
          <div className="space-y-1.5 text-[13px] leading-relaxed text-muted-foreground">
            <p>{publicSentence}</p>
            <p>Public counts and patterns do not prove why another video performed.</p>
          </div>
        </Panel>

        <Panel
          icon={Gauge}
          title="Pre-publication scoring"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          <div className="space-y-1.5 text-[13px] leading-relaxed text-muted-foreground">
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
          </div>
        </Panel>

        <Panel
          icon={Ban}
          iconTone="neutral"
          title="Unavailable before publishing"
          aside={<EvidenceChip tone="neutral">Unavailable</EvidenceChip>}
        >
          <div className="space-y-1.5 text-[13px] leading-relaxed text-muted-foreground">
            <p>
              Actual impressions, CTR, retention, views, and causal performance evidence are
              unavailable for this package.
            </p>
            <p>
              Link the published video in History and collect mature comparable snapshots before
              learning from results.
            </p>
          </div>
        </Panel>
      </div>

      <SourceLegend />
    </div>
  );
}
