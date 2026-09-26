import { Eye, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { OptionSelect } from "@/components/common/OptionSelect";
import { SelectableItem } from "@/components/common/SelectableItem";
import { VideoThumb } from "@/components/common/VideoThumb";
import { ListBody, ListPanel, RecordList } from "@/components/research/ListPanel";
import { initialOf, relativeTime, viewsAsOf } from "@/lib/format";
import { channelCounts, outlierLabel } from "@/lib/watchlistFormat";
import { WATCH_STATE_FILTERS } from "@/schemas/watchlist";
import type { WatchChannel, WatchVideo } from "@/api/watchlistTypes";
import type { Selection } from "@/hooks/useSelection";

export type WatchTab = "videos" | "channels";

interface ListQuery<T> {
  items: T[];
  isPending: boolean;
  isFetching: boolean;
  error: unknown;
  refetch: () => void;
}

function stateNote(state: string, noun: string): string {
  if (state === "archived") return `No archived ${noun}.`;
  return state === "active"
    ? `You aren't watching any ${noun} yet. Add one above.`
    : `No ${noun} in your watchlist yet. Add one above.`;
}

export function WatchList({
  tab,
  onTabChange,
  state,
  onStateChange,
  search,
  onSearchChange,
  videos,
  channels,
  selected,
  onSelect,
}: {
  tab: WatchTab;
  onTabChange: (tab: WatchTab) => void;
  state: string;
  onStateChange: (state: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  videos: ListQuery<WatchVideo>;
  channels: ListQuery<WatchChannel>;
  selected: Selection<"video" | "channel"> | null;
  onSelect: (kind: "video" | "channel", id: number) => void;
}) {
  const refresh = () => {
    videos.refetch();
    channels.refetch();
  };

  return (
    <ListPanel
      icon={Eye}
      title="Watching"
      description="Most recently changed first."
      refreshLabel="Refresh watchlist"
      onRefresh={refresh}
      isFetching={videos.isFetching || channels.isFetching}
    >
      <Tabs value={tab} onValueChange={(value) => onTabChange(value as WatchTab)} className="px-2">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="videos">
            Videos
            <span className="numeric text-[0.6875rem] text-muted-foreground">
              {videos.isPending ? "" : videos.items.length}
            </span>
          </TabsTrigger>
          <TabsTrigger value="channels">
            Channels
            <span className="numeric text-[0.6875rem] text-muted-foreground">
              {channels.isPending ? "" : channels.items.length}
            </span>
          </TabsTrigger>
        </TabsList>

        <div className="mt-3 flex gap-2">
          {tab === "videos" ? (
            <div className="relative min-w-0 flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                type="search"
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder="Search videos"
                aria-label="Search watched videos"
                maxLength={200}
                className="pl-9"
              />
            </div>
          ) : null}
          <OptionSelect
            ariaLabel="Show watched items by state"
            value={state}
            onValueChange={onStateChange}
            options={WATCH_STATE_FILTERS}
            className={tab === "videos" ? "w-32 shrink-0" : "w-full"}
          />
        </div>

        <TabsContent value="videos" className="-mx-2 mt-3">
          <ListBody
            isPending={videos.isPending}
            error={videos.error}
            errorFallback="Watched videos are unavailable."
            onRetry={videos.refetch}
            isEmpty={!videos.items.length}
            empty={search.trim() ? "No watched video matches that search." : stateNote(state, "videos")}
          >
            <RecordList label="Watched videos">
              {videos.items.map((video) => {
                const outlier = outlierLabel(video.outlier?.status);
                const latest = video.latest_snapshot;
                return (
                  <li key={video.id}>
                    <SelectableItem
                      selected={selected?.kind === "video" && selected.id === video.id}
                      onSelect={() => onSelect("video", video.id)}
                      data-testid="watch-video"
                      className="flex items-center gap-3"
                    >
                      <VideoThumb videoId={video.video_id} className="w-20" />
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-foreground">
                          {video.title || video.video_id}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                          {video.channel_title || "Channel unavailable"}
                        </span>
                        <span className="mt-1 flex flex-wrap items-center gap-1.5">
                          <span className="numeric text-[0.6875rem] text-muted-foreground">
                            {typeof latest?.view_count === "number"
                              ? viewsAsOf(latest.view_count, latest.captured_at)
                              : "No snapshot yet"}
                          </span>
                          {video.outlier ? (
                            <EvidenceChip tone={outlier.tone}>{outlier.label}</EvidenceChip>
                          ) : null}
                          {video.state === "archived" ? <EvidenceChip tone="neutral">Archived</EvidenceChip> : null}
                        </span>
                      </span>
                    </SelectableItem>
                  </li>
                );
              })}
            </RecordList>
          </ListBody>
        </TabsContent>

        <TabsContent value="channels" className="-mx-2 mt-3">
          <ListBody
            isPending={channels.isPending}
            error={channels.error}
            errorFallback="Watched channels are unavailable."
            onRetry={channels.refetch}
            isEmpty={!channels.items.length}
            empty={stateNote(state, "channels")}
          >
            <RecordList label="Watched channels">
              {channels.items.map((channel) => (
                <li key={channel.id}>
                  <SelectableItem
                    selected={selected?.kind === "channel" && selected.id === channel.id}
                    onSelect={() => onSelect("channel", channel.id)}
                    data-testid="watch-channel"
                    className="flex items-center gap-3"
                  >
                    <span
                      className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-gradient p-0.5"
                      aria-hidden="true"
                    >
                      <span className="grid size-full place-items-center rounded-full bg-card font-display text-sm font-semibold text-foreground">
                        {initialOf(channel.title || channel.channel_id)}
                      </span>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[0.8125rem] font-medium text-foreground">
                        {channel.title || channel.channel_id}
                      </span>
                      <span className="numeric mt-0.5 block truncate text-xs text-muted-foreground">
                        {channelCounts(channel)}
                      </span>
                      <span className="mt-0.5 block text-[0.6875rem] text-muted-foreground">
                        {channel.last_researched_at
                          ? `Refreshed ${relativeTime(channel.last_researched_at)}`
                          : "Not refreshed yet"}
                        {channel.state === "archived" ? " · Archived" : ""}
                      </span>
                    </span>
                  </SelectableItem>
                </li>
              ))}
            </RecordList>
          </ListBody>
        </TabsContent>
      </Tabs>
    </ListPanel>
  );
}
