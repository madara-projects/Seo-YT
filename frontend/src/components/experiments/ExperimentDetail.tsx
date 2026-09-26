import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  FlaskConical,
  GitCompareArrows,
  Loader2,
  Plus,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { FormField } from "@/components/common/FormField";
import { OptionSelect } from "@/components/common/OptionSelect";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { SectionTitle } from "@/components/common/SectionTitle";
import { CardSkeleton, EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { useRecordActivity } from "@/hooks/useRecordActivity";
import {
  useAssignVideo,
  useCompareExperiment,
  useRemoveAssignment,
  useUpdateExperimentStatus,
} from "@/hooks/useExperiments";
import { historyDate, shortDate } from "@/lib/historyFormat";
import { humanize } from "@/lib/labels";
import { asArray } from "@/lib/utils";
import { candidateTitle } from "@/lib/auditFormat";
import {
  directionLabel,
  experimentStatusLabel,
  isClosed,
  metricLabel,
  metricValue,
  minimumPerGroup,
  modeLabel,
  observationWindowLabel,
  relativeDifference,
  resultStateLabel,
  transitionsFrom,
  variableLabel,
  type Transition,
} from "@/lib/experimentFormat";
import type { AuditCandidate } from "@/api/auditTypes";
import type {
  Experiment,
  ExperimentAssignment,
  ExperimentDetailResponse,
  ExperimentMetricResult,
  MissingMetric,
} from "@/api/experimentTypes";

function GroupCard({
  experimentId,
  title,
  definition,
  assignments,
  closed,
}: {
  experimentId: number;
  title: string;
  definition?: string;
  assignments: ExperimentAssignment[];
  /** A closed comparison keeps its sides as they were compared. */
  closed: boolean;
}) {
  const remove = useRemoveAssignment(experimentId);
  const busy = useRecordActivity("experiment", experimentId).pending !== null;
  const onRemove = async (assignment: ExperimentAssignment) => {
    try {
      await remove.mutateAsync({ id: experimentId, assignmentId: assignment.id });
      toast.success("Video removed from this side.");
    } catch (error) {
      toast.error(formatApiError(error, "The video could not be removed."));
    }
  };

  return (
    <Inset className="space-y-3 p-4" data-testid={`group-${title.toLowerCase().replaceAll(" ", "-")}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <EvidenceChip tone="neutral">{assignments.length} assigned</EvidenceChip>
      </div>
      {definition ? <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{definition}</p> : null}
      {assignments.length ? (
        <ul className="space-y-1.5">
          {assignments.map((assignment) => {
            const label = assignment.title || assignment.youtube_video_id || `Link #${assignment.published_video_link_id}`;
            return (
              <li key={assignment.id} className="flex items-center gap-2.5 rounded-lg bg-card p-1.5 pr-1">
                <VideoThumb videoId={assignment.youtube_video_id} className="w-14" />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-xs font-medium leading-snug text-foreground">{label}</span>
                  <span className="block text-[0.6875rem] text-muted-foreground">
                    Published {shortDate(assignment.published_at)}
                  </span>
                </span>
                {closed ? null : (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => void onRemove(assignment)}
                    disabled={busy}
                    aria-label={`Remove ${label}`}
                  >
                    <X aria-hidden="true" />
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">No videos on this side yet.</p>
      )}
    </Inset>
  );
}

function AssignForm({
  experiment,
  candidates,
  channelId,
  connected,
}: {
  experiment: Experiment;
  candidates: AuditCandidate[];
  channelId: string | null;
  connected: boolean | null;
}) {
  const assign = useAssignVideo(experiment.id);
  const activity = useRecordActivity("experiment", experiment.id);
  const busy = activity.pending !== null;
  const lastAssign = activity.latestOf("assign");
  const [linkId, setLinkId] = useState("");
  const [role, setRole] = useState("control");
  const assigned = new Set(asArray<ExperimentAssignment>(experiment.assignments).map((item) => item.published_video_link_id));
  const eligible = candidates.filter(
    (item) => item.ownership_verified && channelId && item.verified_channel_id === channelId && !assigned.has(item.id),
  );
  const roles = [
    { value: "control", label: "Control" },
    { value: "variant", label: "Variant" },
    ...(experiment.mode === "observational" ? [{ value: "observational_reference", label: "Reference only" }] : []),
  ];

  const blocker = isClosed(experiment.status)
    ? "This comparison is closed, so it takes no new videos."
    : connected === false
      ? "Connect your channel to assign videos: only videos verified for it can be used."
      : connected && !eligible.length
        ? "No other verified videos from your connected channel. A video is verified once it's read from your channel, for example by running its audit."
        : null;

  const onAssign = async () => {
    const id = Number(linkId);
    if (!id) return;
    try {
      await assign.mutateAsync({ id: experiment.id, linkId: id, role });
      setLinkId("");
      toast.success(`Added to ${role === "variant" ? "the variant" : role === "control" ? "the control" : "the references"}. It counts once its ${observationWindowLabel(experiment.observation_window).toLowerCase()} window completes.`);
    } catch (error) {
      // Also shown below; the toast reaches the creator if they've opened another comparison.
      toast.error(formatApiError(error, "The video could not be added."));
    }
  };

  return (
    <section className="space-y-3">
      <SectionTitle icon={Plus}>Assign a video</SectionTitle>
      {blocker ? (
        <UnavailableNote className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{blocker}</span>
          {connected === false && !isClosed(experiment.status) ? (
            <Button variant="outline" size="sm" asChild className="shrink-0">
              <Link to="/channel">
                Connect your channel
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          ) : null}
        </UnavailableNote>
      ) : (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
          <FormField id="assign-video" label="Verified video">
            <OptionSelect
              id="assign-video"
              ariaLabel="Verified video"
              value={linkId}
              onValueChange={setLinkId}
              options={[
                { value: "", label: "Choose a video" },
                ...eligible.map((item) => ({ value: String(item.id), label: candidateTitle(item) })),
              ]}
            />
          </FormField>
          <FormField id="assign-role" label="Side">
            <OptionSelect id="assign-role" ariaLabel="Side" value={role} onValueChange={setRole} options={roles} />
          </FormField>
          <Button variant="outline" onClick={() => void onAssign()} disabled={!linkId || busy}>
            {lastAssign?.status === "pending" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Plus aria-hidden="true" />}
            Add video
          </Button>
        </div>
      )}
      {lastAssign?.status === "error" && !blocker ? (
        <ErrorState message={apiErrorMessage(lastAssign.error, "The video could not be added.")} requestId={apiRequestId(lastAssign.error)} />
      ) : null}
    </section>
  );
}

function MetricRow({ item }: { item: ExperimentMetricResult }) {
  return (
    <li className="space-y-2 rounded-xl border border-border bg-card p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{metricLabel(item.metric)}</p>
        <EvidenceChip tone="neutral">{directionLabel(item.observed_direction)}</EvidenceChip>
      </div>
      <dl className="grid grid-cols-3 gap-2">
        <div>
          <dt className="text-[0.6875rem] text-muted-foreground">Control median</dt>
          <dd className="numeric text-sm font-medium text-foreground">
            {metricValue(item.metric, item.control?.median)}{" "}
            <span className="text-[0.6875rem] font-normal text-muted-foreground">n={item.control?.sample_size ?? 0}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[0.6875rem] text-muted-foreground">Variant median</dt>
          <dd className="numeric text-sm font-medium text-foreground">
            {metricValue(item.metric, item.variant?.median)}{" "}
            <span className="text-[0.6875rem] font-normal text-muted-foreground">n={item.variant?.sample_size ?? 0}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[0.6875rem] text-muted-foreground">Difference</dt>
          <dd className="numeric text-sm font-medium text-foreground">{relativeDifference(item.relative_difference_percent)}</dd>
        </div>
      </dl>
    </li>
  );
}

function ResultSection({ experiment, versionCount }: { experiment: Experiment; versionCount: number }) {
  const result = experiment.latest_result;
  if (!result) {
    return (
      <section className="space-y-3">
        <SectionTitle icon={GitCompareArrows}>Result</SectionTitle>
        <UnavailableNote>
          Not compared yet. Once enough assigned videos have a completed{" "}
          {observationWindowLabel(experiment.observation_window).toLowerCase()} window, compare them here. No direction is
          claimed and no statistical significance is invented.
        </UnavailableNote>
      </section>
    );
  }
  const state = resultStateLabel(result.state);
  const sample = result.sample ?? {};
  const metrics = asArray<ExperimentMetricResult>(result.metrics);
  const limitations = asArray<string>(result.limitations);
  const missing = asArray<MissingMetric>(sample.missing_metrics);
  const titles = new Map(
    asArray<ExperimentAssignment>(experiment.assignments).map((item) => [
      item.published_video_link_id,
      item.title || item.youtube_video_id || `Link #${item.published_video_link_id}`,
    ]),
  );

  return (
    <section className="space-y-3" data-testid="experiment-result">
      <SectionTitle icon={GitCompareArrows} aside={<EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>}>
        Result
      </SectionTitle>
      <Inset className="space-y-2 p-4">
        {result.label ? (
          <p className="text-[0.6875rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            {result.label}
          </p>
        ) : null}
        <p className="text-sm leading-relaxed text-foreground">{result.interpretation}</p>
        <p className="text-xs text-muted-foreground">
          Compared {historyDate(result.captured_at)} · {sample.eligible_control ?? 0} control and{" "}
          {sample.eligible_variant ?? 0} variant videos had a completed window; at least {sample.minimum_per_group ?? 5}{" "}
          per side are needed.
        </p>
      </Inset>
      {missing.length ? (
        <div className="space-y-1.5 rounded-xl border border-dashed border-border px-3.5 py-3">
          <p className="text-xs font-medium text-foreground">
            Left out: {missing.length} assigned {missing.length === 1 ? "video has" : "videos have"} no completed{" "}
            {observationWindowLabel(experiment.observation_window).toLowerCase()} window yet
          </p>
          <ul className="space-y-0.5">
            {missing.map((item, index) => (
              <li key={`${item.link_id}-${index}`} className="text-xs text-muted-foreground">
                {(item.link_id != null && titles.get(item.link_id)) || `Link #${item.link_id ?? "unknown"}`} ·{" "}
                {item.role === "variant" ? "variant" : item.role === "control" ? "control" : humanize(String(item.role ?? ""))}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {metrics.length ? (
        <ul className="space-y-2" aria-label="Metrics compared">
          {metrics.map((item) => (
            <MetricRow key={item.metric} item={item} />
          ))}
        </ul>
      ) : null}
      {result.next_recommendation ? (
        <p className="text-sm font-medium text-foreground">{result.next_recommendation}</p>
      ) : null}
      {result.learning_candidate ? (
        <div className="rounded-xl border border-brand-border bg-brand-soft/50 px-3.5 py-3">
          <p className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
            <Sparkles className="size-4 text-brand" aria-hidden="true" />
            Candidate observation
          </p>
          <p className="mt-1 text-[0.8125rem] leading-relaxed text-muted-foreground">
            {variableLabel(result.learning_candidate.variable)}, from {result.learning_candidate.sample_size ?? 0} videos.{" "}
            {result.learning_candidate.interpretation}
          </p>
        </div>
      ) : null}
      {limitations.length ? (
        <ul className="space-y-1.5">
          {limitations.map((limitation) => (
            <li key={limitation} className="flex gap-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
              {limitation}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs text-muted-foreground">
        {versionCount} saved {versionCount === 1 ? "comparison" : "comparisons"}. Results never change YouTube or your
        future packages on their own.
      </p>
    </section>
  );
}

const ACTION_FAILURES: Record<string, string> = {
  compare: "The comparison could not be saved.",
  status: "The status could not be changed.",
};

/**
 * Compare and status changes. Their state is read from the mutation cache
 * for this experiment, so opening another comparison and coming back still
 * shows one in flight, with the buttons disabled, and the error it ended with.
 */
function ExperimentActions({ experiment, connected }: { experiment: Experiment; connected: boolean | null }) {
  const compare = useCompareExperiment(experiment.id);
  const update = useUpdateExperimentStatus(experiment.id);
  const activity = useRecordActivity("experiment", experiment.id);
  const [confirming, setConfirming] = useState<Transition | null>(null);
  const busy = activity.pending !== null;
  const comparing = activity.pending?.action === "compare";
  const lastRun = activity.latest;
  const failure = lastRun?.status === "error" && ACTION_FAILURES[lastRun.action] ? lastRun : null;
  // A closed comparison keeps its last result: comparing again would rewrite it.
  const closed = isClosed(experiment.status);
  const transitions = transitionsFrom(experiment.status);
  const next = transitions.find((transition) => transition.primary);
  const others = transitions.filter((transition) => !transition.primary);
  const request = (transition: Transition) =>
    transition.final ? setConfirming(transition) : void onTransition(transition);

  const onCompare = async () => {
    try {
      const data = await compare.mutateAsync(experiment.id);
      toast.success(`Comparison saved: ${resultStateLabel(data.result?.state).label.toLowerCase()}.`);
    } catch (error) {
      toast.error(formatApiError(error, ACTION_FAILURES.compare));
    }
  };

  const onTransition = async (transition: Transition) => {
    try {
      await update.mutateAsync({ id: experiment.id, status: transition.to });
      toast.success(`Status changed to ${experimentStatusLabel(transition.to).label.toLowerCase()}.`);
      setConfirming(null);
    } catch (error) {
      setConfirming(null);
      toast.error(formatApiError(error, ACTION_FAILURES.status));
    }
  };

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-elevated p-4" data-testid="experiment-actions">
      <div className="grid gap-2 sm:flex sm:flex-wrap">
        {closed ? null : (
          <Button variant="gradient" onClick={() => void onCompare()} disabled={busy || connected === false}>
            {comparing ? <Loader2 className="animate-spin" aria-hidden="true" /> : <GitCompareArrows aria-hidden="true" />}
            {comparing ? "Comparing…" : "Compare saved evidence"}
          </Button>
        )}
        {next ? (
          <Button variant="outline" onClick={() => request(next)} disabled={busy}>
            {next.label}
          </Button>
        ) : null}
      </div>
      {others.length ? (
        <div className="flex flex-wrap gap-1 border-t border-border pt-3">
          {others.map((transition) => (
            <Button key={transition.to} variant="ghost" size="sm" onClick={() => request(transition)} disabled={busy}>
              {transition.label}
            </Button>
          ))}
        </div>
      ) : null}
      <p className="text-xs leading-relaxed text-muted-foreground">
        {closed
          ? "This comparison is closed, so its saved result stays as it is: it can't be compared again or take new videos."
          : connected === false
            ? "Comparing needs your channel connected, so only videos verified for it are counted."
            : "Comparing reads the completed snapshots already saved for each assigned video. It makes no YouTube call."}
      </p>
      {failure ? (
        <ErrorState
          message={apiErrorMessage(failure.error, ACTION_FAILURES[failure.action])}
          requestId={apiRequestId(failure.error)}
        />
      ) : null}
      <ConfirmDialog
        open={confirming !== null}
        onOpenChange={(open) => (open ? undefined : setConfirming(null))}
        icon={TriangleAlert}
        title={confirming ? `${confirming.label}?` : ""}
        description={
          confirming?.to === "cancelled"
            ? "A cancelled comparison can't be restarted or take new videos. Its saved results stay readable."
            : `A ${confirming ? experimentStatusLabel(confirming.to).label.toLowerCase() : ""} comparison can't be reopened or take new videos. Its saved results stay readable.`
        }
        confirmLabel={confirming?.label ?? "Confirm"}
        pendingLabel="Saving…"
        pending={activity.pending?.action === "status"}
        destructive={confirming?.to === "cancelled"}
        onConfirm={() => (confirming ? void onTransition(confirming) : undefined)}
      />
    </div>
  );
}

export function ExperimentDetail({
  experimentId,
  detail,
  isLoading,
  error,
  connected,
  channelId,
  candidates,
  onNew,
  hasExperiments,
}: {
  experimentId: number | null;
  detail: ExperimentDetailResponse | null;
  isLoading: boolean;
  error: unknown;
  connected: boolean | null;
  channelId: string | null;
  candidates: AuditCandidate[];
  onNew: () => void;
  hasExperiments: boolean;
}) {
  if (experimentId === null) {
    return (
      <EmptyState
        icon={FlaskConical}
        title={hasExperiments ? "Choose a comparison" : "Start only with a real question"}
        description={
          hasExperiments
            ? "You'll see both sides with their assigned videos, what the saved evidence shows, and what it can't."
            : "Create a comparison, assign your own verified videos to each side, then compare the same completed window for both."
        }
        className="h-full min-h-80"
        action={
          hasExperiments ? undefined : (
            <Button variant="gradient" onClick={onNew}>
              <FlaskConical aria-hidden="true" />
              New experiment
            </Button>
          )
        }
      />
    );
  }
  const experiment = detail?.experiment ?? null;
  if (isLoading && !experiment) {
    return (
      <Card className="p-6">
        <CardSkeleton rows={8} />
      </Card>
    );
  }
  if (error && !experiment) {
    return (
      <ErrorState message={apiErrorMessage(error, "This comparison is unavailable.")} requestId={apiRequestId(error)} />
    );
  }
  if (!experiment) return null;

  const status = experimentStatusLabel(experiment.status);
  const kind = modeLabel(experiment.mode);
  const assignments = asArray<ExperimentAssignment>(experiment.assignments);
  const observational = experiment.mode === "observational";
  const closed = isClosed(experiment.status);
  const secondary = asArray<string>(experiment.secondary_metrics);

  return (
    <Panel
      data-testid="experiment-detail"
      icon={FlaskConical}
      title={<span className="text-lg sm:text-xl">{experiment.name}</span>}
      description={`${kind.label} · created ${historyDate(experiment.created_at)}`}
      aside={<EvidenceChip tone={status.tone}>{status.label}</EvidenceChip>}
    >
      <div className="space-y-6">
        <blockquote className="border-l-2 border-brand-border pl-3.5 text-sm italic leading-relaxed text-foreground">
          {experiment.hypothesis}
        </blockquote>
        <p className="flex items-start gap-2 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-2.5 text-[0.8125rem] font-medium text-foreground">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
          {observational
            ? "Observational comparison: the videos weren't assigned before publishing, so this is not a controlled experiment."
            : "A planned comparison gives directional evidence, never causal proof."}
        </p>

        <dl className="grid grid-cols-2 gap-4 rounded-2xl border border-border bg-elevated p-4 md:grid-cols-4">
          <Field label="What changes">{variableLabel(experiment.variable)}</Field>
          <Field label="Primary metric">
            {metricLabel(experiment.success_metric)}
            {secondary.length ? (
              <span className="block text-xs font-normal text-muted-foreground">
                Also: {secondary.map((metric) => metricLabel(metric)).join(", ")}
              </span>
            ) : null}
          </Field>
          <Field label="Window">{observationWindowLabel(experiment.observation_window)}</Field>
          <Field label="Needed per side">{minimumPerGroup(experiment.minimum_sample_size)} videos</Field>
        </dl>

        <div className="grid gap-3 md:grid-cols-2">
          <GroupCard
            experimentId={experiment.id}
            closed={closed}
            title="Control"
            definition={experiment.control_definition}
            assignments={assignments.filter((item) => item.role === "control")}
          />
          <GroupCard
            experimentId={experiment.id}
            closed={closed}
            title="Variant"
            definition={experiment.variant_definition}
            assignments={assignments.filter((item) => item.role === "variant")}
          />
        </div>
        {observational ? (
          <GroupCard
            experimentId={experiment.id}
            closed={closed}
            title="References"
            definition="Kept for context; references are not counted on either side."
            assignments={assignments.filter((item) => item.role === "observational_reference")}
          />
        ) : null}

        <AssignForm key={`assign:${experiment.id}`} experiment={experiment} candidates={candidates} channelId={channelId} connected={connected} />
        <ResultSection experiment={experiment} versionCount={asArray(detail?.result_versions).length} />
        <ExperimentActions key={`actions:${experiment.id}`} experiment={experiment} connected={connected} />
      </div>
    </Panel>
  );
}
