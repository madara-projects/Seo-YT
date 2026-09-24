import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarRange,
  Clock,
  Eye,
  GitCompareArrows,
  GraduationCap,
  Link2,
  ListVideo,
  RefreshCw,
  Timer,
  UserPlus,
  Youtube,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { Delta } from "@/components/common/Delta";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Meter } from "@/components/common/Meter";
import { Panel } from "@/components/common/Panel";
import { StatCard } from "@/components/common/StatCard";
import { CardSkeleton, EmptyState, ErrorState, GridSkeleton, UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChannelSetupNeeded,
  ConnectChannelCard,
  OAuthNoticeBanner,
} from "@/components/channel/ChannelConnection";
import { PeriodComparison } from "@/components/channel/PeriodComparison";
import { UploadsChart } from "@/components/channel/UploadsChart";
import { UploadsTable } from "@/components/channel/UploadsTable";
import { useChannelStatus, useRefreshChannel } from "@/hooks/useSystem";
import { useCohortLearning, usePublishedVideos } from "@/hooks/useHistory";
import { useOAuthReturnNotice } from "@/hooks/useOAuthReturn";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { asArray, cn, formatNumber } from "@/lib/utils";
import { formatCompact, formatMinutes, formatSeconds, initialOf, relativeTime } from "@/lib/format";
import { historyDate, shortDate } from "@/lib/historyFormat";
import { hasMetrics, periodComparison, youtubeChannelUrl } from "@/lib/channelFormat";
import type { ChannelSyncData, ChannelVideo, LearningVideo } from "@/api/systemTypes";
import type { PublishedVideoLink } from "@/api/historyTypes";

/** Refresh once per app session when the stored sync is older than this. */
const STALE_AFTER_MS = 2 * 60 * 1000;
/** Sessions (one QueryClient each) that have already auto-refreshed. */
const autoRefreshed = new WeakSet<object>();

