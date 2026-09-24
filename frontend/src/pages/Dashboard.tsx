import { BarChart3, Clock, Eye, Target, Type } from "lucide-react";

import { StatCard } from "@/components/common/StatCard";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Delta } from "@/components/common/Delta";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, GridSkeleton } from "@/components/common/States";
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
import { asArray, asObject, formatNumber } from "@/lib/utils";
import { toFiniteNumber } from "@/lib/format";
import {
  formatWatchTime,
  roundOpportunity,
  roundTitleScore,
  savedAnalysesCaption,
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
  const opportunityDelta = toFiniteNumber(scorecard.opportunity_delta_vs_previous_window);
  const titleDelta = toFiniteNumber(scorecard.title_score_delta_vs_previous_window);

  return (
    <div className="mx-auto w-full max-w-[1200px] space-y-6 animate-fade-up">
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
      ) : (
        <section aria-label="Key numbers" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Views (28 days)"
            icon={Eye}
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
            icon={Clock}
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
            icon={Target}
            value={avgOpportunity === null ? "Unavailable" : `${avgOpportunity} / 100`}
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
            value={avgTitle === null ? "Unavailable" : `${avgTitle} / 10`}
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

      <div className="grid gap-4 lg:grid-cols-5">
        <QuickLaunch className="lg:col-span-3" />
        <ChannelSnapshot
          className="lg:col-span-2"
          owned={owned as OwnedPerformance}
          channelTitle={channelTitle}
          isConnected={isConnected}
          syncedAt={sync.synced_at ? String(sync.synced_at) : null}
          isPending={summary.isPending}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel
          className="lg:col-span-3"
          icon={BarChart3}
          title="Title quality by content angle"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          {summary.isPending ? <CardSkeleton rows={3} /> : <AngleChart data={angles} />}
        </Panel>
        <LearningPanel
          className="lg:col-span-2"
          data={cohorts.data}
          isPending={cohorts.isPending}
          isError={cohorts.isError}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <RecentPackages
          className="lg:col-span-3"
          runs={recentRuns}
          isPending={summary.isPending}
        />
        <RetentionSpread
          className="lg:col-span-2"
          rows={retention}
          isPending={summary.isPending}
        />
      </div>

      <TopTitles
        titles={winningTitles}
        scoreTrend={
          typeof scorecard.score_trend === "string" && scorecard.score_trend
            ? scorecard.score_trend
            : undefined
        }
        isPending={summary.isPending}
      />
    </div>
  );
}
