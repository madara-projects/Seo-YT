import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { UnavailableNote } from "@/components/common/States";
import { formatCompact, toFiniteNumber } from "@/lib/format";
import { shortDate } from "@/lib/historyFormat";
import { recentUploadsSeries } from "@/lib/channelFormat";
import type { ChannelVideo } from "@/api/systemTypes";

/** In rem, so chart text follows the interface scale like everything else. */
const CHART_TEXT = "0.6875rem";

interface Point {
  id: string;
  title: string;
  date: string;
  axis: string;
  views: number;
  likes: number | null;
  comments: number | null;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  const point = active ? payload?.[0]?.payload : undefined;
  if (!point) return null;
  return (
    <div className="max-w-60 rounded-xl border border-border bg-popover px-3 py-2.5 shadow-elevated">
      <p className="line-clamp-2 text-xs font-semibold text-popover-foreground">{point.title}</p>
      <p className="mt-0.5 text-[0.6875rem] text-muted-foreground">{point.date}</p>
      <p className="numeric mt-1.5 text-xs text-foreground">{point.views.toLocaleString()} views</p>
      <p className="numeric text-[0.6875rem] text-muted-foreground">
        {point.likes === null ? "Likes unavailable" : `${point.likes.toLocaleString()} likes`} ·{" "}
        {point.comments === null ? "comments unavailable" : `${point.comments.toLocaleString()} comments`}
      </p>
    </div>
  );
}

/**
 * Views for the latest uploads in publishing order. Each bar is a lifetime
 * count at sync time, so a newer upload has simply had less time — the
 * caption says so rather than letting the shape imply a decline.
 */
export function UploadsChart({ videos }: { videos: ChannelVideo[] }) {
  const points: Point[] = recentUploadsSeries(videos, 12)
    .filter((video) => toFiniteNumber(video.views) !== null)
    .map((video, index) => ({
      id: String(video.video_id ?? index),
      title: String(video.title ?? "Untitled upload"),
      date: shortDate(video.published_at),
      axis: video.published_at
        ? new Date(video.published_at).toLocaleDateString("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "numeric",
            month: "short",
          })
        : "—",
      views: Number(video.views),
      likes: toFiniteNumber(video.likes),
      comments: toFiniteNumber(video.comments),
    }));

  if (points.length < 2) {
    return (
      <UnavailableNote>
        {points.length === 1
          ? "Only one upload has view data so far; a chart needs at least two."
          : "No upload view counts were returned in the latest sync."}
      </UnavailableNote>
    );
  }

  return (
    <>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: -12 }} barCategoryGap="22%">
            <defs>
              <linearGradient id="uploads-bar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="var(--chart-1)" stopOpacity={1} />
                <stop offset="1" stopColor="var(--chart-1)" stopOpacity={0.45} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
            <XAxis
              dataKey="axis"
              tick={{ fill: "var(--chart-axis)", fontSize: CHART_TEXT }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(value: number) => formatCompact(value)}
              tick={{ fill: "var(--chart-axis)", fontSize: CHART_TEXT }}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.35 }} />
            <Bar dataKey="views" fill="url(#uploads-bar)" radius={[8, 8, 2, 2]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Lifetime views of your latest {points.length} uploads at the last sync, oldest on the left.
        Newer uploads have had less time to collect views, so a shorter bar is not a decline.
      </p>
    </>
  );
}
