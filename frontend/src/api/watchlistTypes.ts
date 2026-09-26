/**
 * The public watchlist (`/api/watchlist/*`). Shapes follow
 * `IntelligenceStore.channel`, `video` and `analyze_outlier`.
 */

export type WatchState = "active" | "archived";
export type WatchKind = "channel" | "video";

export interface WatchChannelSnapshot {
  id: number;
  captured_at?: string | null;
  subscriber_count?: number | null;
  video_count?: number | null;
  view_count?: number | null;
  source?: string | null;
}

export interface WatchChannel {
  id: number;
  channel_id: string;
  title?: string | null;
  thumbnail_url?: string | null;
  subscriber_count?: number | null;
  video_count?: number | null;
  notes?: string | null;
  state: WatchState | string;
  source?: string | null;
  last_researched_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  snapshots?: WatchChannelSnapshot[];
}

export interface WatchVideoSnapshot {
  id: number;
  captured_at?: string | null;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  duration_seconds?: number | null;
  source?: string | null;
}

export type OutlierStatus = "possible_outlier" | "observed_normal" | "insufficient_evidence";

export interface WatchOutlier {
  id?: number;
  analyzed_at?: string | null;
  status?: OutlierStatus | string | null;
  observed_views?: number | null;
  /** The median of peer views, each scaled to this video's age. */
  baseline_median_views?: number | null;
  relative_multiplier?: number | null;
  /** Peers matched at a similar age only. */
  sample_size?: number | null;
  /** How peers were measured, e.g. "peer_snapshot_nearest_same_age". */
  observation_window?: string | null;
  explanation?: string | null;
  provenance?: string | null;
  signals?: { engagement_ratio?: number | null; limitation?: string | null } | null;
}

export interface WatchVideo {
  id: number;
  video_id: string;
  watchlist_channel_id?: number | null;
  channel_id?: string | null;
  channel_title?: string | null;
  title?: string | null;
  published_at?: string | null;
  /** Null for a live or upcoming video (P0D). */
  duration_seconds?: number | null;
  language?: string | null;
  /** From the duration: "youtube_shorts" up to 180 s, "long_form", or "unknown". */
  format?: string | null;
  notes?: string | null;
  state: WatchState | string;
  source?: string | null;
  last_researched_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  /** Every snapshot from the detail endpoint; the list holds only the latest. */
  snapshots?: WatchVideoSnapshot[];
  latest_snapshot?: WatchVideoSnapshot | null;
  outlier?: WatchOutlier | null;
}

export interface WatchChannelsResponse {
  channels?: WatchChannel[];
  total?: number;
}

export interface WatchVideosResponse {
  videos?: WatchVideo[];
  total?: number;
}

export interface WatchChannelResponse {
  status?: string;
  channel?: WatchChannel;
  /** Recent uploads saved to the watchlist by a channel refresh. */
  observed_videos?: number;
}

export interface WatchVideoResponse {
  status?: string;
  video?: WatchVideo;
  analysis?: WatchOutlier;
}
