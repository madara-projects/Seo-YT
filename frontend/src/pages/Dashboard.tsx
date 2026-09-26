import { BarChart3, Clock, Eye, Target, Type } from "lucide-react";

import { StatCard } from "@/components/common/StatCard";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Delta } from "@/components/common/Delta";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, GridSkeleton, UnavailableNote } from "@/components/common/States";
import { AngleChart } from "@/components/dashboard/AngleChart";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import {
  ChannelSnapshot,
  LearningPanel,
  RecentPackages,
  RetentionSpread,
  TopTitles,
} from "@/components/dashboard/DashboardSections";
import { QuickLaunch } from "@/components/dashboard/QuickLaunch";
import { useCohortLearning, useHistorySummary } from "@/hooks/useHistory";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, formatNumber, UNAVAILABLE } from "@/lib/utils";
import { formatMinutes, relativeTime, toFiniteNumber } from "@/lib/format";
import {
  linkedWatchCaption,
  opportunityText,
  savedAnalysesCaption,
  titleScoreText,
  watchTimeSource,
} from "@/lib/dashboardFormat";
import type {
  AngleEffectiveness,
  OwnedPerformance,
  RecentRun,
  RetentionPattern,
  WinningTitle,
} from "@/api/historyTypes";

export default function DashboardPage() {
  const summary = useHistorySummary();
  const cohorts = useCohortLearning();
  // A failed summary (a 503 or 429) says nothing about the channel or the
  // library, so nothing below may read its absence as "not connected" or "none
  // yet". A failed refetch keeps the last good summary, which is still shown.
  const failed = summary.isError && !summary.data;

  const learning = asObject(summary.data?.learning);
  const scorecard = asObject(summary.data?.scorecard);
  const owned = asObject(summary.data?.owned_performance) as OwnedPerformance;

  // `channel` is present exactly when a channel is connected, even while its
  // title is still unknown; the last sync's title says nothing about now.
  const isConnected = Boolean(owned.channel);
  const channelTitle = String(owned.channel?.title || "YouTube channel");
  const sync = owned.latest_sync ?? null;
  const syncedAt = sync?.synced_at ?? null;
  const analyticsFailed = asArray<string>(sync?.partial_failures).includes("analytics");
  // Only YouTube Analytics' own 28-day figure is shown as one, never a sum of lifetime views.
  const views28 = isConnected ? toFiniteNumber(sync?.current_28_days?.views) : null;
  const watchSource = watchTimeSource(owned);
  const watchMinutes =
    watchSource === "channel" ? sync?.current_28_days?.estimatedMinutesWatched : owned.estimated_watch_minutes;

  const recentRuns = asArray<RecentRun>(learning.recent_runs);
  const angles = asArray<AngleEffectiveness>(learning.angle_effectiveness);
  const winningTitles = asArray<WinningTitle>(learning.winning_titles);
  const retention = asArray<RetentionPattern>(learning.retention_pattern);

  const totalRuns = scorecard.total_runs;
  const opportunityDelta = toFiniteNumber(scorecard.opportunity_delta_vs_previous_window);
  const titleDelta = toFiniteNumber(scorecard.title_score_delta_vs_previous_window);

  return (
    <div className="mx-auto w-full max-w-page space-y-5 animate-fade-up">
      <DashboardHero totalRuns={typeof totalRuns === "number" ? totalRuns : undefined} />

      {summary.isError ? (
        <ErrorState
          message={apiErrorMessage(summary.error, "Could not load your dashboard.")}
          requestId={apiRequestId(summary.error)}
          onRetry={() => void summary.refetch()}
        />
      ) : null}

      {summary.isPending ? (
        <GridSkeleton cards={4} />
      ) : failed ? null : (
        <section aria-label="Key numbers" className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Views (28 days)"
            icon={Eye}
            value={views28 === null ? UNAVAILABLE : formatNumber(views28)}
            caption={
              !isConnected
                ? "Connect and refresh your channel in Settings."
                : views28 !== null
                  ? `Real 28-day channel views from YouTube Analytics, synced ${relativeTime(syncedAt)}.`
                  : analyticsFailed
                    ? "YouTube Analytics couldn't be read during the last sync. Refresh on the Channel page."
                    : syncedAt
                      ? "YouTube Analytics has no 28-day figure for this channel yet."
                      : "Not synced yet. Refresh on the Channel page."
            }
            tone={views28 !== null ? "info" : "neutral"}
            toneLabel={!isConnected ? "Not connected" : views28 !== null ? "YouTube data" : "Unavailable"}
          />
          <StatCard
            label="Estimated watch time"
            icon={Clock}
            value={watchSource === "none" ? UNAVAILABLE : formatMinutes(watchMinutes)}
            caption={
              watchSource === "channel"
                ? `Total estimated watch time from the 28-day sync, ${relativeTime(syncedAt)}.`
                : watchSource === "linked"
                  ? linkedWatchCaption(owned)
                  : "Unavailable until a YouTube Analytics sync succeeds."
            }
            tone={watchSource === "none" ? "neutral" : "info"}
            toneLabel={
              watchSource === "channel"
                ? "YouTube data"
                : watchSource === "linked"
                  ? "Linked videos"
                  : isConnected
                    ? "Unavailable"
                    : "Not connected"
            }
          />
          <StatCard
            label="Avg opportunity score"
            icon={Target}
            value={opportunityText(scorecard.avg_opportunity_score)}
            footer={
              opportunityDelta !== null ? (
                <Delta value={opportunityDelta} unit="points" label="vs previous window" />
              ) : undefined
            }
            caption={savedAnalysesCaption(totalRuns)}
            tone="warn"
            toneLabel="Heuristic"
          />
          <StatCard
            label="Avg title quality"
            icon={Type}
            value={titleScoreText(scorecard.avg_title_score)}
            footer={
              titleDelta !== null ? (
                <Delta value={titleDelta} unit="points" label="vs previous window" />
              ) : undefined
            }
            caption="Local title-quality heuristic, not measured CTR."
            tone="warn"
            toneLabel="Heuristic"
          />
        </section>
      )}

      {/*
        Three rows of cards on one 1.25rem spacing scale. Up to 2xl a 3:2 split;
        from 2xl three equal columns, with the two short panels (learning and
        retention) side by side under one column pair instead of stacked.
      */}
      <div className="grid gap-5 lg:grid-cols-5 2xl:grid-cols-3">
        <QuickLaunch className="lg:col-span-3 2xl:col-span-2" />
        <ChannelSnapshot
          className="lg:col-span-2 2xl:col-span-1"
          owned={owned}
          channelTitle={channelTitle}
          isConnected={isConnected}
          syncedAt={syncedAt}
          isPending={summary.isPending}
          isError={failed}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-5 2xl:grid-cols-3">
        <Panel
          className="lg:col-span-3 2xl:col-span-1"
          icon={BarChart3}
          title="Title quality by content angle"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          {summary.isPending ? (
            <CardSkeleton rows={3} />
          ) : failed ? (
            <UnavailableNote>Title quality by angle is unavailable right now.</UnavailableNote>
          ) : (
            <AngleChart data={angles} />
          )}
        </Panel>
        {/* Stacked beside the chart up to 2xl; side by side across two columns from 2xl. */}
        <div className="grid gap-5 lg:col-span-2 2xl:grid-cols-2">
          <LearningPanel
            title="Learning confidence"
            description="Learning from results starts only once enough comparable videos have matured."
            sampleLabel="Comparable videos"
            data={cohorts.data}
            isPending={cohorts.isPending}
            isError={cohorts.isError}
          />
          <RetentionSpread rows={retention} isPending={summary.isPending} isError={failed} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-5 2xl:grid-cols-3">
        <RecentPackages
          className="lg:col-span-3 2xl:col-span-2"
          runs={recentRuns}
          isPending={summary.isPending}
          isError={failed}
        />
        <TopTitles
          className="lg:col-span-2 2xl:col-span-1"
          titles={winningTitles}
          scoreTrend={
            typeof scorecard.score_trend === "string" && scorecard.score_trend
              ? scorecard.score_trend
              : undefined
          }
          isPending={summary.isPending}
          isError={failed}
        />
      </div>
    </div>
  );
}
