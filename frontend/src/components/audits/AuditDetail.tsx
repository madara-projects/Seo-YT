import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  ClipboardCheck,
  History,
  ListChecks,
  Loader2,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  Telescope,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { SectionTitle } from "@/components/common/SectionTitle";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { StepFlow, type Step } from "@/components/research/StepFlow";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useRefreshAudit } from "@/hooks/useAudits";
import { formatDuration, useElapsedSeconds } from "@/hooks/useElapsed";
import { formatCompact } from "@/lib/format";
import { historyDate, shortDate } from "@/lib/historyFormat";
import { humanize } from "@/lib/labels";
import { asArray } from "@/lib/utils";
import { classificationLabel } from "@/lib/demandFormat";
import {
  auditStateLabel,
  candidateTitle,
  comparisonText,
  evidenceStateLabel,
  fieldName,
  fieldStateLabel,
  findingSeverity,
  metadataVerdict,
  windowLabel,
} from "@/lib/auditFormat";
import type {
  Audit,
  AuditCandidate,
  AuditComparison,
  AuditDetailResponse,
  AuditFinding,
  AuditVersion,
  PerformanceSnapshot,
} from "@/api/auditTypes";

const LONG_TEXT = 180;

function percent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "Unavailable";
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Inset className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-display text-xl font-semibold leading-none tracking-tight text-foreground">{value}</dd>
    </Inset>
  );
}

/** One side of a comparison. Long descriptions fold, with a way to read all of it. */
function ComparedValue({ label, value, empty }: { label: string; value: string | null; empty: string }) {
  const [open, setOpen] = useState(false);
  const long = Boolean(value && value.length > LONG_TEXT);
  return (
    <div className="min-w-0 space-y-1">
      <p className="text-[0.6875rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p
        className={
          value
            ? `whitespace-pre-line break-words text-[0.8125rem] leading-relaxed text-foreground${long && !open ? " line-clamp-4" : ""}`
            : "text-[0.8125rem] text-muted-foreground"
        }
      >
        {value ?? empty}
      </p>
      {long ? (
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="text-xs font-medium text-brand underline-offset-4 hover:underline"
          aria-expanded={open}
        >
          {open ? "Show less" : "Show all"}
        </button>
      ) : null}
    </div>
  );
}

function ComparisonCard({ item, withSelection }: { item: AuditComparison; withSelection: boolean }) {
  const state = fieldStateLabel(item.generated_to_published);
  return (
    <Inset className="space-y-3 p-4" data-testid="audit-field">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{fieldName(item.field)}</p>
        <EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>
      </div>
      <div className={withSelection ? "grid gap-3 md:grid-cols-3" : "grid gap-3 sm:grid-cols-2"}>
        <ComparedValue label="Your package" value={comparisonText(item.generated)} empty="Empty" />
        {withSelection ? (
          <ComparedValue label="Selected package" value={comparisonText(item.selected)} empty="Empty" />
        ) : null}
        <ComparedValue
          label="On YouTube"
          value={comparisonText(item.published)}
          empty={item.generated_to_published === "unavailable" ? "Not captured" : "Empty"}
        />
      </div>
    </Inset>
  );
}

function auditSteps(audit: Audit): Step[] {
  const maturity = audit.observed_performance?.maturity;
  const selected = audit.intent?.selection_attribution === "creator_selected";
  const published = audit.published_reality?.available;
  const runId = audit.video?.analysis_run_id;
  return [
    { label: "Generated", value: runId ? `Run #${runId}` : "Saved package", state: "done" },
    { label: "Selected", value: selected ? "Recorded" : "Not recorded", state: selected ? "done" : "pending" },
    {
      label: "Published",
      value: published ? `Captured ${shortDate(audit.published_reality?.captured_at)}` : "Not captured",
      state: published ? "done" : "pending",
    },
    {
      label: "Observed",
      value:
        maturity === "mature_observation"
          ? "Completed window"
          : maturity === "collecting_evidence"
            ? "Current counts"
            : "No data yet",
      state: maturity === "mature_observation" || maturity === "collecting_evidence" ? "done" : "pending",
    },
  ];
}

