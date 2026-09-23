import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import {
  CardSkeleton,
  ErrorState,
  GridSkeleton,
  UnavailableNote,
} from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AngleChart } from "@/components/dashboard/AngleChart";
import { QuickLaunch } from "@/components/dashboard/QuickLaunch";
import { useCohortLearning, useHistorySummary } from "@/hooks/useHistory";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, formatNumber } from "@/lib/utils";
import { historyDate } from "@/lib/historyFormat";
import {
  formatWatchTime,
  riskTone,
  roundOpportunity,
  roundTitleScore,
  savedAnalysesCaption,
} from "@/lib/dashboardFormat";
import type {
  AngleEffectiveness,
  RecentRun,
  RetentionPattern,
  WinningTitle,
} from "@/api/historyTypes";

/** The creator loop, as the legacy dashboard framed it. Publishing is manual. */
const LOOP_STEPS = [
  { label: "Idea", to: "/ideas" },
  { label: "Research", to: "/demand" },
  { label: "Package", to: "/creator" },
  { label: "Publish", to: null },
  { label: "Audit", to: "/audits" },
  { label: "Learn", to: "/history" },
] as const;

export default function DashboardPage() {
  const summary = useHistorySummary();
  const cohorts = useCohortLearning();

  const learning = asObject(summary.data?.learning);
  const scorecard = asObject(summary.data?.scorecard);
  const owned = asObject(summary.data?.owned_performance);

  const channel = asObject(owned.channel);
  const sync = asObject(owned.latest_sync);
  const syncChannel = asObject(sync.channel);
  const channelTitle = String(channel.title ?? syncChannel.title ?? "");
  const isConnected = Boolean(channel.id || channelTitle);

  const recentRuns = asArray<RecentRun>(learning.recent_runs);
  const angles = asArray<AngleEffectiveness>(learning.angle_effectiveness);
  const winningTitles = asArray<WinningTitle>(learning.winning_titles);
  const retention = asArray<RetentionPattern>(learning.retention_pattern);

  const totalRuns = scorecard.total_runs;
  const avgOpportunity = roundOpportunity(scorecard.avg_opportunity_score);
  const avgTitle = roundTitleScore(scorecard.avg_title_score);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Dashboard"
        description="Everything saved locally from your packaging work, with each number labelled by where it came from."
        actions={
          <Button asChild>
            <Link to="/creator">
              <Sparkles aria-hidden="true" />
              Launch Creator
            </Link>
          </Button>
        }
      />

      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-muted/30 p-3">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Creator loop
          </span>
          {LOOP_STEPS.map((step, index) => (
            <span key={step.label} className="flex items-center gap-2">
              {step.to ? (
                <Link
                  to={step.to}
                  className="rounded-md px-2 py-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {index + 1}. {step.label}
                </Link>
              ) : (
                <span
                  className="px-2 py-1 text-xs font-semibold text-muted-foreground"
                  title="Publishing happens manually in YouTube Studio"
                >
                  {index + 1}. {step.label}
                </span>
              )}
              {index < LOOP_STEPS.length - 1 ? (
                <ArrowRight className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
              ) : null}
            </span>
          ))}
        </div>

        {summary.isError ? (
          <ErrorState
            message={apiErrorMessage(summary.error, "Could not load your dashboard.")}
            requestId={apiRequestId(summary.error)}
            onRetry={() => void summary.refetch()}
          />
        ) : null}

        {summary.isPending ? (
          <GridSkeleton cards={4} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Views (28 days)"
              value={isConnected ? formatNumber(owned.total_views) : "Unavailable"}
              caption={
                isConnected
                  ? "Real 28-day channel views synced from YouTube."
                  : "Connect and refresh your channel in Settings."
              }
              tone={isConnected ? "info" : "neutral"}
              toneLabel={isConnected ? "YouTube data" : "Not connected"}
            />
            <StatCard
              label="Estimated watch time"
              value={formatWatchTime(owned.estimated_watch_minutes, isConnected)}
              caption={
                isConnected
                  ? "Total estimated watch time from the 28-day sync."
                  : "Unavailable until a YouTube Analytics sync succeeds."
              }
              tone={isConnected ? "info" : "neutral"}
              toneLabel={isConnected ? "YouTube data" : "Not connected"}
            />
            <StatCard
              label="Avg opportunity score"
              value={avgOpportunity === null ? "Unavailable" : `${avgOpportunity} / 100`}
              caption={savedAnalysesCaption(totalRuns)}
              tone="warn"
              toneLabel="Heuristic"
            />
            <StatCard
              label="Avg title quality"
              value={avgTitle === null ? "Unavailable" : `${avgTitle} / 10`}
              caption="Local title-quality heuristic, not measured CTR."
              tone="warn"
              toneLabel="Heuristic"
            />
          </div>
        )}

        <QuickLaunch />

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Connected channel</CardTitle>
              <EvidenceChip tone={isConnected ? "ok" : "neutral"}>
                {isConnected ? "Connected" : "Not connected"}
              </EvidenceChip>
            </CardHeader>
            <CardContent>
              {summary.isPending ? (
                <CardSkeleton rows={2} />
              ) : isConnected ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground"
                      aria-hidden="true"
                    >
                      {channelTitle.charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {channelTitle}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        Read-only access. This tool never uploads or edits.
                      </p>
                    </div>
                  </div>
                  <dl className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Subscribers
                      </dt>
                      <dd className="numeric font-bold text-foreground">
                        {formatNumber(owned.subscribers)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Lifetime views
                      </dt>
                      <dd className="numeric font-bold text-foreground">
                        {formatNumber(owned.lifetime_views)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Linked videos
                      </dt>
                      <dd className="numeric font-bold text-foreground">
                        {formatNumber(owned.linked_videos_count ?? 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Last synced
                      </dt>
                      <dd className="text-[11px] font-semibold text-foreground">
                        {sync.synced_at ? historyDate(String(sync.synced_at)) : "Never"}
                      </dd>
                    </div>
                  </dl>
                </div>
              ) : (
                <div className="space-y-3">
                  <UnavailableNote>
                    No YouTube channel is connected, so real performance data is unavailable. The
                    packaging tools work without it.
                  </UnavailableNote>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/settings">Connect in Settings</Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Title quality by content angle</CardTitle>
              <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
            </CardHeader>
            <CardContent>
              {summary.isPending ? <CardSkeleton rows={3} /> : <AngleChart data={angles} />}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Recent packages</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/history">
                  View all
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {summary.isPending ? (
                <CardSkeleton rows={3} />
              ) : recentRuns.length ? (
                <ul className="divide-y divide-border">
                  {recentRuns.slice(0, 6).map((run) => (
                    <li
                      key={run.id}
                      className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-foreground">
                          {run.title || "Untitled package"}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {historyDate(run.created_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-4">
                        <span className="numeric text-[11px] text-muted-foreground">
                          Opp {formatNumber(run.opportunity_score)}
                        </span>
                        <span className="numeric text-[11px] text-muted-foreground">
                          Title {formatNumber(run.title_score)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <UnavailableNote>
                  No saved packages yet. Generate one in Creator and it will appear here.
                </UnavailableNote>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Retention risk spread</CardTitle>
              <EvidenceChip tone="warn">Pre-publish</EvidenceChip>
            </CardHeader>
            <CardContent>
              {summary.isPending ? (
                <CardSkeleton rows={2} />
              ) : retention.length ? (
                <ul className="space-y-2">
                  {retention.map((row) => {
                    const risk = String(row.retention_risk ?? "Unknown");
                    return (
                      <li key={risk} className="flex items-center justify-between gap-2">
                        <EvidenceChip tone={riskTone(risk)}>{risk}</EvidenceChip>
                        <span className="numeric text-xs font-bold text-foreground">
                          {formatNumber(row.count ?? 0)}
                        </span>
                      </li>
                    );
                  })}
                  <li className="pt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Counts of saved packages by their pre-publish risk assessment. This is not
                    measured audience retention.
                  </li>
                </ul>
              ) : (
                <UnavailableNote>No retention assessments recorded yet.</UnavailableNote>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Highest-scoring titles</CardTitle>
              <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
            </CardHeader>
            <CardContent>
              {summary.isPending ? (
                <CardSkeleton rows={3} />
              ) : winningTitles.length ? (
                <ul className="space-y-2">
                  {winningTitles.slice(0, 5).map((item, index) => (
                    <li
                      key={`${item.title}-${index}`}
                      className="flex items-start justify-between gap-3 rounded-md border border-border bg-muted/30 p-2.5"
                    >
                      <p className="min-w-0 text-xs text-foreground">{item.title}</p>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="numeric text-[11px] font-bold text-foreground">
                          {formatNumber(item.title_score)}/10
                        </span>
                        {item.opportunity_label ? (
                          <EvidenceChip tone="neutral">{item.opportunity_label}</EvidenceChip>
                        ) : null}
                      </div>
                    </li>
                  ))}
                  <li className="pt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Ranked by the local title-quality heuristic at generation time — not by views,
                    CTR, or any published result.
                  </li>
                </ul>
              ) : (
                <UnavailableNote>No scored titles yet.</UnavailableNote>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle>Learning confidence</CardTitle>
              <EvidenceChip tone={cohorts.data?.learning_allowed ? "ok" : "warn"}>
                {cohorts.data?.confidence_label ?? "Unavailable"}
              </EvidenceChip>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {cohorts.isPending ? (
                <CardSkeleton rows={2} />
              ) : cohorts.isError ? (
                <UnavailableNote>Learning status could not be loaded.</UnavailableNote>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Comparable videos
                      </p>
                      <p className="numeric font-bold text-foreground">
                        {formatNumber(cohorts.data?.sample_size ?? 0)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Needed
                      </p>
                      <p className="numeric font-bold text-foreground">
                        {formatNumber(cohorts.data?.next_threshold)}
                      </p>
                    </div>
                  </div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    {cohorts.data?.recommendation ??
                      "Learning status is unavailable for this window."}
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {typeof scorecard.score_trend === "string" && scorecard.score_trend ? (
          <p className="rounded-lg border border-border bg-muted/30 p-3 text-[11px] leading-relaxed text-muted-foreground">
            <strong className="text-foreground">Score trend:</strong> {scorecard.score_trend}
          </p>
        ) : null}
      </div>
    </div>
  );
}