function ChannelBanner({
  data,
  syncedAt,
}: {
  data: ChannelSyncData;
  syncedAt?: string;
}) {
  const channel = data.channel ?? {};
  const title = channel.title || "YouTube channel";
  const period = data.period ?? {};

  return (
    <section className="relative overflow-hidden rounded-3xl border border-border hero-wash p-6 shadow-card sm:p-8">
      <div
        className="pointer-events-none absolute inset-0 bg-dots [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_60%)]"
        aria-hidden="true"
      />
      <div className="relative flex flex-col gap-7 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <span
            className="grid size-16 shrink-0 place-items-center rounded-full bg-brand-gradient p-[3px] shadow-[0_10px_30px_-10px_oklch(0.55_0.25_300/0.8)]"
            aria-hidden="true"
          >
            <span className="grid size-full place-items-center rounded-full bg-card font-display text-2xl font-semibold text-foreground">
              {initialOf(title)}
            </span>
          </span>
          <div className="min-w-0 space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em] text-brand">
              <Youtube className="size-3.5" aria-hidden="true" />
              Your channel
            </p>
            <h2 className="truncate font-display text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {title}
            </h2>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <RefreshCw className="size-3" aria-hidden="true" />
                Synced {relativeTime(syncedAt)}
                {syncedAt ? ` · ${historyDate(syncedAt)}` : ""}
              </span>
              {period.start && period.end ? (
                <span className="inline-flex items-center gap-1">
                  <CalendarRange className="size-3" aria-hidden="true" />
                  {shortDate(period.start)} – {shortDate(period.end)}
                </span>
              ) : null}
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-3 gap-3 sm:gap-4 lg:w-[440px]">
          {[
            ["Subscribers", channel.subscribers],
            ["Lifetime views", channel.real_total_views],
            ["Videos", channel.video_count],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-2xl border border-border bg-card/80 p-3.5 text-center backdrop-blur-sm sm:p-4"
            >
              <dd
                className="font-display text-xl font-semibold tracking-tight text-foreground sm:text-2xl"
                title={formatNumber(value)}
              >
                {formatCompact(value)}
              </dd>
              <dt className="mt-1 text-[11px] text-muted-foreground">{label}</dt>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

/** The layout that appears once connected. Shapes only — it shows no numbers. */
function ConnectedPreview() {
  const bars = [38, 62, 44, 80, 30, 55, 70, 48, 92, 58, 66, 100];
  return (
    <section className="space-y-3">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Appears after you connect
      </p>
      <div
        className="pointer-events-none select-none space-y-4 opacity-80 [mask-image:linear-gradient(to_bottom,black_35%,transparent)]"
        aria-hidden="true"
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {["Views", "Watch time", "Avg view duration", "Subscribers gained"].map((label) => (
            <div key={label} className="rounded-2xl border border-dashed border-border bg-card/60 p-5">
              <div className="size-7 rounded-lg bg-muted" />
              <p className="mt-3 text-[13px] font-medium text-muted-foreground">{label} (28 days)</p>
              <div className="mt-2 h-7 w-24 rounded-md bg-muted" />
              <div className="mt-3 h-3 w-32 rounded bg-muted" />
            </div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-5">
          <div className="rounded-2xl border border-dashed border-border bg-card/60 p-5 lg:col-span-3">
            <p className="text-[13px] font-medium text-muted-foreground">Recent uploads</p>
            <div className="mt-4 flex h-36 items-end gap-2">
              {bars.map((height, index) => (
                <span
                  key={index}
                  className="flex-1 rounded-t-md bg-linear-to-t from-muted to-brand-soft"
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
          </div>
          <div className="space-y-3 rounded-2xl border border-dashed border-border bg-card/60 p-5 lg:col-span-2">
            <p className="text-[13px] font-medium text-muted-foreground">This period vs the last</p>
            {[70, 55, 80, 45].map((width) => (
              <div key={width} className="space-y-1.5">
                <div className="h-3 rounded bg-muted" style={{ width: `${width}%` }} />
                <div className="h-1.5 rounded-full bg-muted" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function LearningPanel({ fallbackSample }: { fallbackSample?: number }) {
  const cohorts = useCohortLearning();
  const data = cohorts.data;
  const sample = typeof data?.sample_size === "number" ? data.sample_size : fallbackSample ?? 0;
  const threshold = typeof data?.next_threshold === "number" ? data.next_threshold : null;

  return (
    <Panel
      icon={GraduationCap}
      title="Learning from linked packages"
      description="Which packaging worked, once enough linked videos have matured."
      aside={
        <EvidenceChip tone={data?.learning_allowed ? "ok" : "warn"}>
          {data?.confidence_label ?? "Unavailable"}
        </EvidenceChip>
      }
    >
      {cohorts.isPending ? (
        <CardSkeleton rows={2} />
      ) : cohorts.isError ? (
        <UnavailableNote>Learning status could not be loaded.</UnavailableNote>
      ) : (
        <div className="space-y-4">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-display text-4xl font-semibold leading-none text-foreground">
                {formatNumber(sample)}
              </p>
              <p className="mt-1.5 text-xs text-muted-foreground">Comparable linked videos</p>
            </div>
            <p className="text-right text-xs text-muted-foreground">
              <span className="numeric block text-sm font-semibold text-foreground">
                {formatNumber(data?.next_threshold)}
              </span>
              needed for the next level
            </p>
          </div>
          <Meter
            value={sample}
            max={threshold ?? Math.max(sample, 1)}
            label="Comparable linked videos collected"
          />
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {data?.recommendation ?? "Learning status is unavailable for this window."}
          </p>
        </div>
      )}
    </Panel>
  );
}

function BestVideos({ videos }: { videos: LearningVideo[] }) {
  if (!videos.length) return null;
  return (
    <ul className="space-y-2">
      {videos.map((video, index) => (
        <li key={video.video_id ?? index} className="flex items-center gap-3 rounded-xl border border-border bg-elevated p-2.5">
          <VideoThumb videoId={video.video_id} title={video.title} className="w-20" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-foreground">{video.title || "Untitled"}</p>
            <p className="numeric text-xs text-muted-foreground">
              {formatNumber(video.views_per_day)} views/day · {video.snapshot_window ?? "window unknown"}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function LinkedPackages() {
  const published = usePublishedVideos();
  const links = asArray<PublishedVideoLink>(published.data?.links);

  return (
    <Panel
      icon={Link2}
      title="Linked packages"
      description="Saved packages you have tied to a published video."
      aside={
        <Button variant="ghost" size="sm" asChild>
          <Link to="/history">
            Library
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      }
    >
      {published.isPending ? (
        <CardSkeleton rows={3} />
      ) : published.isError ? (
        <UnavailableNote>Linked packages could not be loaded.</UnavailableNote>
      ) : links.length ? (
        <ul className="space-y-2">
          {links.slice(0, 6).map((link) => {
            const title =
              link.youtube_metadata?.title || link.selected_title || link.package_topic || "Saved package";
            const views = link.latest_performance?.views;
            return (
              <li key={link.id ?? link.youtube_video_id}>
                <Link
                  to={link.analysis_run_id ? `/history?run=${link.analysis_run_id}` : "/history"}
                  className="flex items-center gap-3 rounded-xl border border-border bg-elevated p-2.5 transition-colors hover:border-brand-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <VideoThumb videoId={link.youtube_video_id} title={title} className="w-20" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-foreground">{title}</p>
                    <p className="text-xs text-muted-foreground">
                      {views === null || views === undefined
                        ? "No snapshot yet"
                        : `${formatNumber(views)} views at ${link.latest_performance?.snapshot_window ?? "last snapshot"}`}
                    </p>
                  </div>
                  <EvidenceChip tone={link.ownership_verified ? "ok" : "neutral"}>
                    {link.ownership_verified ? "Verified" : "Unverified"}
                  </EvidenceChip>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <UnavailableNote>
          No package is linked to a published video yet. After publishing, use “Link video” in
          History so its performance is kept with the package.
        </UnavailableNote>
      )}
    </Panel>
  );
}

export default function ChannelPage() {
  const { notice, dismiss } = useOAuthReturnNotice();
  const status = useChannelStatus();
  const refresh = useRefreshChannel();
  const queryClient = useQueryClient();

  const data = status.data;
  const connected = Boolean(data?.connected);
  const sync = data?.latest_sync ?? null;
  const syncData = sync?.data;
  const syncedAt = sync?.synced_at;

  const onRefresh = async (silent = false) => {
    try {
      await refresh.mutateAsync();
      if (!silent) toast.success("YouTube analytics and video counts updated.");
    } catch (error) {
      toast.error(formatApiError(error, "YouTube refresh failed."));
    }
  };

  // Like the classic dashboard: bring stale numbers up to date once per session.
  useEffect(() => {
    if (!connected || autoRefreshed.has(queryClient)) return;
    const age = syncedAt ? Date.now() - new Date(syncedAt).getTime() : Infinity;
    if (!(age > STALE_AFTER_MS)) return;
    autoRefreshed.add(queryClient);
    void onRefresh(true);
    // `onRefresh` closes over the mutation, which is stable for this purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, syncedAt]);

  const videos = asArray<ChannelVideo>(syncData?.recent_videos?.rows);
  const current = syncData?.current_28_days;
  const previous = syncData?.previous_28_days;
  const comparison = periodComparison(current, previous);
  const metric = (key: string) => comparison.find((item) => item.key === key);
  const channelUrl = youtubeChannelUrl(syncData?.channel?.id ?? data?.channel?.id);
  const analyticsAvailable = hasMetrics(current);

  const actions = connected ? (
    <>
      <Button onClick={() => void onRefresh()} disabled={refresh.isPending}>
        <RefreshCw className={cn(refresh.isPending && "animate-spin")} aria-hidden="true" />
        {refresh.isPending ? "Refreshing…" : "Refresh analytics"}
      </Button>
      {channelUrl ? (
        <Button variant="outline" asChild>
          <a href={channelUrl} target="_blank" rel="noreferrer">
            Open on YouTube
            <ArrowUpRight aria-hidden="true" />
          </a>
        </Button>
      ) : null}
    </>
  ) : undefined;

  const kpis = [
    {
      key: "views",
      label: "Views",
      icon: Eye,
      value: (value: number | null) => (value === null ? "Unavailable" : value.toLocaleString()),
    },
    {
      key: "estimatedMinutesWatched",
      label: "Watch time",
      icon: Clock,
      value: (value: number | null) => formatMinutes(value),
    },
    {
      key: "averageViewDuration",
      label: "Avg view duration",
      icon: Timer,
      value: (value: number | null) => formatSeconds(value),
    },
    {
      key: "subscribersGained",
      label: "Subscribers gained",
      icon: UserPlus,
      value: (value: number | null) => (value === null ? "Unavailable" : value.toLocaleString()),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1200px] animate-fade-up">
      <PageHeader
        eyebrow="Performance"
        icon={Youtube}
        title="Channel"
        description="Real numbers from your connected YouTube channel, read-only. Nothing here edits or uploads."
        actions={actions}
      />

      <div className="space-y-5">
        <OAuthNoticeBanner notice={notice} onDismiss={dismiss} />

        {status.isPending ? (
          <div className="space-y-5">
            <Skeleton className="h-40 rounded-3xl" />
            <GridSkeleton cards={4} />
          </div>
        ) : status.isError ? (
          <ErrorState
            message={apiErrorMessage(status.error, "Could not load the channel status.")}
            requestId={apiRequestId(status.error)}
            onRetry={() => void status.refetch()}
          />
        ) : data?.configured === false ? (
          <ChannelSetupNeeded message={data.setup_message} />
        ) : !connected ? (
          <>
            <ConnectChannelCard returnTo="/next/channel" />
            <ConnectedPreview />
          </>
        ) : !syncData ? (
          <EmptyState
            icon={RefreshCw}
            title="Connected — waiting for the first sync"
            description="Your channel is connected, but no analytics have been pulled yet. Refresh to fetch current counts from YouTube."
            action={
              <Button onClick={() => void onRefresh()} disabled={refresh.isPending}>
                <RefreshCw className={cn(refresh.isPending && "animate-spin")} aria-hidden="true" />
                {refresh.isPending ? "Refreshing…" : "Refresh analytics"}
              </Button>
            }
          />
        ) : (
          <>
            <ChannelBanner data={syncData} syncedAt={syncedAt} />

            {analyticsAvailable ? (
              <section aria-label="Last 28 days" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {kpis.map((kpi) => {
                  const item = metric(kpi.key);
                  return (
                    <StatCard
                      key={kpi.key}
                      label={`${kpi.label} (28 days)`}
                      icon={kpi.icon}
                      value={kpi.value(item?.current ?? null)}
                      footer={
                        <Delta
                          value={item?.change ?? null}
                          label={item?.change === null ? "No earlier period to compare" : "vs previous 28 days"}
                        />
                      }
                      caption="YouTube Analytics, processed days only."
                      tone="info"
                      toneLabel="YouTube data"
                    />
                  );
                })}
              </section>
            ) : (
              <UnavailableNote>
                YouTube Analytics returned no totals for the last 28 days. This happens for new
                channels and for a few minutes after the Analytics API is enabled; the subscriber
                and upload counts above come from the Data API and are current.
              </UnavailableNote>
            )}

            <div className="grid gap-5 lg:grid-cols-5">
              <Panel
                className="lg:col-span-3"
                icon={BarChart3}
                title="Recent uploads"
                aside={<EvidenceChip tone="info">YouTube data</EvidenceChip>}
              >
                <UploadsChart videos={videos} />
              </Panel>
              <Panel
                className="lg:col-span-2"
                icon={GitCompareArrows}
                title="This period vs the last"
                description="Last 28 processed days against the 28 before."
              >
                {analyticsAvailable ? (
                  <PeriodComparison metrics={comparison} />
                ) : (
                  <UnavailableNote>No Analytics totals to compare yet.</UnavailableNote>
                )}
              </Panel>
            </div>

            <Panel
              icon={ListVideo}
              title="All uploads"
              description={`${videos.length.toLocaleString()} uploads in the last sync.`}
              aside={<EvidenceChip tone="info">Public counts</EvidenceChip>}
            >
              <UploadsTable videos={videos} />
            </Panel>

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-5">
                <LearningPanel fallbackSample={syncData.video_learning?.sample_size} />
                {asArray<LearningVideo>(syncData.video_learning?.best_videos).length ? (
                  <Panel icon={GraduationCap} title="Leading comparable videos" headingLevel={3}>
                    <BestVideos videos={asArray<LearningVideo>(syncData.video_learning?.best_videos)} />
                  </Panel>
                ) : null}
              </div>
              <LinkedPackages />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
