import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Archive,
  ArchiveRestore,
  ArrowRight,
  Clapperboard,
  Compass,
  FileCheck2,
  Lightbulb,
  Loader2,
  Rocket,
  Sparkles,
  Telescope,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { SectionTitle } from "@/components/common/SectionTitle";
import { CardSkeleton, EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { PublicVideoList } from "@/components/research/PublicVideoList";
import { SavedRunNotice } from "@/components/research/SavedRunNotice";
import { StepFlow } from "@/components/research/StepFlow";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import {
  useGenerateIdeaPackage,
  useIdeaDemandResearch,
  useResearchIdea,
  useUpdateIdeaStatus,
} from "@/hooks/useIdeas";
import { formatDuration, useElapsedSeconds } from "@/hooks/useElapsed";
import { relativeTime } from "@/lib/format";
import { historyDate, withReadableDates } from "@/lib/historyFormat";
import { asArray, formatNumber } from "@/lib/utils";
import { classificationLabel } from "@/lib/demandFormat";
import {
  durationLabel,
  ideaActions,
  ideaFormatLabel,
  ideaLanguageLabel,
  ideaLifecycle,
  ideaRegionLabel,
  ideaStatusLabel,
} from "@/lib/ideaFormat";
import type { Idea, IdeaPublicResult } from "@/api/ideaTypes";

function TextList({ items }: { items: [string, string | null | undefined][] }) {
  return (
    <dl className="grid gap-3 md:grid-cols-3">
      {items.map(([label, value]) => (
        <Inset key={label} className="space-y-1">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd
            className={
              value
                ? "whitespace-pre-line break-words text-sm leading-relaxed text-foreground"
                : "text-sm text-muted-foreground"
            }
          >
            {value || "Not supplied"}
          </dd>
        </Inset>
      ))}
    </dl>
  );
}

function ResearchSection({ idea }: { idea: Idea }) {
  const latest = idea.latest_research;
  const evidence = latest?.evidence ?? null;
  const kept = idea.research_snapshots?.length ?? 0;
  const signals = evidence?.signals ?? {};
  const personal = evidence?.personal_evidence ?? {};

  return (
    <section className="space-y-3">
      <SectionTitle
        icon={Telescope}
        aside={evidence ? <EvidenceChip tone="info">Public observation</EvidenceChip> : null}
      >
        Dated research
      </SectionTitle>
      {evidence ? (
        <>
          <Inset className="space-y-2 p-4">
            <p className="text-sm leading-relaxed text-foreground">
              {evidence.opportunity_explanation
                ? withReadableDates(evidence.opportunity_explanation)
                : "No explanation was recorded with this research."}
            </p>
            <p className="text-xs text-muted-foreground">
              Captured {historyDate(latest?.captured_at)}
              {kept > 1 ? ` · ${kept} dated snapshots kept` : ""}
            </p>
          </Inset>

          <dl className="grid grid-cols-3 gap-3">
            {(
              [
                ["Relevant results", signals.relevant_result_count],
                ["Research queries", signals.research_query_count],
                ["Possible outliers", signals.possible_outlier_count],
              ] as const
            ).map(([label, value]) => (
              <Inset key={label} className="space-y-1">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-display text-xl font-semibold leading-none text-foreground">
                  {formatNumber(value)}
                </dd>
              </Inset>
            ))}
          </dl>

          <Inset className="space-y-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
                <UserRound className="size-4 text-muted-foreground" aria-hidden="true" />
                Your channel's evidence
              </p>
              <EvidenceChip tone={personal.learning_allowed ? "ok" : "warn"}>
                {personal.learning_allowed ? "Your published videos" : "Not enough evidence"}
              </EvidenceChip>
            </div>
            <p className="text-sm text-foreground">{personal.message || "Not enough personal evidence."}</p>
            <p className="text-xs text-muted-foreground">
              {formatNumber(personal.sample_size ?? 0)} comparable{" "}
              {personal.sample_size === 1 ? "video" : "videos"} · {personal.confidence_label || "Collecting evidence"}
              {personal.snapshot_window ? ` · ${personal.snapshot_window} window` : ""}
            </p>
          </Inset>

          <PublicVideoList
            videos={asArray<IdeaPublicResult>(evidence.youtube_results)}
            empty="No relevant public results were returned in this snapshot."
          />
        </>
      ) : idea.research_is_stale ? (
        <div className="rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-3 text-[0.8125rem] leading-relaxed text-foreground">
          This idea changed after its last research, so that research no longer applies. Research again before
          generating; {kept === 1 ? "the earlier snapshot is" : `the ${kept} earlier snapshots are`} kept for
          reference.
        </div>
      ) : (
        <UnavailableNote>
          Not researched yet. No search volume, trend, competitor or personal pattern is assumed until you
          research it.
        </UnavailableNote>
      )}
    </section>
  );
}

function DemandSection({ idea }: { idea: Idea }) {
  const latest = idea.latest_demand_research;
  const classification = classificationLabel(latest?.classification);

  return (
    <section className="space-y-3">
      <SectionTitle
        icon={TrendingUp}
        aside={
          latest ? (
            <EvidenceChip tone={latest.stale ? "warn" : classification.tone}>
              {latest.stale ? "Out of date" : classification.label}
            </EvidenceChip>
          ) : (
            <EvidenceChip tone="neutral">Not checked</EvidenceChip>
          )
        }
      >
        Topic demand
      </SectionTitle>
      {latest ? (
        <Inset className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 space-y-1">
            <p className="text-sm leading-relaxed text-foreground">
              {latest.stale
                ? "This idea changed after its last demand check. Check again for a current reading."
                : `${classification.label}: ${classification.meaning}`}
            </p>
            <p className="text-xs text-muted-foreground">Checked {historyDate(latest.captured_at)}</p>
          </div>
          <Button variant="outline" size="sm" asChild className="shrink-0">
            <Link to={`/demand?snapshot=${latest.id}`}>
              Open in Demand
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </Inset>
      ) : (
        <UnavailableNote>
          Demand hasn't been checked for this idea. No market-demand conclusion is assumed.
        </UnavailableNote>
      )}
    </section>
  );
}

/**
 * What the creator can do next. Keyed by idea, so switching ideas starts from
 * a clean slate instead of showing another idea's result.
 */
function IdeaActionBar({ idea }: { idea: Idea }) {
  const research = useResearchIdea();
  const demand = useIdeaDemandResearch();
  const generate = useGenerateIdeaPackage();
  const update = useUpdateIdeaStatus();
  const [runId, setRunId] = useState<number | null>(null);
  const [demandId, setDemandId] = useState<number | null>(null);
  const [failure, setFailure] = useState<{ error: unknown; fallback: string } | null>(null);

  const working = research.isPending || demand.isPending || generate.isPending;
  const busy = working || update.isPending;
  const elapsed = useElapsedSeconds(working);
  const actions = ideaActions(idea);
  const hasResearch = Boolean(idea.latest_research?.evidence);

  const run = async (action: () => Promise<void>, fallback: string) => {
    setFailure(null);
    try {
      await action();
    } catch (error) {
      setFailure({ error, fallback });
    }
  };

  const onResearch = () =>
    run(async () => {
      await research.mutateAsync(idea.id);
      toast.success("Research saved as a dated snapshot.");
    }, "Research failed.");

  const onDemand = () =>
    run(async () => {
      const data = await demand.mutateAsync(idea.id);
      setDemandId(data.research?.id ?? null);
      toast.success("Demand snapshot saved.");
    }, "The demand check failed.");

  const onGenerate = () =>
    run(async () => {
      const data = await generate.mutateAsync(idea.id);
      const saved = data.analysis?.history_run_id;
      setRunId(typeof saved === "number" ? saved : null);
      toast.success("Package generated and saved to History.");
    }, "Package generation failed.");

  const onStatus = (status: string, message: string) =>
    run(async () => {
      await update.mutateAsync({ id: idea.id, status });
      toast.success(message);
    }, "The status could not be changed.");

  const note = research.isPending
    ? `Researching YouTube for this idea… ${formatDuration(elapsed)}`
    : demand.isPending
      ? `Checking demand on YouTube… ${formatDuration(elapsed)}`
      : generate.isPending
        ? `${hasResearch ? "" : "Researching first, then "}writing the package with Gemini… ${formatDuration(elapsed)}. This can take a minute or two.`
        : `Research and demand checks run live YouTube searches, which spend API quota. Generating also uses Gemini${
            hasResearch ? "" : ", and researches first because this idea has no current research"
          }.`;

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-elevated p-4" data-testid="idea-actions">
      {/* Full-width and stacked on phones; one row from `sm`. */}
      <div className="grid gap-2 sm:flex sm:flex-wrap">
        <Button variant="outline" onClick={() => void onResearch()} disabled={busy || !actions.canResearch}>
          {research.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Telescope aria-hidden="true" />}
          {research.isPending ? "Researching…" : "Research now"}
        </Button>
        <Button variant="outline" onClick={() => void onDemand()} disabled={busy || !actions.canResearch}>
          {demand.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <TrendingUp aria-hidden="true" />}
          {demand.isPending ? "Checking…" : "Check demand"}
        </Button>
        <Button variant="gradient" onClick={() => void onGenerate()} disabled={busy || !actions.canGenerate}>
          {generate.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
          {generate.isPending ? "Generating…" : idea.analysis_run_id ? "Generate again" : "Generate package"}
        </Button>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
        {note}
      </p>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {actions.canMarkScripted ? (
          <Button variant="ghost" size="sm" onClick={() => void onStatus("scripted", "Marked as scripted.")} disabled={busy}>
            <FileCheck2 aria-hidden="true" />
            Mark scripted
          </Button>
        ) : null}
        {actions.showMarkPublished ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void onStatus("published", "Marked as published.")}
            disabled={busy || !actions.canMarkPublished}
          >
            <Rocket aria-hidden="true" />
            Mark published
          </Button>
        ) : null}
        {actions.isArchived ? (
          <Button variant="ghost" size="sm" onClick={() => void onStatus(actions.restoreTo, "Idea restored.")} disabled={busy}>
            <ArchiveRestore aria-hidden="true" />
            Restore
          </Button>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => void onStatus("archived", "Idea archived.")} disabled={busy}>
            <Archive aria-hidden="true" />
            Archive
          </Button>
        )}
        {idea.analysis_run_id ? (
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/history?run=${idea.analysis_run_id}`}>
              Open package in History
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        ) : null}
      </div>
      {actions.showMarkPublished && !actions.canMarkPublished ? (
        <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
          Publishing stays manual in YouTube Studio. Mark published unlocks once this idea's package is linked to
          your video in History.
        </p>
      ) : null}

      {failure ? (
        <ErrorState message={apiErrorMessage(failure.error, failure.fallback)} requestId={apiRequestId(failure.error)} />
      ) : null}
      {generate.isSuccess ? <SavedRunNotice runId={runId} /> : null}
      {demand.isSuccess && demandId ? (
        <div
          role="status"
          className="flex flex-col gap-3 rounded-xl border border-tone-ok-border bg-tone-ok-bg p-3.5 sm:flex-row sm:items-center sm:justify-between"
        >
          <p className="text-sm font-medium text-foreground">Demand snapshot #{demandId} saved.</p>
          <Button variant="outline" size="sm" asChild>
            <Link to={`/demand?snapshot=${demandId}`}>
              Open in Demand
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function IdeaDetail({
  idea,
  isLoading,
  error,
  hasSelection,
  hasIdeas,
  onNewIdea,
}: {
  idea: Idea | null;
  isLoading: boolean;
  error: unknown;
  hasSelection: boolean;
  hasIdeas: boolean;
  onNewIdea: () => void;
}) {
  if (!hasSelection) {
    return hasIdeas ? (
      <EmptyState
        icon={Lightbulb}
        title="Choose an idea to inspect"
        description="You'll see its angles and production plan, its dated research, whether demand was checked, and what to do next."
        className="h-full min-h-80"
      />
    ) : (
      <EmptyState
        icon={Lightbulb}
        title="Start your backlog"
        description="Save an idea with its format and angles. Research it with real YouTube data when you're ready, then turn the strongest into a package."
        className="h-full min-h-80"
        action={
          <Button variant="gradient" onClick={onNewIdea}>
            <Lightbulb aria-hidden="true" />
            Add your first idea
          </Button>
        }
      />
    );
  }
  if (isLoading && !idea) {
    return (
      <Card className="p-6">
        <CardSkeleton rows={8} />
      </Card>
    );
  }
  if (error && !idea) {
    return (
      <ErrorState message={apiErrorMessage(error, "This idea is unavailable.")} requestId={apiRequestId(error)} />
    );
  }
  if (!idea) return null;

  const status = ideaStatusLabel(idea.status);
  const edited = idea.updated_at && idea.updated_at !== idea.created_at;

  return (
    <Panel
      data-testid="idea-detail"
      icon={Lightbulb}
      title={<span className="text-lg sm:text-xl">{idea.topic || "Untitled idea"}</span>}
      description={`Saved ${historyDate(idea.created_at)}${edited ? ` · updated ${relativeTime(idea.updated_at)}` : ""}`}
      aside={<EvidenceChip tone={status.tone}>{status.label}</EvidenceChip>}
    >
      <div className="space-y-6">
        {idea.notes ? (
          <p className="whitespace-pre-line break-words text-sm leading-relaxed text-foreground">{idea.notes}</p>
        ) : (
          <p className="text-sm text-muted-foreground">No notes or outline yet.</p>
        )}

        <StepFlow label="Where this idea is" steps={ideaLifecycle(idea)} />

        <dl className="grid grid-cols-2 gap-4 rounded-2xl border border-border bg-elevated p-4 md:grid-cols-3">
          <Field label="Format">{ideaFormatLabel(idea.format)}</Field>
          <Field label="Language">{ideaLanguageLabel(idea.language)}</Field>
          <Field label="Region">{ideaRegionLabel(idea.region)}</Field>
          <Field label="Target duration">{durationLabel(idea.target_duration_seconds)}</Field>
          <Field label="Package">
            {idea.analysis_run_id ? (
              <Link to={`/history?run=${idea.analysis_run_id}`} className="text-brand underline-offset-4 hover:underline">
                Run #{idea.analysis_run_id}
              </Link>
            ) : (
              "Not generated"
            )}
          </Field>
          <Field label="Published video">{idea.published_video_link_id ? "Linked in History" : "Not linked"}</Field>
        </dl>

        <section className="space-y-3">
          <SectionTitle icon={Compass} aside={<EvidenceChip tone="ok">Creator-entered</EvidenceChip>}>
            Angles
          </SectionTitle>
          <TextList
            items={[
              ["Search angle", idea.search_angle],
              ["Browse angle", idea.browse_angle],
              ["Existing audience angle", idea.audience_angle],
            ]}
          />
        </section>

        <section className="space-y-3">
          <SectionTitle icon={Clapperboard} aside={<EvidenceChip tone="ok">Creator-entered</EvidenceChip>}>
            Production plan
          </SectionTitle>
          <TextList
            items={[
              ["Visual or background", idea.visual_or_background],
              ["On-screen text", idea.on_screen_text],
              ["Emotion or intent", idea.emotion_or_intent],
            ]}
          />
        </section>

        <ResearchSection idea={idea} />
        <DemandSection idea={idea} />
        <IdeaActionBar key={idea.id} idea={idea} />
      </div>
    </Panel>
  );
}
