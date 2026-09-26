import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  ChannelStatus,
  ChannelSyncData,
  CloudSyncRunResult,
  CloudSyncStatus,
  HealthStatus,
  LiveDiagnostics,
  SettingsStatus,
} from "@/api/systemTypes";
import { historyKeys, mutationKeys, systemKeys } from "./queryKeys";

/**
 * Settings, sync and channel data access.
 *
 * The channel status is read by the sidebar, Settings, the Channel page and
 * the research pages that need a connected channel, so it lives under one key
 * and is fetched once. (The Dashboard reads its channel from the history
 * summary instead.)
 */

/** Scheduled times on Settings are re-read this often, so "next check" never goes stale. */
const STATUS_POLL_MS = 60_000;

export function useHealth() {
  return useQuery({
    queryKey: systemKeys.health,
    queryFn: ({ signal }) => apiRequest<HealthStatus>("/health", { signal }),
    // An at-a-glance reassurance, not a monitor; the backend rate-limits per path.
    refetchInterval: 60_000,
    retry: 1,
  });
}

export function useSettingsStatus() {
  return useQuery({
    queryKey: systemKeys.settings,
    queryFn: ({ signal }) => apiRequest<SettingsStatus>("/api/settings/status", { signal }),
    refetchInterval: STATUS_POLL_MS,
  });
}

export function useCloudSyncStatus() {
  return useQuery({
    queryKey: systemKeys.cloudSync,
    queryFn: ({ signal }) => apiRequest<CloudSyncStatus>("/api/cloud-sync/status", { signal }),
    refetchInterval: STATUS_POLL_MS,
  });
}

export function useRunCloudSync() {
  const queryClient = useQueryClient();
  return useMutation<CloudSyncRunResult, unknown, void>({
    mutationFn: () => apiRequest<CloudSyncRunResult>("/api/cloud-sync/run", { method: "POST" }),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: systemKeys.cloudSync });
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
      // A pull can add or remove saved packages.
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}

/**
 * Runs `/diagnostics`, which proves a YouTube key works with one
 * `i18nRegions` call (1 quota unit). It is a mutation rather than a query so
 * it only ever runs when asked, and a POST so the server's cross-site guard and
 * costly-request budget apply.
 */
export function useLiveDiagnostics() {
  return useMutation<LiveDiagnostics, unknown, void>({
    mutationFn: () => apiRequest<LiveDiagnostics>("/diagnostics", { method: "POST" }),
  });
}

function fetchChannelStatus(signal?: AbortSignal) {
  return apiRequest<ChannelStatus>("/youtube/channel/status", { signal });
}

export function useChannelStatus() {
  return useQuery({
    queryKey: systemKeys.channel,
    queryFn: ({ signal }) => fetchChannelStatus(signal),
  });
}

/** The channel status as the server reports it now, not as cached. */
export function fetchFreshChannelStatus(queryClient: QueryClient) {
  return queryClient.fetchQuery({
    queryKey: systemKeys.channel,
    queryFn: ({ signal }) => fetchChannelStatus(signal),
    staleTime: 0,
  });
}

function invalidateChannelViews(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: systemKeys.channel });
  void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
  // The Dashboard's owned-performance numbers come from the history summary.
  void queryClient.invalidateQueries({ queryKey: historyKeys.all });
}

/**
 * Pulls fresh numbers from YouTube with the stored read-only token. Retrying
 * silently would spend quota twice, so failures surface instead. Settings and
 * Channel share `mutationKeys.channelRefresh`, so either can see a refresh the
 * other started and not start a second one.
 */
export function useRefreshChannel() {
  const queryClient = useQueryClient();
  return useMutation<ChannelSyncData, unknown, void>({
    mutationKey: mutationKeys.channelRefresh,
    retry: false,
    mutationFn: () =>
      apiRequest<ChannelSyncData>("/youtube/channel/refresh", { method: "POST" }),
    onSettled: () => invalidateChannelViews(queryClient),
  });
}

export function useDisconnectChannel() {
  const queryClient = useQueryClient();
  return useMutation<{ disconnected?: boolean }, unknown, void>({
    mutationFn: () =>
      apiRequest<{ disconnected?: boolean }>("/youtube/channel/disconnect", { method: "POST" }),
    onSettled: () => invalidateChannelViews(queryClient),
  });
}

/** Where the OAuth flow should return the browser to once Google is done. */
export function channelConnectUrl(returnTo: "/settings" | "/channel"): string {
  return `/youtube/channel/connect?return_to=${encodeURIComponent(returnTo)}`;
}
