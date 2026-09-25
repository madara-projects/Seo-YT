import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  Binoculars,
  Brain,
  CheckCircle2,
  Loader2,
  Scale,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UserRound,
  Youtube,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { CardSkeleton, EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { useGenerateFromDemand } from "@/hooks/useDemand";
import { formatDuration, useElapsedSeconds } from "@/hooks/useElapsed";
import { asArray, formatNumber } from "@/lib/utils";
import { historyDate, shortDate } from "@/lib/historyFormat";
import {
  classificationLabel,
  formatLabel,
  languageLabel,
  regionLabel,
  signalName,
  sourceLabel,
} from "@/lib/demandFormat";
import type {
  DemandPublicResult,
  DemandSignal,
  DemandSnapshot,
  DemandWatchlistMatch,
} from "@/api/researchTypes";

const PUBLIC_RESULTS_SHOWN = 8;

function SectionTitle({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-display text-sm font-semibold text-foreground">{children}</h3>
      {aside}
    </div>
  );
}

function SignalTile({ signal }: { signal: DemandSignal }) {
  const source = sourceLabel(signal.source);
  const value =
    signal.observed === null || signal.observed === undefined ? "Unavailable" : formatNumber(signal.observed);
  return (
    <Inset className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{signalName(signal.name)}</p>
      <div className="flex items-end justify-between gap-2">
        <p
          className={
            value === "Unavailable"
              ? "text-sm font-medium text-muted-foreground"
              : "font-display text-2xl font-semibold leading-none tracking-tight text-foreground"
          }
        >
          {value}
        </p>
        <EvidenceChip tone={source.tone} className="shrink-0">
          {source.label}
        </EvidenceChip>
      </div>
      {signal.limitation ? (
        <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">{signal.limitation}</p>
      ) : null}
    </Inset>
  );
}

function outlierLabel(status?: string): string {
  if (status === "possible_outlier") return "Possible outlier";
  if (!status || status === "not_analyzed") return "Not analysed";
  return status.replaceAll("_", " ");
}

function GenerateAction({ snapshot }: { snapshot: DemandSnapshot }) {
  const generate = useGenerateFromDemand();
  const elapsed = useElapsedSeconds(generate.isPending);
  const [runId, setRunId] = useState<number | null>(null);

  const onGenerate = async () => {
    try {
      const result = await generate.mutateAsync(snapshot.id);
      const saved = result.analysis?.history_run_id;
      setRunId(typeof saved === "number" ? saved : null);
      toast.success("Package generated and saved to History.");
    } catch (error) {
      toast.error(formatApiError(error, "Package generation failed."));
    }
  };

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-elevated p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-semibold text-foreground">Turn this topic into a package</p>
          <p className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
            {generate.isPending
              ? `Writing the package with Gemini… ${formatDuration(elapsed)}. This can take a minute or two.`
              : snapshot.idea_id
                ? "This snapshot belongs to an idea, so the idea's own research is used (collected fresh if it has none) and the package is linked back to it. Saved to History; publishing stays manual."
                : "Uses the public results in this snapshot and the Creator engine (Gemini). The package is saved to History; publishing stays manual."}
          </p>
        </div>
        <Button
          variant="gradient"
          onClick={() => void onGenerate()}
          disabled={generate.isPending}
          className="shrink-0"
        >
          {generate.isPending ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles aria-hidden="true" />
          )}
          {generate.isPending ? "Generating…" : "Generate package"}
        </Button>
      </div>

      {generate.isError ? (
        <ErrorState
          message={apiErrorMessage(generate.error, "Package generation failed.")}
          requestId={apiRequestId(generate.error)}
        />
      ) : null}

      {generate.isSuccess ? (
        <div
          role="status"
          className="flex flex-col gap-3 rounded-xl border border-tone-ok-border bg-tone-ok-bg p-3.5 sm:flex-row sm:items-center sm:justify-between"
        >
          <p className="flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle2 className="size-4 shrink-0 text-tone-ok" aria-hidden="true" />
            {runId ? `Package saved to History as run #${runId}.` : "Package generated and saved to History."}
          </p>
          <Button variant="outline" size="sm" asChild>
            <Link to={runId ? `/history?run=${runId}` : "/history"}>
              Open in History
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function SnapshotDetail({
  snapshot,
  isLoading,
  error,
  hasSelection,
}: {
  snapshot: DemandSnapshot | null;
  isLoading: boolean;
  error: unknown;
  hasSelection: boolean;
}) {
  if (!hasSelection) {
    return (
      <EmptyState
        icon={Binoculars}
        title="Choose a snapshot to inspect"
        description="You'll see how interest was classified and why, the public videos that were sampled, matching watchlist outliers, whether your own published videos can add evidence, and the limits of what was measured."
        className="h-full min-h-80"
      />
    );
  }
  if (isLoading && !snapshot) {
    return (
      <Card className="p-6">
        <CardSkeleton rows={8} />
      </Card>
    );
  }
  if (error && !snapshot) {
    return (
      <ErrorState
        message={apiErrorMessage(error, "This demand snapshot is unavailable.")}
        requestId={apiRequestId(error)}
      />
    );
  }
  if (!snapshot) return null;

  const evidence = snapshot.evidence ?? {};
  const classification = classificationLabel(snapshot.classification);
  const signals = asArray<DemandSignal>(evidence.signals);
  const reasons = asArray<string>(evidence.reasons);
  const results = asArray<DemandPublicResult>(evidence.public_results);
  const watchlist = asArray<DemandWatchlistMatch>(evidence.watchlist_evidence);
  const outliers = watchlist.filter((item) => item.outlier_status === "possible_outlier").length;
  const personal = evidence.personal_evidence ?? {};
  const limitations = asArray<string>(evidence.limitations);
  const sampled = signals.find((signal) => signal.name === "sampled_relevant_results")?.observed;

  return (
    <Panel
      data-testid="demand-detail"
      icon={TrendingUp}
      title={<span className="text-lg sm:text-xl">{snapshot.topic || "Untitled topic"}</span>}
      description={`Snapshot captured ${historyDate(snapshot.captured_at)}. It never changes; research again to see how interest has moved.`}
      aside={<EvidenceChip tone={classification.tone}>{classification.label}</EvidenceChip>}
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-1.5">
          {[languageLabel(snapshot.language), formatLabel(snapshot.format), regionLabel(snapshot.region)].map(
            (label) => (
              <span
                key={label}
                className="rounded-lg border border-border bg-elevated px-2.5 py-1 text-xs text-muted-foreground"
              >
                {label}
              </span>
            ),
          )}
          {snapshot.audience_context ? (
            <span className="rounded-lg border border-border bg-elevated px-2.5 py-1 text-xs text-muted-foreground">
              Audience: {snapshot.audience_context}
            </span>
          ) : null}
        </div>

        <ol className="grid gap-2 sm:grid-cols-3" aria-label="How this snapshot was classified">
          {[
            { step: "1. Topic", value: snapshot.topic || "Untitled topic" },
            {
              step: "2. Public signals",
              value:
                typeof sampled === "number"
                  ? `${formatNumber(sampled)} sampled ${sampled === 1 ? "result" : "results"}`
                  : "Unavailable",
            },
            { step: "3. Classification", value: classification.label },
          ].map((item) => (
            <li key={item.step} className="rounded-xl border border-border bg-card p-3">
              <p className="text-[0.6875rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                {item.step}
              </p>
              <p className="mt-1 line-clamp-2 text-sm font-semibold text-foreground">{item.value}</p>
            </li>
          ))}
        </ol>

        <div className="rounded-2xl border border-brand-border bg-brand-soft/50 p-4">
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-brand">
            What “{classification.label}” means
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground">{classification.meaning}</p>
        </div>

        <section className="space-y-3">
          <SectionTitle aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}>
            <span className="inline-flex items-center gap-2">
              <Brain className="size-4 text-muted-foreground" aria-hidden="true" />
              Why this classification
            </span>
          </SectionTitle>
          {reasons.length ? (
            <ul className="space-y-1.5">
              {reasons.map((reason, index) => (
                <li key={index} className="flex gap-2 text-sm leading-relaxed text-foreground">
                  <BadgeCheck className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden="true" />
                  {reason}
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>No classification reason was recorded.</UnavailableNote>
          )}
        </section>

        <section className="space-y-3">
          <SectionTitle>
            <span className="inline-flex items-center gap-2">
              <Scale className="size-4 text-muted-foreground" aria-hidden="true" />
              Observed signals
            </span>
          </SectionTitle>
          {signals.length ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {signals.map((signal, index) => (
                <SignalTile key={signal.name ?? index} signal={signal} />
              ))}
            </div>
          ) : (
            <UnavailableNote>No signals were observed in public data.</UnavailableNote>
          )}
        </section>

        <section className="space-y-3">
          <SectionTitle aside={<EvidenceChip tone="info">Public observation</EvidenceChip>}>
            <span className="inline-flex items-center gap-2">
              <Youtube className="size-4 text-muted-foreground" aria-hidden="true" />
              Sampled public videos
            </span>
          </SectionTitle>
          {results.length ? (
            <ul className="divide-y divide-border rounded-2xl border border-border">
              {results.slice(0, PUBLIC_RESULTS_SHOWN).map((result, index) => (
                <li
                  key={result.video_id ?? index}
                  // On phones the count sits under the title so the title keeps
                  // its room; wider screens give the count a column of its own.
                  className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-0.5 p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
                >
                  <VideoThumb
                    videoId={result.video_id}
                    title={result.title}
                    className="row-span-2 w-20 sm:row-span-1 sm:w-28"
                  />
                  <div className="min-w-0 self-end sm:self-center">
                    <p className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-foreground">
                      {result.title || "Untitled video"}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {result.channel_title || "Channel unavailable"} · {shortDate(result.published_at)}
                    </p>
                  </div>
                  <p className="self-start text-xs text-muted-foreground sm:self-center sm:text-right sm:text-[0.6875rem]">
                    <span className="numeric font-semibold text-foreground sm:block sm:text-[0.8125rem]">
                      {formatNumber(result.view_count)}
                    </span>{" "}
                    views at capture
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>No public results were stored with this snapshot.</UnavailableNote>
          )}
          {results.length > PUBLIC_RESULTS_SHOWN ? (
            <p className="text-xs text-muted-foreground">
              Showing {PUBLIC_RESULTS_SHOWN} of {results.length} sampled results.
            </p>
          ) : null}
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <Inset className="space-y-2.5 p-4">
            <SectionTitle aside={<EvidenceChip tone="info">Public observation</EvidenceChip>}>
              Watchlist matches
            </SectionTitle>
            <p className="text-sm text-foreground">
              {watchlist.length} matching saved {watchlist.length === 1 ? "video" : "videos"}, {outliers}{" "}
              possible {outliers === 1 ? "outlier" : "outliers"}.
            </p>
            {watchlist.length ? (
              <ul className="space-y-1.5">
                {watchlist.slice(0, 5).map((item, index) => (
                  <li key={item.video_id ?? index} className="flex items-center justify-between gap-2 text-xs">
                    <span className="min-w-0 truncate text-foreground">{item.title || item.video_id}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {outlierLabel(item.outlier_status)}
                      {typeof item.relative_multiplier === "number"
                        ? ` · ${item.relative_multiplier.toFixed(1)}× peers`
                        : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
              Outliers show observed engagement speed, not a prediction that a video will go viral.
            </p>
          </Inset>

          <Inset className="space-y-2.5 p-4">
            <SectionTitle
              aside={
                <EvidenceChip tone={personal.learning_allowed ? "ok" : "warn"}>
                  {personal.confidence_label || (personal.learning_allowed ? "Eligible" : "Collecting evidence")}
                </EvidenceChip>
              }
            >
              <span className="inline-flex items-center gap-2">
                <UserRound className="size-4 text-muted-foreground" aria-hidden="true" />
                Your channel's evidence
              </span>
            </SectionTitle>
            <p className="text-sm text-foreground">
              {personal.learning_allowed
                ? "Enough mature, comparable history from your published videos is available for this topic."
                : "Not enough mature, comparable history from your published videos exists for this topic yet."}
            </p>
            <p className="text-xs text-muted-foreground">
              Comparable videos: {formatNumber(personal.sample_size ?? 0)}
            </p>
          </Inset>
        </div>

        <section className="space-y-2.5">
          <SectionTitle>
            <span className="inline-flex items-center gap-2">
              <ShieldAlert className="size-4 text-muted-foreground" aria-hidden="true" />
              Limits of this evidence
            </span>
          </SectionTitle>
          <ul className="space-y-1.5">
            {(limitations.length
              ? limitations
              : ["Public observations and keyword signals do not guarantee search volume or future reach."]
            ).map((limitation, index) => (
              <li key={index} className="flex gap-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
                <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                {limitation}
              </li>
            ))}
          </ul>
        </section>

        <GenerateAction key={snapshot.id} snapshot={snapshot} />
      </div>
    </Panel>
  );
}
