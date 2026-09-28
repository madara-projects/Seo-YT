import { Scale } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Meter } from "@/components/common/Meter";
import { Inset, Panel } from "@/components/common/Panel";
import { CardSkeleton, UnavailableNote } from "@/components/common/States";
import { useScoreCalibration } from "@/hooks/useScoreCalibration";
import { asArray, formatNumber } from "@/lib/utils";
import { windowLabel } from "@/lib/auditFormat";
import { ideaFormatLabel, ideaLanguageLabel } from "@/lib/ideaFormat";
import { EXCLUSION_LABEL, RECOMMENDATION_LABEL, calibrationStatus } from "@/lib/opportunityFormat";
import type { CalibrationGroup } from "@/api/opportunityTypes";

function median(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? formatNumber(Math.round(value)) : "n/a";
}

function Group({ group }: { group: CalibrationGroup }) {
  const higher = group.higher_scoring ?? {};
  const lower = group.lower_scoring ?? {};
  return (
    <li data-testid="calibration-group">
      <Inset className="space-y-1 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">
          {ideaFormatLabel(group.format)} · {ideaLanguageLabel(group.language)} · {formatNumber(group.sample_size)} video(s)
        </p>
        <p>
          Higher-scoring: median {median(higher.median_views)} views ({formatNumber(higher.sample_size ?? 0)}) ·
          Lower-scoring: median {median(lower.median_views)} views ({formatNumber(lower.sample_size ?? 0)})
        </p>
        <p>
          {typeof group.spearman_rho === "number"
            ? `Rank correlation ${group.spearman_rho >= 0 ? "+" : ""}${group.spearman_rho.toFixed(2)}`
            : "Too few videos for a rank correlation"}
        </p>
      </Inset>
    </li>
  );
}

/**
 * "Does the Opportunity Score track your results?": past scores against the
 * views of comparable published videos. An association at most, and it says
 * so, including when there is not yet enough evidence to say anything.
 */
export function ScoreCalibrationCard({ className }: { className?: string }) {
  const calibration = useScoreCalibration();
  const data = calibration.data;
  const status = calibrationStatus(data?.status);
  const known = status.label !== "Unavailable";
  const groups = asArray<CalibrationGroup>(data?.groups);
  const minimum = data?.minimum_group_samples ?? 5;
  const largest = Math.max(0, ...groups.map((group) => group.sample_size ?? 0));
  const windows = Object.entries(data?.windows ?? {});
  const excluded = Object.entries(data?.excluded ?? {}).filter(([, count]) => count > 0);

  return (
    <Panel
      className={className}
      icon={Scale}
      title="Does the Opportunity Score track your results?"
      description="Past scores compared with the views of your own comparable published videos. An association, not causation."
      aside={<EvidenceChip tone={status.tone}>{status.label}</EvidenceChip>}
    >
      {calibration.isPending ? (
        <CardSkeleton rows={3} />
      ) : calibration.isError || !known ? (
        <UnavailableNote>The calibration is unavailable right now.</UnavailableNote>
      ) : (
        <div className="space-y-4 text-[0.8125rem] leading-relaxed text-muted-foreground">
          <p className="text-foreground">{data?.summary}</p>

          {data?.status === "insufficient_evidence" ? (
            <div className="space-y-2">
              <p className="numeric text-xs font-medium text-foreground">
                {formatNumber(largest)} of {formatNumber(minimum)} comparable videos in the largest group
              </p>
              <Meter value={Math.min(largest, minimum)} max={minimum} label="Comparable videos collected toward a calibration" />
              {data.needed ? <p>{data.needed}</p> : null}
            </div>
          ) : data?.needed ? (
            <p>{data.needed}</p>
          ) : null}

          {data?.recommendation ? (
            <Inset data-testid="calibration-recommendation" className="space-y-1">
              <p className="font-semibold text-foreground">
                Recommendation: {RECOMMENDATION_LABEL[data.recommendation] ?? data.recommendation}
              </p>
              {data.recommendation_text ? <p className="text-xs">{data.recommendation_text}</p> : null}
            </Inset>
          ) : null}

          {groups.length ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-foreground">
                {data?.outcome_label ?? "Views at the same completed window"}, by format and language
              </p>
              <ul className="grid gap-2 lg:grid-cols-2">
                {groups.map((group) => (
                  <Group key={`${group.format}-${group.language}`} group={group} />
                ))}
              </ul>
            </div>
          ) : null}

          <div className="space-y-1 text-xs">
            {windows.length ? (
              <p>
                Comparable videos per completed window:{" "}
                {windows.map(([window, count]) => `${windowLabel(window)}: ${formatNumber(count)}`).join(" · ")}
              </p>
            ) : null}
            {excluded.length ? (
              <p>
                Left out:{" "}
                {excluded.map(([reason, count]) => `${formatNumber(count)} ${EXCLUSION_LABEL[reason] ?? reason}`).join(" · ")}
              </p>
            ) : null}
            <ul className="list-disc space-y-0.5 pl-4">
              {asArray<string>(data?.caveats).map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Panel>
  );
}
