import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  WatchChannelResponse,
  WatchChannelsResponse,
  WatchKind,
  WatchVideoResponse,
  WatchVideosResponse,
} from "@/api/watchlistTypes";
import { mutationKeys, watchKeys } from "./queryKeys";

export function useWatchChannels(state: string) {
  return useQuery({
    queryKey: watchKeys.channels(state),
    queryFn: ({ signal }) =>
      apiRequest<WatchChannelsResponse>(
        `/api/watchlist/channels${state ? `?state=${encodeURIComponent(state)}` : ""}`,
        { signal },
      ),
  });
}

export function useWatchVideos(state: string, query: string) {
  return useQuery({
    queryKey: watchKeys.videos(state, query),
    queryFn: ({ signal }) => {
      const params = new URLSearchParams();
      if (state) params.set("state", state);
      if (query) params.set("q", query);
      const search = params.toString();
      return apiRequest<WatchVideosResponse>(`/api/watchlist/videos${search ? `?${search}` : ""}`, { signal });
    },
    // Typing a search keeps the current results on screen until new ones
    // arrive. Switching between active and archived doesn't: the old rows
    // would sit under the wrong filter.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[3] === state ? previous : undefined,
  });
}

export function useWatchChannel(id: number | null) {
  return useQuery({
    queryKey: watchKeys.channel(id ?? 0),
    queryFn: ({ signal }) => apiRequest<WatchChannelResponse>(`/api/watchlist/channels/${id}`, { signal }),
    enabled: typeof id === "number" && id > 0,
  });
}

export function useWatchVideo(id: number | null) {
  return useQuery({
    queryKey: watchKeys.video(id ?? 0),
    queryFn: ({ signal }) => apiRequest<WatchVideoResponse>(`/api/watchlist/videos/${id}`, { signal }),
    enabled: typeof id === "number" && id > 0,
  });
}

/** Every change returns the updated record: store it and refresh both lists. */
function useWatchUpdater() {
  const queryClient = useQueryClient();
  return (data: WatchChannelResponse & WatchVideoResponse) => {
    if (data.channel?.id) queryClient.setQueryData(watchKeys.channel(data.channel.id), { channel: data.channel });
    if (data.video?.id) queryClient.setQueryData(watchKeys.video(data.video.id), { video: data.video });
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

/*
 * The actions below are keyed by the record (`mutationKeys.recordAction`), so
 * its panel finds one still running after the creator looked at another.
 */

/**
 * Captures a new dated snapshot. A channel refresh reads the channel (1 unit),
 * one page of its uploads playlist (1 unit) and those videos' counts (1 unit),
 * so about 3 quota units; a video costs one.
 */
export function useResearchWatchItem(kind: WatchKind, id: number) {
  const store = useWatchUpdater();
  const queryClient = useQueryClient();
  return useMutation<WatchChannelResponse & WatchVideoResponse, unknown, { kind: WatchKind; id: number }>({
    mutationKey: mutationKeys.recordAction(`watch-${kind}`, id, "research"),
    retry: false,
    mutationFn: ({ kind: itemKind, id: itemId }) =>
      apiRequest(`/api/watchlist/${itemKind}s/${itemId}/research`, { method: "POST" }),
    onSuccess: (data, variables) => {
      store(data);
      // A channel refresh saves new snapshots of its uploads too, which open
      // video inspectors would otherwise keep showing from their cache.
      if (variables.kind === "channel") void queryClient.invalidateQueries({ queryKey: watchKeys.all });
    },
  });
}

/** Compares a video with its channel's other watched videos. Local only: no quota. */
export function useAnalyzeOutlier(id: number) {
  const store = useWatchUpdater();
  return useMutation<WatchVideoResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("watch-video", id, "outlier"),
    mutationFn: (videoId) =>
      apiRequest<WatchVideoResponse>(`/api/watchlist/videos/${videoId}/analyze-outlier`, { method: "POST" }),
    onSuccess: store,
  });
}

export function useUpdateWatchItem(kind: WatchKind, id: number) {
  const store = useWatchUpdater();
  return useMutation<
    WatchChannelResponse & WatchVideoResponse,
    unknown,
    { kind: WatchKind; id: number; changes: { state?: string; notes?: string } }
  >({
    mutationKey: mutationKeys.recordAction(`watch-${kind}`, id, "update"),
    mutationFn: ({ kind: itemKind, id: itemId, changes }) =>
      apiRequest(`/api/watchlist/${itemKind}s/${itemId}`, { method: "PATCH", body: changes }),
    onSuccess: store,
  });
}
