import { useState } from "react";
import {
  Archive,
  ArchiveRestore,
  ArrowUpRight,
  Binoculars,
  History,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Tv,
  Youtube,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { SectionTitle } from "@/components/common/SectionTitle";
import { SelectableItem } from "@/components/common/SelectableItem";
import { CardSkeleton, EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import {
  useAnalyzeOutlier,
  useResearchWatchItem,
  useUpdateWatchItem,
  useWatchVideos,
} from "@/hooks/useWatchlist";
import { formatCompact, formatSeconds, initialOf, relativeTime } from "@/lib/format";
import { historyDate, shortDate } from "@/lib/historyFormat";
import { asArray, formatNumber } from "@/lib/utils";
import {
  OUTLIER_MINIMUM_PEERS,
  OUTLIER_THRESHOLD,
  channelCounts,
  languageName,
  outlierLabel,
  watchFormatLabel,
  watchStateLabel,
} from "@/lib/watchlistFormat";
import type {
  WatchChannel,
  WatchChannelSnapshot,
  WatchKind,
  WatchVideo,
  WatchVideoSnapshot,
} from "@/api/watchlistTypes";

const SNAPSHOTS_SHOWN = 10;

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Inset className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-display text-xl font-semibold leading-none tracking-tight text-foreground">{value}</dd>
    </Inset>
  );
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-brand underline-offset-4 hover:underline"
    >
      {children}
      <ArrowUpRight className="size-3.5" aria-hidden="true" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

function SnapshotRows({
  count,
  rows,
}: {
  count: number;
  rows: { id: number; captured_at?: string | null; summary: string }[];
}) {
  return (
    <section className="space-y-3">
      <SectionTitle icon={History} aside={<EvidenceChip tone="info">Public observation</EvidenceChip>}>
        Dated snapshots ({count})
      </SectionTitle>
      {rows.length ? (
        <>
          <ul className="divide-y divide-border rounded-2xl border border-border">
            {rows.slice(0, SNAPSHOTS_SHOWN).map((row) => (
              <li key={row.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-3.5 py-2.5">
                <span className="text-xs text-muted-foreground">{historyDate(row.captured_at)}</span>
                <span className="numeric text-[0.8125rem] font-medium text-foreground">{row.summary}</span>
              </li>
            ))}
          </ul>
          {rows.length > SNAPSHOTS_SHOWN ? (
            <p className="text-xs text-muted-foreground">
              Showing the latest {SNAPSHOTS_SHOWN} of {rows.length}.
            </p>
          ) : null}
        </>
      ) : (
        <UnavailableNote>No snapshot yet. Refresh to capture today's public numbers.</UnavailableNote>
      )}
    </section>
  );
}

/**
 * Refresh, outlier check and archive. Keyed by record, so switching records
 * starts from a clean slate instead of showing another record's error.
 */
function WatchActions({ kind, item }: { kind: WatchKind; item: WatchChannel | WatchVideo }) {
  const research = useResearchWatchItem();
  const analyze = useAnalyzeOutlier();
  const update = useUpdateWatchItem();
  const [failure, setFailure] = useState<{ error: unknown; fallback: string } | null>(null);
  const busy = research.isPending || analyze.isPending || update.isPending;
  const archived = item.state === "archived";

  const run = async (action: () => Promise<void>, fallback: string) => {
    setFailure(null);
    try {
      await action();
    } catch (error) {
      setFailure({ error, fallback });
    }
  };

  const onRefresh = () =>
    run(async () => {
      const data = await research.mutateAsync({ kind, id: item.id });
      toast.success(
        kind === "channel"
          ? `Snapshot saved. ${data.observed_videos ?? 0} recent uploads are now in your watchlist.`
          : "Snapshot saved.",
      );
    }, "The refresh failed; no snapshot was saved.");

  const onAnalyze = () =>
    run(async () => {
      const data = await analyze.mutateAsync(item.id);
      const status = data.analysis?.status;
      toast.success(
        status === "possible_outlier"
          ? "Flagged as a possible outlier for its channel."
          : status === "observed_normal"
            ? "Within its channel's normal range."
            : "Not enough watched videos from this channel to compare yet.",
      );
    }, "The outlier check failed.");

  const onToggle = () =>
    run(async () => {
      await update.mutateAsync({ kind, id: item.id, changes: { state: archived ? "active" : "archived" } });
      toast.success(archived ? "Restored to your watchlist." : "Archived. Its snapshots are kept.");
    }, "The change could not be saved.");

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-elevated p-4" data-testid="watch-actions">
      <div className="grid gap-2 sm:flex sm:flex-wrap">
        <Button variant="outline" onClick={() => void onRefresh()} disabled={busy}>
          {research.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
          {research.isPending ? "Refreshing…" : "Refresh snapshot"}
        </Button>
        {kind === "video" ? (
          <Button variant="outline" onClick={() => void onAnalyze()} disabled={busy}>
            {analyze.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Zap aria-hidden="true" />}
            {analyze.isPending ? "Checking…" : (item as WatchVideo).outlier ? "Check again" : "Run outlier check"}
          </Button>
        ) : null}
        <Button variant="ghost" onClick={() => void onToggle()} disabled={busy}>
          {archived ? <ArchiveRestore aria-hidden="true" /> : <Archive aria-hidden="true" />}
          {archived ? "Restore" : "Archive"}
        </Button>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        {kind === "channel"
          ? "Refreshing reads the channel's public numbers and its 20 most recent uploads, which costs about 100 YouTube quota units."
          : "Refreshing reads the video's public counts (one YouTube quota unit). The outlier check runs locally and is free."}
      </p>
      {failure ? (
        <ErrorState message={apiErrorMessage(failure.error, failure.fallback)} requestId={apiRequestId(failure.error)} />
      ) : null}
    </div>
  );
}

function Notes({ notes }: { notes?: string | null }) {
  return notes ? (
    <p className="whitespace-pre-line break-words text-sm leading-relaxed text-foreground">{notes}</p>
  ) : (
    <p className="text-sm text-muted-foreground">No notes.</p>
  );
}

function VideoInspector({ video }: { video: WatchVideo }) {
  const snapshots = asArray<WatchVideoSnapshot>(video.snapshots);
  const latest = video.latest_snapshot ?? snapshots[0] ?? null;
  const outlier = video.outlier ?? null;
  const outlierInfo = outlierLabel(outlier?.status);
  const state = watchStateLabel(video.state);

  return (
    <Panel
      data-testid="watch-detail"
      icon={Youtube}
      title={<span className="text-lg sm:text-xl">{video.title || video.video_id}</span>}
      description={`${video.channel_title || "Channel unavailable"} · published ${shortDate(video.published_at)}`}
      aside={<EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>}
    >
      <div className="space-y-6">
        <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
          <VideoThumb videoId={video.video_id} title={video.title ?? undefined} className="w-full" />
          <div className="space-y-2">
            <dl className="grid grid-cols-3 gap-2">
              <Stat label="Views" value={formatCompact(latest?.view_count)} />
              <Stat label="Likes" value={formatCompact(latest?.like_count)} />
              <Stat label="Comments" value={formatCompact(latest?.comment_count)} />
            </dl>
            <p className="text-xs text-muted-foreground">
              {latest
                ? `Public counts captured ${historyDate(latest.captured_at)}.`
                : "No snapshot yet. Refresh to capture its public counts."}
            </p>
          </div>
        </div>

        <Notes notes={video.notes} />

        <dl className="grid grid-cols-2 gap-4 rounded-2xl border border-border bg-elevated p-4 md:grid-cols-3">
          <Field label="Video">
            <ExternalLink href={`https://www.youtube.com/watch?v=${encodeURIComponent(video.video_id)}`}>
              <span className="numeric">{video.video_id}</span>
            </ExternalLink>
          </Field>
          <Field label="Format">{watchFormatLabel(video.format)}</Field>
          <Field label="Language">{languageName(video.language)}</Field>
          <Field label="Duration">{formatSeconds(video.duration_seconds)}</Field>
          <Field label="Published">{historyDate(video.published_at)}</Field>
          <Field label="Last refreshed">
            {video.last_researched_at ? relativeTime(video.last_researched_at) : "Not refreshed yet"}
          </Field>
        </dl>

        <section className="space-y-3">
          <SectionTitle icon={Zap} aside={outlier ? <EvidenceChip tone="warn">Local heuristic</EvidenceChip> : null}>
            Outlier check
          </SectionTitle>
          <Inset className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <EvidenceChip tone={outlierInfo.tone}>{outlierInfo.label}</EvidenceChip>
              {outlier?.analyzed_at ? (
                <span className="text-xs text-muted-foreground">Checked {historyDate(outlier.analyzed_at)}</span>
              ) : null}
            </div>
            {outlier && typeof outlier.relative_multiplier === "number" ? (
              <dl className="grid grid-cols-3 gap-2">
                <Stat label="Multiplier" value={`${outlier.relative_multiplier.toFixed(1)}×`} />
                <Stat label="Peer median" value={formatCompact(outlier.baseline_median_views)} />
                <Stat label="Peers compared" value={formatNumber(outlier.sample_size)} />
              </dl>
            ) : null}
            <p className="text-sm leading-relaxed text-foreground">
              {outlier?.explanation || "Not checked yet."}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              The check compares this video's latest views with the median of at least {OUTLIER_MINIMUM_PEERS} other
              watched videos from the same channel, and flags {OUTLIER_THRESHOLD}× or more. It shows unusual reach,
              not why it happened.
            </p>
          </Inset>
        </section>

        <SnapshotRows
          count={snapshots.length}
          rows={snapshots.map((snapshot) => ({
            id: snapshot.id,
            captured_at: snapshot.captured_at,
            summary: `${formatNumber(snapshot.view_count)} views · ${formatNumber(snapshot.like_count)} likes · ${formatNumber(snapshot.comment_count)} comments`,
          }))}
        />

        <WatchActions key={`video:${video.id}`} kind="video" item={video} />
        <Footnote />
      </div>
    </Panel>
  );
}

function ChannelInspector({
  channel,
  onSelectVideo,
}: {
  channel: WatchChannel;
  onSelectVideo: (id: number) => void;
}) {
  const snapshots = asArray<WatchChannelSnapshot>(channel.snapshots);
  const latest = snapshots[0] ?? null;
  const state = watchStateLabel(channel.state);
  const everything = useWatchVideos("", "");
  const uploads = asArray<WatchVideo>(everything.data?.videos).filter(
    (video) => video.watchlist_channel_id === channel.id,
  );

  return (
    <Panel
      data-testid="watch-detail"
      icon={Tv}
      title={<span className="text-lg sm:text-xl">{channel.title || channel.channel_id}</span>}
      description={`Public channel · added ${shortDate(channel.created_at)}`}
      aside={<EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>}
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <span className="grid size-16 shrink-0 place-items-center rounded-full bg-brand-gradient p-0.75" aria-hidden="true">
            <span className="grid size-full place-items-center rounded-full bg-card font-display text-2xl font-semibold text-foreground">
              {initialOf(channel.title || channel.channel_id)}
            </span>
          </span>
          <dl className="grid flex-1 grid-cols-3 gap-2">
            <Stat label="Subscribers" value={formatCompact(channel.subscriber_count)} />
            <Stat label="Videos" value={formatCompact(channel.video_count)} />
            <Stat label="Total views" value={formatCompact(latest?.view_count)} />
          </dl>
        </div>
        <p className="-mt-3 text-xs text-muted-foreground">
          {latest
            ? `Latest snapshot ${historyDate(latest.captured_at)}.`
            : `${channelCounts(channel)} when added. Refresh to capture a dated snapshot.`}
        </p>

        <Notes notes={channel.notes} />

        <dl className="grid grid-cols-2 gap-4 rounded-2xl border border-border bg-elevated p-4 md:grid-cols-3">
          <Field label="Channel" className="col-span-2 md:col-span-1">
            <ExternalLink href={`https://www.youtube.com/channel/${encodeURIComponent(channel.channel_id)}`}>
              <span className="numeric break-all">{channel.channel_id}</span>
            </ExternalLink>
          </Field>
          <Field label="Added">{historyDate(channel.created_at)}</Field>
          <Field label="Last refreshed">
            {channel.last_researched_at ? relativeTime(channel.last_researched_at) : "Not refreshed yet"}
          </Field>
        </dl>

        <section className="space-y-3">
          <SectionTitle icon={Youtube}>Watched uploads ({uploads.length})</SectionTitle>
          {uploads.length ? (
            <ul className="grid gap-1 sm:grid-cols-2">
              {uploads.slice(0, 6).map((video) => (
                <li key={video.id}>
                  <SelectableItem selected={false} onSelect={() => onSelectVideo(video.id)} className="flex items-center gap-3 p-2">
                    <VideoThumb videoId={video.video_id} title={video.title ?? undefined} className="w-20" />
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-xs font-medium leading-snug text-foreground">
                        {video.title || video.video_id}
                      </span>
                      <span className="numeric mt-0.5 block text-[0.6875rem] text-muted-foreground">
                        {typeof video.latest_snapshot?.view_count === "number"
                          ? `${formatCompact(video.latest_snapshot.view_count)} views`
                          : "No snapshot yet"}
                      </span>
                    </span>
                  </SelectableItem>
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>
              Refresh this channel to add its 20 most recent uploads to your watchlist. They become the peers its
              videos are compared with in outlier checks.
            </UnavailableNote>
          )}
          {uploads.length > 6 ? (
            <p className="text-xs text-muted-foreground">
              Showing 6 of {uploads.length}; the rest are in the Videos list.
            </p>
          ) : null}
        </section>

        <SnapshotRows
          count={snapshots.length}
          rows={snapshots.map((snapshot) => ({
            id: snapshot.id,
            captured_at: snapshot.captured_at,
            summary: `${formatNumber(snapshot.subscriber_count)} subscribers · ${formatNumber(snapshot.video_count)} videos · ${formatNumber(snapshot.view_count)} views`,
          }))}
        />

        <WatchActions key={`channel:${channel.id}`} kind="channel" item={channel} />
        <Footnote />
      </div>
    </Panel>
  );
}

function Footnote() {
  return (
    <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
      <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      Public observations and local heuristics don't establish why a video performed, and don't predict how
      yours will.
    </p>
  );
}

export function WatchDetail({
  kind,
  channel,
  video,
  isLoading,
  error,
  onSelectVideo,
}: {
  kind: WatchKind | null;
  channel: WatchChannel | null;
  video: WatchVideo | null;
  isLoading: boolean;
  error: unknown;
  onSelectVideo: (id: number) => void;
}) {
  if (!kind) {
    return (
      <EmptyState
        icon={Binoculars}
        title="Choose a channel or video"
        description="You'll see its dated public snapshots, how a video compares with its channel's other uploads, and your notes."
        className="h-full min-h-80"
      />
    );
  }
  const item = kind === "channel" ? channel : video;
  if (isLoading && !item) {
    return (
      <Card className="p-6">
        <CardSkeleton rows={8} />
      </Card>
    );
  }
  if (error && !item) {
    return (
      <ErrorState
        message={apiErrorMessage(error, `This watched ${kind} is unavailable.`)}
        requestId={apiRequestId(error)}
      />
    );
  }
  if (kind === "channel" && channel) return <ChannelInspector channel={channel} onSelectVideo={onSelectVideo} />;
  if (kind === "video" && video) return <VideoInspector video={video} />;
  return null;
}
