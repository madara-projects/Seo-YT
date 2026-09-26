import { useMemo } from "react";
import { Eye } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { WatchAddPanel } from "@/components/watchlist/WatchAddPanel";
import { WatchDetail } from "@/components/watchlist/WatchDetail";
import { WatchList, type WatchTab } from "@/components/watchlist/WatchList";
import { useSelection } from "@/hooks/useSelection";
import { useUrlState, useUrlTextParam } from "@/hooks/useUrlState";
import { useWatchChannel, useWatchChannels, useWatchVideo, useWatchVideos } from "@/hooks/useWatchlist";
import { asArray } from "@/lib/utils";
import type { WatchChannel, WatchKind, WatchVideo } from "@/api/watchlistTypes";

const KINDS = ["video", "channel"] as const;

/** The state filter's URL form: absent is the default "active", and "" (every state) is "all". */
function stateFromUrl(value: string): string {
  return value === "all" ? "" : value === "archived" ? "archived" : "active";
}

function stateToUrl(state: string): string | null {
  return state === "" ? "all" : state === "archived" ? "archived" : null;
}

/**
 * Public channels and videos followed for ideas and benchmarks. The open
 * record (`?video=` or `?channel=`), the tab, the state filter and the search
 * all live in the URL, so a reload or a shared link shows the same view.
 */
export default function WatchlistPage() {
  const { selected, select, detailRef } = useSelection(KINDS);
  const url = useUrlState();
  const requestedTab = url.get("tab");
  // Without an explicit tab, the list follows the open record.
  const tab: WatchTab =
    requestedTab === "channels" || requestedTab === "videos"
      ? requestedTab
      : selected?.kind === "channel"
        ? "channels"
        : "videos";
  const state = stateFromUrl(url.get("state"));
  // The box answers every keystroke; the URL, and the query, follow once typing pauses.
  const search = useUrlTextParam("q");
  const query = search.settled;

  const channels = useWatchChannels(state);
  const videos = useWatchVideos(state, query);
  const channel = useWatchChannel(selected?.kind === "channel" ? selected.id : null);
  const video = useWatchVideo(selected?.kind === "video" ? selected.id : null);

  // Opening a record (an upload in a channel, a new add) shows its own list.
  const open = (kind: WatchKind, id: number, extra: Record<string, string | null> = {}) =>
    select(kind, id, { tab: null, ...extra });

  const channelItems = useMemo(() => asArray<WatchChannel>(channels.data?.channels), [channels.data]);
  const videoItems = useMemo(() => asArray<WatchVideo>(videos.data?.videos), [videos.data]);
  const active = selected?.kind === "channel" ? channel : video;

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Research lab"
        icon={Eye}
        title="Watchlist"
        description="Channels and videos you follow for ideas and benchmarks. Each refresh saves a dated snapshot of public numbers; nothing here touches your own channel."
      />

      <div className="space-y-5">
        <WatchAddPanel
          // Added items are always active, so an archived-only view would hide them.
          onAdded={(kind, id) => open(kind, id, state === "archived" ? { state: null } : {})}
        />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[23rem_minmax(0,1fr)]">
          <WatchList
            tab={tab}
            onTabChange={(next) => url.set({ tab: next })}
            state={state}
            onStateChange={(next) => url.set({ state: stateToUrl(next) })}
            search={search.value}
            onSearchChange={search.change}
            videos={{
              items: videoItems,
              isPending: videos.isPending,
              isFetching: videos.isFetching,
              error: videos.error,
              refetch: () => void videos.refetch(),
            }}
            channels={{
              items: channelItems,
              isPending: channels.isPending,
              isFetching: channels.isFetching,
              error: channels.error,
              refetch: () => void channels.refetch(),
            }}
            selected={selected}
            onSelect={(kind, id) => open(kind, id)}
          />
          <div ref={detailRef} className="min-w-0 scroll-mt-24">
            <WatchDetail
              kind={selected?.kind ?? null}
              channel={channel.data?.channel ?? null}
              video={video.data?.video ?? null}
              isLoading={active.isPending && selected !== null}
              error={active.error}
              onSelectVideo={(id) => open("video", id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
