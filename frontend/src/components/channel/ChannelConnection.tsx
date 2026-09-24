import {
  BarChart3,
  CheckCircle2,
  Clock,
  Eye,
  KeyRound,
  Lock,
  TriangleAlert,
  Users,
  X,
  Youtube,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { channelConnectUrl } from "@/hooks/useSystem";
import type { OAuthNotice } from "@/hooks/useOAuthReturn";

const PERMISSIONS = [
  { label: "View your YouTube account", scope: "youtube.readonly" },
  { label: "View YouTube Analytics reports", scope: "yt-analytics.readonly" },
];

const SETUP_VARIABLES = [
  "WIN_ENGINE_YOUTUBE_OAUTH_CLIENT_ID",
  "WIN_ENGINE_YOUTUBE_OAUTH_CLIENT_SECRET",
  "WIN_ENGINE_YOUTUBE_OAUTH_REDIRECT_URI",
  "WIN_ENGINE_OAUTH_TOKEN_ENCRYPTION_KEY",
];

/** The result of a return from Google's consent screen. */
export function OAuthNoticeBanner({
  notice,
  onDismiss,
}: {
  notice: OAuthNotice | null;
  onDismiss: () => void;
}) {
  if (!notice) return null;
  const ok = notice.kind === "connected";
  return (
    <div
      role={ok ? "status" : "alert"}
      className={cn(
        "flex items-start gap-3 rounded-2xl border p-4",
        ok ? "border-tone-ok-border bg-tone-ok-bg" : "border-tone-bad-border bg-tone-bad-bg",
      )}
    >
      {ok ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-tone-ok" aria-hidden="true" />
      ) : (
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-tone-bad" aria-hidden="true" />
      )}
      <p className="flex-1 text-[13px] font-medium text-foreground">{notice.message}</p>
      <Button variant="ghost" size="icon-sm" onClick={onDismiss} aria-label="Dismiss message" className="-my-1">
        <X aria-hidden="true" />
      </Button>
    </div>
  );
}

/** Invitation to connect, with the exact read-only scopes spelled out. */
export function ConnectChannelCard({
  returnTo,
  compact = false,
}: {
  returnTo: "/next/settings" | "/next/channel";
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border hero-wash",
        compact ? "p-5" : "p-6 sm:p-8",
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-dots [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_60%)]"
        aria-hidden="true"
      />
      <div className={cn("relative grid gap-6", !compact && "lg:grid-cols-[minmax(0,1fr)_minmax(0,300px)] lg:items-center")}>
        <div className="space-y-4">
          <span
            className="grid size-12 place-items-center rounded-2xl bg-[#ff0033] text-white shadow-[0_10px_24px_-10px_#ff0033]"
            aria-hidden="true"
          >
            <Youtube className="size-6" />
          </span>
          <div className="space-y-2">
            <h3 className="font-display text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
              Connect your YouTube channel
            </h3>
            <p className="max-w-xl text-[13px] leading-relaxed text-muted-foreground">
              See real 28-day views, watch time, subscribers and per-video numbers next to your
              packages. Access is read-only: Win-Engine can never upload, edit or delete anything
              on your channel.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="gradient" size="lg" asChild>
              <a href={channelConnectUrl(returnTo)}>
                <Youtube aria-hidden="true" />
                Connect YouTube channel
              </a>
            </Button>
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Lock className="size-3.5" aria-hidden="true" />
              Token stored encrypted in your local database
            </span>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-border bg-card/80 p-4 backdrop-blur-sm">
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
            Google will ask to
          </p>
          <ul className="space-y-2">
            {PERMISSIONS.map(({ label, scope }) => (
              <li key={scope} className="flex items-start gap-2 text-[13px] text-foreground">
                <Eye className="mt-0.5 size-3.5 shrink-0 text-brand" aria-hidden="true" />
                <span>
                  {label}
                  <code className="numeric block text-[11px] text-muted-foreground">{scope}</code>
                </span>
              </li>
            ))}
          </ul>
          <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
            {[
              { icon: Users, label: "Subscribers" },
              { icon: Clock, label: "Watch time" },
              { icon: BarChart3, label: "Per video" },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="space-y-1">
                <Icon className="mx-auto size-4 text-muted-foreground" aria-hidden="true" />
                <p className="text-[11px] text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Shown when the server has no OAuth client configured. */
export function ChannelSetupNeeded({ message }: { message?: string | null }) {
  return (
    <div className="space-y-4 rounded-2xl border border-tone-warn-border bg-tone-warn-bg p-5">
      <div className="flex items-start gap-3">
        <KeyRound className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-[13px] font-semibold text-foreground">YouTube OAuth is not set up</p>
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {message ||
              "Add YouTube OAuth client credentials and an encryption key to .env to connect your channel."}
          </p>
        </div>
      </div>
      <div className="rounded-xl border border-border bg-card p-3.5">
        <p className="mb-2 text-xs text-muted-foreground">
          Set these in <code className="numeric text-foreground">.env</code>, then restart the
          server:
        </p>
        <ul className="space-y-1">
          {SETUP_VARIABLES.map((name) => (
            <li key={name} className="numeric break-all text-xs text-foreground">
              {name}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function DisconnectChannelDialog({
  open,
  channelTitle,
  pending,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  channelTitle: string;
  pending: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <span
            className="mb-1 grid size-11 place-items-center rounded-2xl bg-tone-bad-bg text-tone-bad ring-1 ring-inset ring-tone-bad-border"
            aria-hidden="true"
          >
            <Youtube className="size-5" />
          </span>
          <DialogTitle>Disconnect {channelTitle || "YouTube channel"}?</DialogTitle>
          <DialogDescription>
            This deletes the stored read-only token from the local database, so channel numbers stop
            refreshing. Saved packages, video links and past syncs are kept. To revoke access on
            Google&apos;s side as well, remove Win-Engine from your Google Account permissions.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={pending}>
            {pending ? "Disconnecting…" : "Disconnect"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