function AuditBody({ audit, videoId, versions }: { audit: Audit; videoId?: string; versions: AuditVersion[] }) {
  const comparisons = asArray<AuditComparison>(audit.comparisons);
  const withSelection = comparisons.some((item) => comparisonText(item.selected) !== null);
  const verdict = metadataVerdict(comparisons);
  const performance = audit.observed_performance ?? {};
  const latest: PerformanceSnapshot | null = performance.latest_observation ?? null;
  const windows = asArray<PerformanceSnapshot>(performance.completed_windows);
  const mature = performance.maturity === "mature_observation";
  const findings = asArray<AuditFinding>(audit.findings);
  const before = audit.before_publication ?? {};
  const demand = before.demand_research ?? null;
  const limitations = asArray<string>(audit.limitations);

  return (
    <>
      <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
        <VideoThumb videoId={videoId} className="w-full" />
        <div className="space-y-2">
          <dl className="grid grid-cols-2 gap-2 xl:grid-cols-4">
            <Stat label="Views" value={formatCompact(latest?.views)} />
            <Stat label="Likes" value={formatCompact(latest?.likes)} />
            <Stat label="Comments" value={formatCompact(latest?.comments)} />
            <Stat label="Avg viewed" value={percent(latest?.avg_view_percentage)} />
          </dl>
          <p className="text-xs text-muted-foreground">
            {latest
              ? `${windowLabel(latest.snapshot_window)} · captured ${historyDate(latest.captured_at)}.`
              : "No performance snapshot was available for this audit."}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <StepFlow label="What this audit compared" steps={auditSteps(audit)} />
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">{auditStateLabel(audit.summary?.state).label}:</span>{" "}
          {auditStateLabel(audit.summary?.state).meaning}
        </p>
      </div>

      <section className="space-y-3">
        <SectionTitle icon={ListChecks} aside={<EvidenceChip tone={verdict.tone}>{verdict.label}</EvidenceChip>}>
          Metadata check
        </SectionTitle>
        <p className="text-sm leading-relaxed text-foreground">
          {verdict.text}{" "}
          {withSelection
            ? "The package you selected is shown beside it."
            : "No package selection was recorded, so the comparison uses the generated package."}
        </p>
        <div className="space-y-3">
          {comparisons.map((item) => (
            <ComparisonCard key={item.field} item={item} withSelection={withSelection} />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={BarChart3} aside={<EvidenceChip tone="info">Your channel's analytics</EvidenceChip>}>
          Performance by window
        </SectionTitle>
        <dl className="grid gap-2 sm:grid-cols-3">
          {(["24h", "7d", "28d"] as const).map((window) => {
            const snapshot = windows.find((item) => item.snapshot_window === window);
            return (
              <Inset key={window} className="space-y-1">
                <dt className="text-xs text-muted-foreground">{windowLabel(window)}</dt>
                <dd className={snapshot ? "text-sm font-semibold text-foreground" : "text-sm text-muted-foreground"}>
                  {snapshot ? `${formatCompact(snapshot.views)} views` : "Not complete yet"}
                </dd>
                {snapshot ? (
                  <dd className="numeric text-[0.6875rem] text-muted-foreground">
                    {percent(snapshot.avg_view_percentage)} viewed · {formatCompact(snapshot.likes)} likes
                  </dd>
                ) : null}
              </Inset>
            );
          })}
        </dl>
        <div
          className={
            mature
              ? "rounded-xl border border-tone-ok-border bg-tone-ok-bg px-3.5 py-3"
              : "rounded-xl border border-brand-border bg-brand-soft/50 px-3.5 py-3"
          }
        >
          <p className="text-sm font-semibold text-foreground">
            {mature ? "Enough observation time to compare." : "More observation time is needed."}
          </p>
          <p className="mt-0.5 text-[0.8125rem] leading-relaxed text-muted-foreground">
            {mature
              ? "This video can be compared with similar ones once enough comparable examples exist."
              : "Current counts are useful, but completed 24-hour, 7-day and 28-day windows are stronger evidence."}{" "}
            Nothing here establishes why the video performed as it did.
          </p>
        </div>
      </section>

      {findings.length ? (
        <section className="space-y-3">
          <SectionTitle icon={ScrollText}>Findings</SectionTitle>
          <ul className="space-y-2">
            {findings.map((finding) => {
              const severity = findingSeverity(finding.severity);
              return (
                <li key={finding.code} className="rounded-xl border border-border bg-card p-3.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <EvidenceChip tone={severity.tone}>{severity.label}</EvidenceChip>
                    <p className="text-sm font-medium text-foreground">{finding.explanation}</p>
                  </div>
                  {finding.recommended_interpretation ? (
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                      {finding.recommended_interpretation}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <details className="group rounded-2xl border border-border bg-elevated">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-semibold text-foreground [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-2">
            <Telescope className="size-4 text-muted-foreground" aria-hidden="true" />
            Before publishing
          </span>
          <span className="text-xs font-normal text-muted-foreground group-open:hidden">Show saved checks</span>
        </summary>
        <dl className="grid grid-cols-2 gap-4 border-t border-border p-4 md:grid-cols-4">
          <Field label="Generation quality">{humanize(before.generation_quality?.status || "unavailable")}</Field>
          <Field label="Retention risk">
            {humanize(before.retention_assistant?.risk_level || before.retention_assistant?.status || "unavailable")}
          </Field>
          <Field label="Demand">
            {demand?.id ? (
              <Link to={`/demand?snapshot=${demand.id}`} className="text-brand underline-offset-4 hover:underline">
                {classificationLabel(demand.classification).label}
              </Link>
            ) : (
              "Not checked"
            )}
          </Field>
          <Field label="Idea">
            {before.idea?.id ? (
              <Link to={`/ideas?idea=${before.idea.id}`} className="text-brand underline-offset-4 hover:underline">
                {before.idea.topic || `Idea #${before.idea.id}`}
              </Link>
            ) : (
              "No idea linked"
            )}
          </Field>
        </dl>
      </details>

      <section className="space-y-3">
        <SectionTitle icon={History}>Audit history ({versions.length})</SectionTitle>
        <ul className="divide-y divide-border rounded-2xl border border-border">
          {versions.slice(0, 5).map((version, index) => {
            const state = auditStateLabel(version.summary_state);
            return (
              <li key={version.id} className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
                <span className="text-xs text-muted-foreground">
                  {historyDate(version.captured_at)}
                  {index === 0 ? " · latest" : ""}
                </span>
                <EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>
              </li>
            );
          })}
        </ul>
        {versions.length > 5 ? (
          <p className="text-xs text-muted-foreground">Showing the latest 5 of {versions.length} versions.</p>
        ) : null}
      </section>

      {limitations.length ? (
        <section className="space-y-2.5">
          <SectionTitle icon={ShieldAlert}>Limits of this audit</SectionTitle>
          <ul className="space-y-1.5">
            {limitations.map((limitation) => (
              <li key={limitation} className="flex gap-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
                <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                {limitation}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function NotRun({ candidate, videoId }: { candidate?: AuditCandidate; videoId?: string }) {
  const evidence = evidenceStateLabel(candidate?.evidence_state);
  return (
    <>
      <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
        <VideoThumb videoId={videoId} className="w-full" />
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Published">{historyDate(candidate?.published_at)}</Field>
          <Field label="Views">{formatCompact(candidate?.latest_performance?.views)}</Field>
          <Field label="Performance data">
            <EvidenceChip tone={evidence.tone}>{evidence.label}</EvidenceChip>
          </Field>
          <Field label="Package">
            {candidate?.analysis_run_id ? (
              <Link to={`/history?run=${candidate.analysis_run_id}`} className="text-brand underline-offset-4 hover:underline">
                Run #{candidate.analysis_run_id}
              </Link>
            ) : (
              "Unavailable"
            )}
          </Field>
        </dl>
      </div>
      <Inset className="space-y-1.5 p-4">
        <p className="text-sm font-semibold text-foreground">What an audit does</p>
        <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
          It reads this video from your connected channel, saves its current title, description, tags and counts,
          and captures any 24-hour, 7-day or 28-day analytics window that has come due. Then it compares what went
          live with the package you generated. Every audit is kept as a dated version.
        </p>
      </Inset>
    </>
  );
}

/** Keyed by video, so switching videos never shows another video's error. */
function RefreshAction({ linkId, hasAudit, connected }: { linkId: number; hasAudit: boolean; connected: boolean | null }) {
  const refresh = useRefreshAudit();
  const elapsed = useElapsedSeconds(refresh.isPending);
  const blocked = connected === false;

  const onRefresh = async () => {
    try {
      const data = await refresh.mutateAsync(linkId);
      const captured = asArray<{ snapshot_window?: string }>(data.video_refresh?.captured)
        .map((item) => item.snapshot_window)
        .filter(Boolean);
      toast.success(
        captured.length
          ? `Audit saved. Captured the ${captured.map((window) => windowLabel(window).toLowerCase()).join(", ")}.`
          : "Audit saved with the latest metadata and counts.",
      );
    } catch {
      /* Shown below with its request ID. */
    }
  };

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-elevated p-4" data-testid="audit-actions">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-semibold text-foreground">{hasAudit ? "Refresh this audit" : "Run the first audit"}</p>
          <p className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
            {refresh.isPending
              ? `Reading the video from your channel… ${formatDuration(elapsed)}`
              : blocked
                ? "Connect your YouTube channel first: an audit reads the video from it."
                : "Reads the video from your connected channel, captures any analytics window that's due, and saves a new dated version. Uses a little YouTube quota."}
          </p>
        </div>
        {blocked ? (
          <Button variant="outline" asChild className="shrink-0">
            <Link to="/channel">
              Connect your channel
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        ) : (
          <Button variant="gradient" onClick={() => void onRefresh()} disabled={refresh.isPending} className="shrink-0">
            {refresh.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
            {refresh.isPending ? "Auditing…" : hasAudit ? "Refresh audit" : "Run audit"}
          </Button>
        )}
      </div>
      {refresh.isError ? (
        <ErrorState
          message={apiErrorMessage(refresh.error, "The audit could not be refreshed.")}
          requestId={apiRequestId(refresh.error)}
        />
      ) : null}
    </div>
  );
}

export function AuditDetail({
  linkId,
  candidate,
  detail,
  isLoading,
  error,
  connected,
}: {
  linkId: number | null;
  candidate?: AuditCandidate;
  detail: AuditDetailResponse | null;
  isLoading: boolean;
  error: unknown;
  connected: boolean | null;
}) {
  if (linkId === null) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="Choose a published video"
        description="You'll see whether what went live matches the package you generated, how the video performed in completed windows, and what an audit can and can't establish."
        className="h-full min-h-80"
      />
    );
  }
  // First load only: both the audit and the video's facts must be in hand.
  if (isLoading) {
    return (
      <Card className="p-6">
        <CardSkeleton rows={8} />
      </Card>
    );
  }
  if (error && !detail) {
    return (
      <ErrorState
        message={apiErrorMessage(error, "This audit is unavailable.")}
        requestId={apiRequestId(error)}
      />
    );
  }

  const audit = detail?.audit ?? null;
  const versions = asArray<AuditVersion>(detail?.versions);
  const videoId = candidate?.youtube_video_id ?? audit?.video?.youtube_video_id;
  const title =
    audit?.published_reality?.title ||
    (candidate ? candidateTitle(candidate) : "") ||
    audit?.intent?.generated_package?.title ||
    videoId ||
    "Published video";
  const state = auditStateLabel(audit ? audit.summary?.state : "not_run");

  return (
    <Panel
      data-testid="audit-detail"
      icon={ClipboardCheck}
      title={<span className="text-lg sm:text-xl">{title}</span>}
      description={
        audit
          ? `Audited ${historyDate(audit.captured_at)} · ${versions.length} saved ${versions.length === 1 ? "version" : "versions"}`
          : `Published ${historyDate(candidate?.published_at)} · not audited yet`
      }
      aside={
        <EvidenceChip tone={state.tone} title={state.meaning}>
          {state.label}
        </EvidenceChip>
      }
    >
      <div className="space-y-6">
        {audit ? <AuditBody audit={audit} videoId={videoId} versions={versions} /> : <NotRun candidate={candidate} videoId={videoId} />}
        <RefreshAction key={linkId} linkId={linkId} hasAudit={Boolean(audit)} connected={connected} />
      </div>
    </Panel>
  );
}
