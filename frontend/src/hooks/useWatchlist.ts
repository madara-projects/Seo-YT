import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  WatchChannelResponse,
  WatchChannelsResponse,
  WatchKind,
  WatchVideoResponse,
  WatchVideosResponse,
} from "@/api/watchlistTypes";

export const watchKeys = {
  all: ["watchlist"] as const,
  lists: () => [...watchKeys.all, "list"] as const,
  channels: (state: string) => [...watchKeys.lists(), "channels", state] as const,
  videos: (state: string, query: string) => [...watchKeys.lists(), "videos", state, query] as const,
  channel: (id: number) => [...watchKeys.all, "channel", id] as const,
  video: (id: number) => [...watchKeys.all, "video", id] as const,
};

export function useWatchChannels(state: string) {
  return useQuery({
    queryKey: watchKeys.channels(state),
    queryFn: () =>
      apiRequest<WatchChannelsResponse>(
        `/api/watchlist/channels${state ? `?state=${encodeURIComponent(state)}` : ""}`,
      ),
  });
}

export function useWatchVideos(state: string, query: string) {
  return useQuery({
    queryKey: watchKeys.videos(state, query),
    queryFn: () => {
      const params = new URLSearchParams();
      if (state) params.set("state", state);
      if (query) params.set("q", query);
      const search = params.toString();
      return apiRequest<WatchVideosResponse>(`/api/watchlist/videos${search ? `?${search}` : ""}`);
    },
    // Typing a search keeps the current results on screen until new ones arrive.
    placeholderData: keepPreviousData,
  });
}

export function useWatchChannel(id: number | null) {
  return useQuery({
    queryKey: watchKeys.channel(id ?? 0),
    queryFn: () => apiRequest<WatchChannelResponse>(`/api/watchlist/channels/${id}`),
    enabled: typeof id === "number" && id > 0,
  });
}

export function useWatchVideo(id: number | null) {
  return useQuery({
    queryKey: watchKeys.video(id ?? 0),
    queryFn: () => apiRequest<WatchVideoResponse>(`/api/watchlist/videos/${id}`),
    enabled: typeof id === "number" && id > 0,
  });
}

/** Every change returns the updated record: store it and refresh both lists. */
function useWatchUpdater() {
  const queryClient = useQueryClient();
  return (data: WatchChannelResponse & WatchVideoResponse) => {
    if (data.channel?.id) queryClient.setQueryData(watchKeys.channel(data.channel.id), { channel: data.channel });
    if (data.video?.id) queryClient.setQueryData(watchKeys.video(data.video.id), { video: data.video });
    // A channel refresh also saves its recent uploads as watched videos.
    void queryClient.invalidateQueries({ queryKey: watchKeys.lists() });
  };
}

/** Looks the channel up on YouTube (one quota unit); never retried. */
export function useAddWatchChannel() {
  const store = useWatchUpdater();
  return useMutation<WatchChannelResponse, unknown, { channel_id: string; notes: string }>({
    retry: false,
    mutationFn: (body) => apiRequest<WatchChannelResponse>("/api/watchlist/channels", { method: "POST", body }),
    onSuccess: store,
  });
}

/** Looks the video up on YouTube (one quota unit); never retried. */
export function useAddWatchVideo() {
  const store = useWatchUpdater();
  return useMutation<WatchVideoResponse, unknown, { video_id: string; notes: string }>({
    retry: false,
    mutationFn: (body) => apiRequest<WatchVideoResponse>("/api/watchlist/videos", { method: "POST", body }),
    onSuccess: store,
  });
}

/**
 * Captures a new dated snapshot. A channel refresh also lists its 20 most
 * recent uploads, which costs about 100 quota units; a video costs one.
 */
export function useResearchWatchItem() {
  const store = useWatchUpdater();
  return useMutation<WatchChannelResponse & WatchVideoResponse, unknown, { kind: WatchKind; id: number }>({
    retry: false,
    mutationFn: ({ kind, id }) =>
      apiRequest(`/api/watchlist/${kind}s/${id}/research`, { method: "POST" }),
    onSuccess: store,
  });
}

/** Compares a video with its channel's other watched videos. Local only: no quota. */
export function useAnalyzeOutlier() {
  const store = useWatchUpdater();
  return useMutation<WatchVideoResponse, unknown, number>({
    mutationFn: (id) =>
      apiRequest<WatchVideoResponse>(`/api/watchlist/videos/${id}/analyze-outlier`, { method: "POST" }),
    onSuccess: store,
  });
}

export function useUpdateWatchItem() {
  const store = useWatchUpdater();
  return useMutation<
    WatchChannelResponse & WatchVideoResponse,
    unknown,
    { kind: WatchKind; id: number; changes: { state?: string; notes?: string } }
  >({
    mutationFn: ({ kind, id, changes }) =>
      apiRequest(`/api/watchlist/${kind}s/${id}`, { method: "PATCH", body: changes }),
    onSuccess: store,
  });
}
