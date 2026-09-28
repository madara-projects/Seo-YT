import { useState } from "react";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, UnavailableNote } from "@/components/common/States";
import { useTrafficCohorts } from "@/hooks/useLearning";
import { trafficSourceLabel } from "@/lib/learningFormat";
import { formatCompact } from "@/lib/format";
import { humanize } from "@/lib/labels";
import { asArray } from "@/lib/utils";
import type { TrafficSourceCohort } from "@/api/learningTypes";

/** "Shorts · English": the format and language a group's videos share. */
function cohortLabel(group: TrafficSourceCohort): string {
  const format = group.format === "youtube_shorts" ? "Shorts" : humanize(group.format ?? "");
  return [format, humanize(group.language ?? "")].filter(Boolean).join(" · ");
}

const WINDOWS = [
  ["24h", "24 hours"],
  ["7d", "7 days"],
  ["28d", "28 days"],
] as const;

/**
 * Comparable linked videos grouped by the traffic source that brought most of
 * their views in one window. A group is compared only once it holds the
 * evidence policy's minimum of videos; until then it says how many more.
 */
export function TrafficSourceLearning({ className }: { className?: string }) {
  const [evidenceWindow, setEvidenceWindow] = useState<string>("7d");
  const cohorts = useTrafficCohorts(evidenceWindow);
  const groups = asArray<TrafficSourceCohort>(cohorts.data?.traffic_source_groups);
  const withoutBreakdown = cohorts.data?.without_traffic_sources ?? 0;

  return (
    <Panel
      className={className}
      icon={Compass}
      headingLevel={3}
      title="Learning by traffic source"
      description="Linked videos of the same format and language, grouped by where most of their views came from."
      aside={<EvidenceChip tone="info">YouTube data</EvidenceChip>}
      data-testid="traffic-source-learning"
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Evidence window">
          {WINDOWS.map(([value, text]) => (
            <Button
              key={value}
              size="xs"
              variant={evidenceWindow === value ? "soft" : "ghost"}
              aria-pressed={evidenceWindow === value}
              onClick={() => setEvidenceWindow(value)}
            >
              {text}
            </Button>
          ))}
        </div>
        {cohorts.isPending ? (
          <CardSkeleton rows={2} />
        ) : cohorts.isError ? (
          <UnavailableNote>Traffic-source learning could not be loaded.</UnavailableNote>
        ) : !groups.length ? (
          <UnavailableNote>
            No comparable video has a traffic-source breakdown for this window yet. It is read with each
            completed window of a linked, verified video.
          </UnavailableNote>
        ) : (
          <ul className="space-y-2">
            {groups.map((group) => (
              <li
                key={`${group.format}|${group.language}|${group.traffic_source}`}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border border-border bg-elevated p-2.5"
              >
                <span className="text-[0.8125rem] font-medium text-foreground">
                  {trafficSourceLabel(group.traffic_source)}
                  {group.format || group.language ? (
                    <span className="ml-1.5 text-xs font-normal text-muted-foreground">{cohortLabel(group)}</span>
                  ) : null}
                </span>
                <span className="numeric text-xs text-muted-foreground">
                  {group.learning_allowed
                    ? `${group.sample_size} videos · median ${formatCompact(group.median_views)} views${typeof group.median_retention_percentage === "number" ? ` · ${group.median_retention_percentage.toFixed(1)}% viewed` : ""}`
                    : `${group.sample_size} of ${group.minimum_samples} videos · ${group.more_needed} more needed`}
                </span>
              </li>
            ))}
          </ul>
        )}
        {withoutBreakdown ? (
          <p className="text-xs text-muted-foreground">
            {withoutBreakdown} comparable {withoutBreakdown === 1 ? "video has" : "videos have"} no breakdown for this
            window.
          </p>
        ) : null}
        <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
          An association between where views came from and how videos did, not a cause.
        </p>
      </div>
    </Panel>
  );
}
