import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { historyKeys } from "./useHistory";

/**
 * Settings, sync and channel data access.
 *
 * The channel status is read by the sidebar, the Dashboard, Settings and the
 * Channel page, so it lives under one key and is fetched once.
 */
export const systemKeys = {
  health: ["health"] as const,
  settings: ["system", "settings"] as const,
  cloudSync: ["system", "cloud-sync"] as const,
  channel: ["system", "channel"] as const,
  diagnostics: ["system", "diagnostics"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: systemKeys.health,
    queryFn: () => apiRequest<HealthStatus>("/health"),
    // An at-a-glance reassurance, not a monitor; the backend rate-limits per path.
    refetchInterval: 60_000,
    retry: 1,
  });
}

export function useSettingsStatus() {
  return useQuery({
    queryKey: systemKeys.settings,
    queryFn: () => apiRequest<SettingsStatus>("/api/settings/status"),
  });
}

export function useCloudSyncStatus() {
  return useQuery({
    queryKey: systemKeys.cloudSync,
    queryFn: () => apiRequest<CloudSyncStatus>("/api/cloud-sync/status"),
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
 * Runs `/diagnostics`, which performs one real YouTube search. It is a
 * mutation rather than a query so it only ever runs when asked.
 */
export function useLiveDiagnostics() {
  return useMutation<LiveDiagnostics, unknown, void>({
    mutationKey: systemKeys.diagnostics,
    mutationFn: () => apiRequest<LiveDiagnostics>("/diagnostics"),
  });
}

export function useChannelStatus() {
  return useQuery({
    queryKey: systemKeys.channel,
    queryFn: () => apiRequest<ChannelStatus>("/youtube/channel/status"),
  });
}

function invalidateChannelViews(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: systemKeys.channel });
  void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
  // The Dashboard's owned-performance numbers come from the history summary.
  void queryClient.invalidateQueries({ queryKey: historyKeys.all });
}

/**
 * Pulls fresh numbers from YouTube with the stored read-only token. Retrying
 * silently would spend quota twice, so failures surface instead.
 */
export function useRefreshChannel() {
  const queryClient = useQueryClient();
  return useMutation<ChannelSyncData, unknown, void>({
    mutationKey: ["channel-refresh"],
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
export function channelConnectUrl(returnTo: "/next/settings" | "/next/channel"): string {
  return `/youtube/channel/connect?return_to=${encodeURIComponent(returnTo)}`;
}
