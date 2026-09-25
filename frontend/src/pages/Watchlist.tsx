import { useEffect, useMemo, useState } from "react";
import { Eye } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { WatchAddPanel } from "@/components/watchlist/WatchAddPanel";
import { WatchDetail } from "@/components/watchlist/WatchDetail";
import { WatchList, type WatchTab } from "@/components/watchlist/WatchList";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useSelection } from "@/hooks/useSelection";
import { useWatchChannel, useWatchChannels, useWatchVideo, useWatchVideos } from "@/hooks/useWatchlist";
import { asArray } from "@/lib/utils";
import type { WatchChannel, WatchVideo } from "@/api/watchlistTypes";

const KINDS = ["video", "channel"] as const;

/**
 * Public channels and videos followed for ideas and benchmarks. The open
 * record lives in the URL (`?video=` or `?channel=`), so it can be linked to.
 */
export default function WatchlistPage() {
  const { selected, select, detailRef } = useSelection(KINDS);
  const [tab, setTab] = useState<WatchTab>(selected?.kind === "channel" ? "channels" : "videos");
  const [state, setState] = useState("active");
  const [search, setSearch] = useState("");
  const query = useDebouncedValue(search.trim(), 300);

  const channels = useWatchChannels(state);
  const videos = useWatchVideos(state, query);
  const channel = useWatchChannel(selected?.kind === "channel" ? selected.id : null);
  const video = useWatchVideo(selected?.kind === "video" ? selected.id : null);

  // Opening a record from elsewhere (an upload in a channel, a new add) shows its list.
  const selectedKind = selected?.kind;
  useEffect(() => {
    if (selectedKind) setTab(selectedKind === "channel" ? "channels" : "videos");
  }, [selectedKind]);

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
          onAdded={(kind, id) => {
            // Show the new record: added items are always active.
            if (state === "archived") setState("active");
            select(kind, id);
          }}
        />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[23rem_minmax(0,1fr)]">
          <WatchList
            tab={tab}
            onTabChange={setTab}
            state={state}
            onStateChange={setState}
            search={search}
            onSearchChange={setSearch}
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
            onSelect={select}
          />
          <div ref={detailRef} className="min-w-0 scroll-mt-24">
            <WatchDetail
              kind={selected?.kind ?? null}
              channel={channel.data?.channel ?? null}
              video={video.data?.video ?? null}
              isLoading={active.isPending && selected !== null}
              error={active.error}
              onSelectVideo={(id) => select("video", id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
