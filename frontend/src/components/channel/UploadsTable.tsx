import { useState } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { formatNumber } from "@/lib/utils";
import { engagementRate, toFiniteNumber } from "@/lib/format";
import { shortDate } from "@/lib/historyFormat";
import { sortVideos, youtubeWatchUrl, type VideoSort } from "@/lib/channelFormat";
import type { ChannelVideo } from "@/api/systemTypes";

const PAGE = 8;

/**
 * Every upload from the last sync with its public counts. Engagement is
 * derived here — (likes + comments) per 100 views — and labelled as such.
 */
export function UploadsTable({ videos }: { videos: ChannelVideo[] }) {
  const [sort, setSort] = useState<VideoSort>("newest");
  const [expanded, setExpanded] = useState(false);

  if (!videos.length) {
    return <UnavailableNote>No uploads were returned in the latest sync.</UnavailableNote>;
  }

  const sorted = sortVideos(videos, sort);
  const shown = expanded ? sorted : sorted.slice(0, PAGE);
  const maxViews = Math.max(1, ...videos.map((video) => toFiniteNumber(video.views) ?? 0));

  return (
    <div className="space-y-4">
      <Tabs value={sort} onValueChange={(value) => setSort(value as VideoSort)}>
        <TabsList aria-label="Sort uploads">
          <TabsTrigger value="newest">Newest</TabsTrigger>
          <TabsTrigger value="views">Most viewed</TabsTrigger>
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="-mx-5 overflow-x-auto sm:-mx-6">
        <table className="w-full min-w-[640px] text-left">
          <thead>
            <tr className="border-y border-border bg-muted/40 text-[11px] font-medium text-muted-foreground">
              <th scope="col" className="px-5 py-2.5 font-medium sm:px-6">Upload</th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">Views</th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">Likes</th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">Comments</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium sm:px-6">
                <abbr title="Likes plus comments per 100 views" className="no-underline">
                  Engagement
                </abbr>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {shown.map((video, index) => {
              const url = youtubeWatchUrl(video.video_id);
              const views = toFiniteNumber(video.views);
              const rate = engagementRate(video.likes, video.comments, video.views);
              return (
                <tr key={video.video_id ?? index} className="transition-colors hover:bg-accent/40">
                  <td className="px-5 py-3 sm:px-6">
                    <div className="flex items-center gap-3">
                      <VideoThumb videoId={video.video_id} title={video.title} className="w-24" />
                      <div className="min-w-0">
                        {url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="group line-clamp-2 text-[13px] font-medium leading-snug text-foreground hover:text-brand"
                          >
                            {video.title || "Untitled upload"}
                            <ArrowUpRight className="ml-0.5 inline size-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
                          </a>
                        ) : (
                          <p className="line-clamp-2 text-[13px] font-medium leading-snug text-foreground">
                            {video.title || "Untitled upload"}
                          </p>
                        )}
                        <p className="mt-0.5 text-xs text-muted-foreground">{shortDate(video.published_at)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <p className="numeric text-[13px] font-semibold text-foreground">{formatNumber(video.views)}</p>
                    <div className="ml-auto mt-1.5 h-1 w-16 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                      <div
                        className="h-full rounded-full bg-brand-gradient"
                        style={{ width: `${((views ?? 0) / maxViews) * 100}%` }}
                      />
                    </div>
                  </td>
                  <td className="numeric px-3 py-3 text-right text-[13px] text-muted-foreground">
                    {formatNumber(video.likes)}
                  </td>
                  <td className="numeric px-3 py-3 text-right text-[13px] text-muted-foreground">
                    {formatNumber(video.comments)}
                  </td>
                  <td className="numeric px-5 py-3 text-right text-[13px] text-foreground sm:px-6">
                    {rate === null ? "—" : rate.toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Public counts from the YouTube Data API at the last sync. Engagement = likes plus comments
          per 100 views, calculated here.
        </p>
        {sorted.length > PAGE ? (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((open) => !open)}>
            {expanded ? "Show fewer" : `Show all ${sorted.length}`}
            <ChevronDown className={expanded ? "rotate-180" : undefined} aria-hidden="true" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
