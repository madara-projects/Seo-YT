import { Activity, Compass } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { UnavailableNote } from "@/components/common/States";
import { formatApiError } from "@/api/client";
import { useRemPx } from "@/hooks/useRemPx";
import { useRetentionProbe } from "@/hooks/useLearning";
import { clockTime, retentionReasonLabel, trafficSourceLabel } from "@/lib/learningFormat";
import { windowLabel } from "@/lib/auditFormat";
import { formatCompact } from "@/lib/format";
import { asArray } from "@/lib/utils";
import type {
  LinkedTrafficEvidence,
  RetentionObservations,
  RetentionPoint,
  RetentionProbeResult,
  TrafficSourceRow,
} from "@/api/learningTypes";

const CHART_TEXT = "0.6875rem";
const HOOK_PERCENT = 15;

function Heading({ icon: Icon, children, aside }: { icon: React.ElementType; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
        {children}
      </p>
      {aside}
    </div>
  );
}

/** Where the evidence window's views came from, and how videos led by the same source compare. */
export function TrafficSourcesBlock({ evidence }: { evidence: LinkedTrafficEvidence }) {
  const traffic = evidence.traffic_sources ?? null;
  const cohort = evidence.traffic_source_cohort ?? null;
  const rows = asArray<TrafficSourceRow>(traffic?.sources).slice(0, 6);

  return (
    <div className="space-y-2" data-testid="traffic-sources">
      <Heading icon={Compass} aside={<EvidenceChip tone="info">YouTube data</EvidenceChip>}>
        Traffic sources
      </Heading>
      {!traffic || !rows.length ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          No traffic-source breakdown is stored yet. It is read with each completed 24-hour, 7-day or
          28-day window; YouTube may also refuse it or have none.
        </p>
      ) : (
        <>
          <ul className="space-y-1.5">
            {rows.map((row) => (
              <li key={row.source} className="space-y-0.5">
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="text-foreground">{trafficSourceLabel(row.source)}</span>
                  <span className="numeric text-muted-foreground">
                    {formatCompact(row.views)} views
                    {typeof row.share_percent === "number" ? ` · ${row.share_percent.toFixed(1)}%` : ""}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-muted" aria-hidden="true">
                  <div
                    className="h-full rounded-full bg-chart-1"
                    style={{ width: `${Math.max(2, Math.min(100, row.share_percent ?? 0))}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {windowLabel(traffic.window)}
            {traffic.dominant_source
              ? ` · mostly ${trafficSourceLabel(traffic.dominant_source)} (${traffic.dominant_share_percent?.toFixed(1)}% of views).`
              : "."}
          </p>
          {cohort ? (
            <p className="text-xs leading-relaxed text-muted-foreground" data-testid="traffic-cohort">
              {cohort.learning_allowed
                ? `${cohort.confidence_label ?? "Evidence"}: ${cohort.sample_size} other comparable videos were also led by ${trafficSourceLabel(cohort.traffic_source)} in this window — median ${formatCompact(cohort.median_views)} views${typeof cohort.median_retention_percentage === "number" ? `, ${cohort.median_retention_percentage.toFixed(1)}% average viewed` : ""}.`
                : `${cohort.sample_size} other comparable ${cohort.sample_size === 1 ? "video was" : "videos were"} led by ${trafficSourceLabel(cohort.traffic_source)}; ${cohort.more_needed} more needed before comparing with them.`}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

interface ChartPoint {
  x: number;
  y: number;
  relative: number | null;
  seconds: number | null;
}

function CurveTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  const point = active ? payload?.[0]?.payload : undefined;
  if (!point) return null;
  return (
    <div className="rounded-xl border border-border bg-popover px-3 py-2 shadow-elevated">
      <p className="numeric text-xs font-semibold text-popover-foreground">
        {point.x}% in{point.seconds !== null ? ` · ${clockTime(point.seconds)}` : ""}
      </p>
      <p className="numeric text-xs text-foreground">{point.y.toFixed(1)}% of the audience watching</p>
      {point.relative !== null ? (
        <p className="numeric text-[0.6875rem] text-muted-foreground">
          Relative to similar-length videos: {point.relative.toFixed(2)} (0.50 is typical)
        </p>
      ) : null}
    </div>
  );
}

/** The audience still watching at each point of the video, with the hook shaded and chapter starts marked. */
export function RetentionCurveChart({
  points,
  durationSeconds,
  observations,
}: {
  points: RetentionPoint[];
  durationSeconds: number | null | undefined;
  observations: RetentionObservations | null;
}) {
  const rem = useRemPx();
  const duration = typeof durationSeconds === "number" && durationSeconds > 0 ? durationSeconds : null;
  const data: ChartPoint[] = points.map((point) => ({
    x: Math.round(point.elapsed_ratio * 100),
    y: point.audience_watch_ratio * 100,
    relative: point.relative_retention_performance,
    seconds: duration ? point.elapsed_ratio * duration : null,
  }));
  const chapters = observations?.chapters ?? [];
  const tableRows = data.filter((point) => point.x % 10 === 0);

  return (
    <figure className="space-y-2" data-testid="retention-curve">
      <figcaption className="text-xs text-muted-foreground">
        Audience still watching, by how far into the video (the shaded start is the hook, the first{" "}
        {HOOK_PERCENT}%{chapters.length ? "; dashed lines are chapter starts" : ""}).
      </figcaption>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: rem(0.5), right: rem(0.5), bottom: 0, left: rem(-0.75) }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
            <ReferenceArea x1={0} x2={HOOK_PERCENT} fill="var(--chart-1)" fillOpacity={0.08} stroke="none" />
            {duration
              ? chapters
                  .filter((chapter) => chapter.start_seconds > 0)
                  .map((chapter) => (
                    <ReferenceLine
                      key={chapter.start_seconds}
                      x={Math.round((chapter.start_seconds / duration) * 100)}
                      stroke="var(--chart-axis)"
                      strokeDasharray="3 3"
                    />
                  ))
              : null}
            <XAxis
              dataKey="x"
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "var(--chart-axis)", fontSize: CHART_TEXT }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tickFormatter={(value: number) => `${Math.round(value)}%`}
              tick={{ fill: "var(--chart-axis)", fontSize: CHART_TEXT }}
              tickLine={false}
              axisLine={false}
              width={rem(2.75)}
            />
            <Tooltip content={<CurveTooltip />} cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }} />
            <Line type="monotone" dataKey="y" stroke="var(--chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Curve values</summary>
        <table className="numeric mt-2 w-full text-left">
          <thead>
            <tr>
              <th className="font-medium">Point</th>
              <th className="font-medium">Watching</th>
              <th className="font-medium">Relative</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((point) => (
              <tr key={point.x}>
                <td>
                  {point.x}%{point.seconds !== null ? ` (${clockTime(point.seconds)})` : ""}
                </td>
                <td>{point.y.toFixed(1)}%</td>
                <td>{point.relative !== null ? point.relative.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

function ProbeResult({ result }: { result: RetentionProbeResult }) {
  if (result.status !== "available") {
    return (
      <UnavailableNote>
        <span className="font-medium text-foreground">{retentionReasonLabel(result.reason)}.</span> {result.message}
        {result.requests ? " One YouTube Analytics request was made." : " No YouTube request was made."}
      </UnavailableNote>
    );
  }
  const observations = result.observations;
  return (
    <div className="space-y-3">
      <RetentionCurveChart
        points={asArray<RetentionPoint>(result.points)}
        durationSeconds={result.duration_seconds}
        observations={observations}
      />
      {observations?.observations?.length ? (
        <ul className="space-y-1" aria-label="Observations">
          {observations.observations.map((item) => (
            <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
              <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
        {observations?.note ?? "Observations of when viewers left, not proof of why."} Shown now only; nothing
        is stored.
      </p>
    </div>
  );
}

/**
 * The retention-curve probe: one YouTube Analytics request for this linked,
 * ownership-verified video. Whether a curve exists depends on the channel,
 * the video's age and views, and the connection's Analytics permission.
 */
export function RetentionProbe({ linkId, verified }: { linkId: number | null; verified: boolean }) {
  const probe = useRetentionProbe(linkId);
  const run = () =>
    probe.mutateAsync().catch((error: unknown) => {
      toast.error(formatApiError(error, "The retention curve could not be requested."));
    });

  return (
    <div className="space-y-2" data-testid="retention-probe">
      <Heading icon={Activity} aside={<EvidenceChip tone="info">YouTube Analytics</EvidenceChip>}>
        Retention curve
      </Heading>
      {!verified || !linkId ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          Available only for a video verified as your connected channel's own.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => void run()} disabled={probe.isPending}>
              {probe.isPending ? "Asking YouTube…" : probe.data ? "Check again" : "Check retention curve"}
            </Button>
            <span className="text-xs text-muted-foreground">Uses one YouTube Analytics request.</span>
          </div>
          {probe.data ? <ProbeResult result={probe.data} /> : null}
        </>
      )}
    </div>
  );
}

/** The outcome-learning sections of a linked video's report in History. */
export function LinkedVideoLearning({
  evidence,
  linkId,
  verified,
}: {
  evidence: LinkedTrafficEvidence;
  linkId: number | null;
  verified: boolean;
}) {
  return (
    <div className="space-y-4 border-t border-border pt-3">
      <TrafficSourcesBlock evidence={evidence} />
      <RetentionProbe linkId={linkId} verified={verified} />
    </div>
  );
}
