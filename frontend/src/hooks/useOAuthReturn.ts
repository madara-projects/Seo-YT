import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { historyKeys, systemKeys } from "./queryKeys";
import { fetchFreshChannelStatus } from "./useSystem";

export interface OAuthNotice {
  kind: "connected" | "error";
  message: string;
}

/** Google's `error` values, and the server's own reasons, explained. */
const REASONS: Record<string, string> = {
  access_denied: "Access was declined on the Google consent screen, so nothing was connected.",
  expired_state: "The connection request expired or was already used. Start the connection again.",
  missing_scopes:
    "Both permissions are needed: allow access to your YouTube account and to YouTube Analytics, then connect again.",
  no_refresh_token:
    "Google did not return a lasting token. Remove Win-Engine in your Google Account permissions, then connect again.",
  no_channel: "That Google account has no YouTube channel. Connect with the account that owns your channel.",
  not_configured: "YouTube OAuth is not set up on this server. Add the OAuth settings to .env and restart it.",
  connect_failed: "Google's reply could not be completed, so nothing was connected. Try connecting again.",
};

/** Anyone can put any text in a link, so an unrecognised reason is never echoed. */
const GENERIC_FAILURE = "YouTube connection failed. Nothing was changed; try connecting again.";

/**
 * Reads the `?youtube=connected|error&reason=` the OAuth callback appends,
 * announces it once, refreshes everything that shows channel data, and then
 * removes the parameters so a reload does not repeat the message.
 *
 * The parameters come from a URL, so they are not taken on trust: a claimed
 * connection is announced only once the server confirms a connected channel.
 */
export function useOAuthReturnNotice() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<OAuthNotice | null>(null);
  const handled = useRef<string | null>(null);

  const outcome = searchParams.get("youtube");
  const reason = searchParams.get("reason");

  useEffect(() => {
    if (outcome !== "connected" && outcome !== "error") return;
    const key = `${outcome}:${reason ?? ""}`;
    // StrictMode runs effects twice in development; announce once.
    if (handled.current === key) return;
    handled.current = key;

    const announce = (next: OAuthNotice) => {
      if (next.kind === "connected") toast.success(next.message);
      else toast.error(next.message);
      setNotice(next);
    };

    if (outcome === "connected") {
      // Also refreshes the cached status that the sidebar and the page show.
      void fetchFreshChannelStatus(queryClient)
        .then((status) =>
          announce(
            status.connected
              ? { kind: "connected", message: "YouTube channel connected with read-only access." }
              : { kind: "error", message: "The server has no connected channel, so the connection didn't complete. Try connecting again." },
          ),
        )
        .catch(() =>
          announce({ kind: "error", message: "The connection could not be confirmed: the channel status is unavailable." }),
        );
    } else {
      announce({ kind: "error", message: (reason && REASONS[reason]) || GENERIC_FAILURE });
      void queryClient.invalidateQueries({ queryKey: systemKeys.channel });
    }

    void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
    void queryClient.invalidateQueries({ queryKey: historyKeys.all });

    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("youtube");
        next.delete("reason");
        return next;
      },
      { replace: true },
    );
  }, [outcome, reason, queryClient, setSearchParams]);

  return { notice, dismiss: () => setNotice(null) };
}
