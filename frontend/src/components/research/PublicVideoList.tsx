import { UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { formatNumber } from "@/lib/utils";
import { shortDate } from "@/lib/historyFormat";
import type { PublicVideoResult } from "@/api/researchTypes";

/**
 * Public YouTube videos captured in a research snapshot, with the views they
 * had at capture time — never a live or predicted count.
 */
export function PublicVideoList({
  videos,
  limit = 8,
  empty,
}: {
  videos: PublicVideoResult[];
  limit?: number;
  empty: string;
}) {
  if (!videos.length) return <UnavailableNote>{empty}</UnavailableNote>;

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-border rounded-2xl border border-border">
        {videos.slice(0, limit).map((video, index) => (
          <li
            key={video.video_id ?? index}
            // On phones the count sits under the title so the title keeps its
            // room; wider screens give the count a column of its own.
            className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-0.5 p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
          >
            <VideoThumb videoId={video.video_id} className="row-span-2 w-20 sm:row-span-1 sm:w-28" />
            <div className="min-w-0 self-end sm:self-center">
              <p className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-foreground">
                {video.title || "Untitled video"}
              </p>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {video.channel_title || "Channel unavailable"} · {shortDate(video.published_at)}
              </p>
            </div>
            <p className="self-start text-xs text-muted-foreground sm:self-center sm:text-right sm:text-[0.6875rem]">
              <span className="numeric font-semibold text-foreground sm:block sm:text-[0.8125rem]">
                {formatNumber(video.view_count)}
              </span>{" "}
              views at capture
            </p>
          </li>
        ))}
      </ul>
      {videos.length > limit ? (
        <p className="text-xs text-muted-foreground">
          Showing {limit} of {videos.length} results.
        </p>
      ) : null}
    </div>
  );
}
