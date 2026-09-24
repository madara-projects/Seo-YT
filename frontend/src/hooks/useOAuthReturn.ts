import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { historyKeys } from "./useHistory";
import { systemKeys } from "./useSystem";

export interface OAuthNotice {
  kind: "connected" | "error";
  message: string;
}

/** Google's `error` values that have a clearer explanation than their code. */
const REASONS: Record<string, string> = {
  access_denied: "Access was declined on the Google consent screen, so nothing was connected.",
};

/**
 * Reads the `?youtube=connected|error&reason=` the OAuth callback appends,
 * announces it once, refreshes everything that shows channel data, and then
 * removes the parameters so a reload does not repeat the message.
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

    if (outcome === "connected") {
      const message = "YouTube channel connected with read-only access.";
      toast.success(message);
      setNotice({ kind: "connected", message });
    } else {
      const message =
        (reason && REASONS[reason]) ||
        (reason
          ? `YouTube connection failed (${reason}). Nothing was changed; try connecting again.`
          : "YouTube connection failed. Nothing was changed; try connecting again.");
      toast.error(message);
      setNotice({ kind: "error", message });
    }

    void queryClient.invalidateQueries({ queryKey: systemKeys.channel });
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
