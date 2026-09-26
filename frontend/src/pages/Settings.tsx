import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Cloud,
  CloudUpload,
  Database,
  HardDrive,
  Info,
  Laptop,
  Moon,
  Palette,
  Radar,
  RefreshCw,
  Server,
  Settings2,
  Sun,
  Unplug,
  Youtube,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { useIsMutating } from "@tanstack/react-query";

import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { Field, Inset, Panel } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import {
  ChannelSetupNeeded,
  ConnectChannelCard,
  DisconnectChannelDialog,
  OAuthNoticeBanner,
} from "@/components/channel/ChannelConnection";
import {
  useChannelStatus,
  useCloudSyncStatus,
  useDisconnectChannel,
  useHealth,
  useLiveDiagnostics,
  useRefreshChannel,
  useRunCloudSync,
  useSettingsStatus,
} from "@/hooks/useSystem";
import { useOAuthReturnNotice } from "@/hooks/useOAuthReturn";
import { mutationKeys } from "@/hooks/queryKeys";
import { useRemPx } from "@/hooks/useRemPx";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { cn, formatNumber } from "@/lib/utils";
import { formatBytes, formatUptime, initialOf, relativeTime, scheduledTime } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { cloudSyncRunOutcome, cloudSyncState, collectorState, geminiFailureLabel } from "@/lib/systemFormat";
import { useTheme } from "@/lib/theme";

const SECTIONS = [
  { id: "channel", label: "YouTube channel", icon: Youtube },
  { id: "sync", label: "Cloud sync", icon: Cloud },
  { id: "providers", label: "AI & data providers", icon: Bot },
  { id: "database", label: "Local database", icon: Database },
  { id: "collector", label: "Snapshot collector", icon: Radar },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "about", label: "About", icon: Info },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

/**
 * When a stamp is set, both the absolute IST time and how long ago. A
 * `scheduled` time already passed reads "Due now", not "4 min ago".
 */
function When({
  value,
  empty = "Not run yet",
  scheduled = false,
}: {
  value?: string | null;
  empty?: string;
  scheduled?: boolean;
}) {
  if (!value) return <span className="text-muted-foreground">{empty}</span>;
  return (
    <span>
      {historyDate(value)}
      <span className="block text-xs font-normal text-muted-foreground">
        {scheduled ? scheduledTime(value) : relativeTime(value)}
      </span>
    </span>
  );
}

function SectionNav({ active }: { active: SectionId }) {
  const jump = (id: SectionId) =>
    document.getElementById(`settings-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <nav aria-label="Settings sections" className="min-w-0 lg:sticky lg:top-24 lg:self-start">
      <ul className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 scrollbar-none lg:mx-0 lg:flex-col lg:gap-0.5 lg:px-0">
        {SECTIONS.map(({ id, label, icon: Icon }) => (
          <li key={id} className="shrink-0">
            <button
              type="button"
              onClick={() => jump(id)}
              aria-current={active === id ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-2.5 whitespace-nowrap rounded-xl px-3 py-2 text-[0.8125rem] font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active === id
                  ? "bg-card text-foreground shadow-card ring-1 ring-border"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className={cn("size-4", active === id && "text-brand")} aria-hidden="true" />
              {label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function ChannelSection() {
  const status = useChannelStatus();
  const refresh = useRefreshChannel();
  // A refresh the Channel page started counts too: both share one mutation key.
  const refreshing = useIsMutating({ mutationKey: mutationKeys.channelRefresh }) > 0;
  const disconnect = useDisconnectChannel();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const data = status.data;
  const connected = Boolean(data?.connected);
  const title = data?.channel?.title || "YouTube channel";

  const onRefresh = async () => {
    try {
      await refresh.mutateAsync();
      toast.success("YouTube analytics and video counts updated.");
    } catch (error) {
      toast.error(formatApiError(error, "YouTube refresh failed."));
    }
  };

  const onDisconnect = async () => {
    try {
      await disconnect.mutateAsync();
      toast.success("YouTube channel disconnected.");
      setConfirmOpen(false);
    } catch (error) {
      toast.error(formatApiError(error, "Could not disconnect the channel."));
    }
  };

  return (
    <Panel
      id="settings-channel"
      className="scroll-mt-24"
      icon={Youtube}
      title="YouTube channel"
      description="Read-only access for real performance numbers. Nothing here can upload or edit."
      aside={
        status.isPending ? null : (
          <EvidenceChip
            tone={connected ? "ok" : data?.configured === false ? "warn" : "neutral"}
          >
            {connected ? "Connected" : data?.configured === false ? "Setup needed" : "Not connected"}
          </EvidenceChip>
        )
      }
    >
      {status.isPending ? (
        <CardSkeleton rows={3} />
      ) : status.isError ? (
        <ErrorState
          message={apiErrorMessage(status.error, "Could not load channel settings.")}
          requestId={apiRequestId(status.error)}
          onRetry={() => void status.refetch()}
        />
      ) : data?.configured === false ? (
        <ChannelSetupNeeded message={data.setup_message} />
      ) : !connected ? (
        <ConnectChannelCard returnTo="/next/settings" compact />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <span
              className="grid size-14 shrink-0 place-items-center rounded-full bg-brand-gradient p-0.5"
              aria-hidden="true"
            >
              <span className="grid size-full place-items-center rounded-full bg-card font-display text-xl font-semibold text-foreground">
                {initialOf(title)}
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-display text-lg font-semibold text-foreground">{title}</p>
              <p className="numeric truncate text-xs text-muted-foreground">
                {data?.channel?.id || "Channel ID unavailable"}
              </p>
            </div>
          </div>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Inset>
              <Field label="Connected">
                <When value={data?.channel?.connected_at} empty="Unknown" />
              </Field>
            </Inset>
            <Inset>
              <Field label="Last analytics sync">
                <When value={data?.latest_sync?.synced_at} empty="Not refreshed yet" />
              </Field>
            </Inset>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button onClick={onRefresh} disabled={refreshing}>
              <RefreshCw className={cn(refreshing && "animate-spin")} aria-hidden="true" />
              {refreshing ? "Refreshing…" : "Refresh analytics"}
            </Button>
            <Button variant="outline" asChild>
              <Link to="/channel">
                View channel stats
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button variant="danger" onClick={() => setConfirmOpen(true)}>
              <Unplug aria-hidden="true" />
              Disconnect
            </Button>
          </div>
        </div>
      )}

      <DisconnectChannelDialog
        open={confirmOpen}
        channelTitle={title}
        pending={disconnect.isPending}
        onConfirm={onDisconnect}
        onOpenChange={setConfirmOpen}
      />
    </Panel>
  );
}

function CloudSyncSection() {
  const status = useCloudSyncStatus();
  const run = useRunCloudSync();
  const data = status.data;
  const state = cloudSyncState(data?.state);
  const counts = data?.last_counts ?? {};

  const onRun = async () => {
    try {
      const result = await run.mutateAsync();
      // The run answers 200 even when it couldn't reach the cloud; only a healthy run succeeded.
      const outcome = cloudSyncRunOutcome(result?.state);
      if (outcome.kind === "success") toast.success(outcome.message);
      else if (outcome.kind === "warning") toast.warning(outcome.message);
      else toast.info(outcome.message);
    } catch (error) {
      toast.error(formatApiError(error, "Cloud sync failed; local packages are unchanged."));
    }
  };

  return (
    <Panel
      id="settings-sync"
      className="scroll-mt-24"
      icon={Cloud}
      title="Cloud sync"
      description="Keeps saved packages in step across your devices. Local SQLite stays the source of truth."
      aside={
        <>
          {status.isPending ? null : <EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>}
          <Button
            size="sm"
            variant="outline"
            onClick={onRun}
            disabled={run.isPending || !data?.enabled || Boolean(data?.running)}
          >
            <CloudUpload aria-hidden="true" />
            {run.isPending ? "Syncing…" : "Sync now"}
          </Button>
        </>
      }
    >
      {status.isPending ? (
        <CardSkeleton rows={3} />
      ) : status.isError ? (
        <ErrorState
          message={apiErrorMessage(status.error, "Cloud sync status unavailable.")}
          requestId={apiRequestId(status.error)}
          onRetry={() => void status.refetch()}
        />
      ) : !data?.enabled ? (
        <UnavailableNote>
          Cloud synchronization is disabled. Packages remain safely stored in local SQLite.
        </UnavailableNote>
      ) : (
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {([
              ["Device", data.device_id || "Unconfigured"],
              ["Local packages", formatNumber(data.local_packages)],
              ["Synced packages", formatNumber(data.synced_packages)],
              ["Pending changes", formatNumber(data.pending_uploads)],
              ["Conflicts", formatNumber(data.conflicts_detected)],
              ["In the cloud", formatNumber(data.remote_packages, "Not checked yet")],
            ] satisfies [string, string][]).map(([label, value]) => (
              <Inset key={label}>
                <Field label={label} mono>
                  {value}
                </Field>
              </Inset>
            ))}
          </dl>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Inset>
              <Field label="Last check">
                <When value={data.last_finished_at} />
              </Field>
            </Inset>
            <Inset>
              <Field label="Next check">
                <When value={data.next_run_at} empty="Not scheduled" scheduled />
              </Field>
            </Inset>
          </dl>
          {data.last_finished_at ? (
            <p className="text-xs text-muted-foreground">
              Last run uploaded {formatNumber(counts.pushed)} and downloaded {formatNumber(counts.pulled)} package
              changes
              {counts.failed ? `, with ${formatNumber(counts.failed)} failed` : ""}
              {counts.skipped
                ? `; ${formatNumber(counts.skipped)} cloud ${counts.skipped === 1 ? "change was" : "changes were"} skipped because this version can't apply ${counts.skipped === 1 ? "it" : "them"}`
                : ""}
              .
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">No sync has finished yet.</p>
          )}
          {data.last_error ? (
            <div className="space-y-1 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-3 text-[0.8125rem] leading-relaxed text-foreground">
              <p>
                {/^\w+$/.test(data.last_error) ? (
                  // Driver errors arrive as a bare class name: their messages
                  // can contain connection details, so the server keeps those.
                  <>
                    The last attempt failed (
                    <code className="numeric text-xs">{data.last_error}</code>).
                  </>
                ) : (
                  data.last_error
                )}{" "}
                Packages stay safe in local SQLite.
              </p>
              <p className="text-xs text-muted-foreground">
                {(data.consecutive_failures ?? 0) > 1
                  ? `${data.consecutive_failures} attempts in a row have failed, so retries are spaced further apart${data.next_run_at ? `; the next is ${relativeTime(data.next_run_at)}` : ""}.`
                  : "The sync retries automatically."}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}

function ProviderTile({
  icon: Icon,
  name,
  status,
  tone,
  detail,
}: {
  icon: React.ElementType;
  name: string;
  status: string;
  tone: EvidenceTone;
  detail: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-elevated p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-2.5 text-[0.8125rem] font-semibold text-foreground">
          <span className="grid size-8 place-items-center rounded-lg bg-card text-muted-foreground ring-1 ring-inset ring-border" aria-hidden="true">
            <Icon className="size-4" />
          </span>
          {name}
        </span>
        <EvidenceChip tone={tone}>{status}</EvidenceChip>
      </div>
      <div className="text-xs leading-relaxed text-muted-foreground">{detail}</div>
    </div>
  );
}

function ProvidersSection() {
  const settings = useSettingsStatus();
  const health = useHealth();
  const live = useLiveDiagnostics();
  const providers = settings.data?.providers ?? {};
  const gemini = providers.gemini ?? {};
  const providerHealth = gemini.provider_health ?? {};
  const researchHealth = gemini.research_provider_health;
  const youtube = providers.youtube_data_api ?? {};
  const redisConfigured = Boolean(providers.redis?.configured);
  const cacheOk = health.data?.cache_ok;

  const liveYoutube = live.data?.youtube;
  const liveTone: EvidenceTone =
    liveYoutube?.status === "ok" ? "ok" : liveYoutube?.status === "error" ? "bad" : "warn";

  return (
    <Panel
      id="settings-providers"
      className="scroll-mt-24"
      icon={Bot}
      title="AI & data providers"
      description="What writes the packages and where research data comes from. Keys are never shown."
    >
      {settings.isPending ? (
        <CardSkeleton rows={4} />
      ) : settings.isError ? (
        <ErrorState
          message={apiErrorMessage(settings.error, "Provider status unavailable.")}
          requestId={apiRequestId(settings.error)}
          onRetry={() => void settings.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <ProviderTile
              icon={Zap}
              name="Gemini"
              status={
                !gemini.configured
                  ? "Not configured"
                  : providerHealth.cooldown_active
                    ? "Cooling down"
                    : "Configured"
              }
              tone={!gemini.configured ? "warn" : providerHealth.cooldown_active ? "warn" : "ok"}
              detail={
                gemini.configured ? (
                  <>
                    Model <code className="numeric text-foreground">{gemini.model || "unknown"}</code>
                    {providerHealth.cooldown_active
                      ? ` · paused for ${Math.ceil(providerHealth.cooldown_remaining_seconds ?? 0)}s after repeated failures`
                      : ""}
                    {providerHealth.transient_failure_count
                      ? ` · ${providerHealth.transient_failure_count} recent transient failure(s)`
                      : " · no recent failures"}
                    {providerHealth.last_failure_category
                      ? ` · last: ${geminiFailureLabel(providerHealth.last_failure_category)}`
                      : ""}
                    {researchHealth?.cooldown_active || researchHealth?.transient_failure_count ? (
                      <span className="block">
                        Research calls:{" "}
                        {researchHealth.cooldown_active
                          ? `paused for ${Math.ceil(researchHealth.cooldown_remaining_seconds ?? 0)}s`
                          : `${researchHealth.transient_failure_count} recent transient failure(s)`}
                        {researchHealth.last_failure_category
                          ? ` · last: ${geminiFailureLabel(researchHealth.last_failure_category)}`
                          : ""}
                      </span>
                    ) : null}
                  </>
                ) : (
                  "Packages are written by the local fallback until a Gemini key is configured."
                )
              }
            />
            <ProviderTile
              icon={Youtube}
              name="YouTube Data API"
              status={youtube.configured ? `${formatNumber(youtube.key_count ?? 0)} key(s)` : "Not configured"}
              tone={youtube.configured ? "ok" : "bad"}
              detail={
                youtube.configured
                  ? "Used for public research: search results, video statistics and suggestions."
                  : "Research is unavailable until an API key is configured."
              }
            />
            <ProviderTile
              icon={HardDrive}
              name="Local fallback"
              status={providers.local_fallback?.available ? "Available" : "Unavailable"}
              tone={providers.local_fallback?.available ? "ok" : "warn"}
              detail="Writes a package locally when Gemini is unavailable, and says so on the result."
            />
            <ProviderTile
              icon={Server}
              name="Redis cache"
              status={
                !redisConfigured
                  ? "Not configured"
                  : cacheOk === false
                    ? "Unreachable"
                    : "Configured"
              }
              tone={!redisConfigured ? "neutral" : cacheOk === false ? "bad" : "ok"}
              detail={
                !redisConfigured
                  ? "Optional. Research still runs, just without a shared cache."
                  : cacheOk === false
                    ? "Configured but not responding; research runs uncached."
                    : "Caches research responses to save quota."
              }
            />
          </div>

          <Inset className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <p className="text-[0.8125rem] font-semibold text-foreground">Live YouTube check</p>
                <p className="text-xs text-muted-foreground">
                  Makes one small YouTube request to prove the key works (1 quota unit).
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => live.mutate()}
                disabled={live.isPending}
              >
                <Activity aria-hidden="true" />
                {live.isPending ? "Checking…" : "Run live check"}
              </Button>
            </div>
            {live.isError ? (
              <ErrorState
                message={apiErrorMessage(live.error, "The live check could not run.")}
                requestId={apiRequestId(live.error)}
              />
            ) : liveYoutube ? (
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <EvidenceChip tone={liveTone}>
                  {liveYoutube.status === "ok"
                    ? "YouTube reachable"
                    : liveYoutube.status === "missing_api_key"
                      ? "No API key"
                      : "YouTube request failed"}
                </EvidenceChip>
                {liveYoutube.error ? <span>{liveYoutube.error}</span> : null}
                {liveYoutube.available_key_count ? (
                  <span>
                    Key {formatNumber(liveYoutube.active_key_index)} of{" "}
                    {formatNumber(liveYoutube.available_key_count)} in use
                  </span>
                ) : null}
                {liveYoutube.quota_date ? <span>· quota day {liveYoutube.quota_date}</span> : null}
                {liveYoutube.warning ? <span>· {liveYoutube.warning}</span> : null}
              </div>
            ) : null}
          </Inset>
        </div>
      )}
    </Panel>
  );
}

function DatabaseSection() {
  const settings = useSettingsStatus();
  const database = settings.data?.database ?? {};
  const counts = database.counts ?? {};
  // The server now reports the database's real state; a missing value is unknown, not healthy.
  const healthy = typeof database.healthy === "boolean" ? database.healthy : null;

  return (
    <Panel
      id="settings-database"
      className="scroll-mt-24"
      icon={Database}
      title="Local database"
      description="Everything you generate is saved here first."
      aside={
        settings.isSuccess ? (
          <EvidenceChip tone={healthy === null ? "neutral" : healthy ? "ok" : "bad"}>
            {healthy === null ? "Unavailable" : healthy ? "Healthy" : "Error"}
          </EvidenceChip>
        ) : null
      }
    >
      {settings.isPending ? (
        <CardSkeleton rows={3} />
      ) : settings.isError ? (
        <UnavailableNote>Database status unavailable.</UnavailableNote>
      ) : (
        <div className="space-y-4">
          {healthy === false ? (
            <p className="rounded-xl border border-tone-bad-border bg-tone-bad-bg px-3.5 py-3 text-[0.8125rem] leading-relaxed text-foreground">
              The database could not be opened
              {database.error ? (
                <>
                  {" "}
                  (<code className="numeric text-xs">{database.error}</code>)
                </>
              ) : null}
              , so its counts are unavailable. Saving and loading packages fail until it can be read again.
            </p>
          ) : null}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["Packages", counts.packages],
              ["Ideas", counts.ideas],
              ["Linked videos", counts.published_links],
              ["Performance snapshots", counts.performance_snapshots],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl border border-border bg-elevated p-4">
                <p className="font-display text-2xl font-semibold text-foreground">
                  {formatNumber(value)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
          <dl className="grid gap-3 sm:grid-cols-3">
            <Inset>
              <Field label="File" mono>
                {database.name || "Unknown"}
              </Field>
            </Inset>
            <Inset>
              <Field label="Schema · size" mono>
                {typeof database.schema_version === "number" ? `v${database.schema_version}` : "Schema unavailable"} ·{" "}
                {formatBytes(database.size_bytes)}
              </Field>
            </Inset>
            <Inset>
              <Field label="Last backup">
                <When value={database.last_backup_at} empty="No migration backup recorded" />
              </Field>
            </Inset>
          </dl>
        </div>
      )}
    </Panel>
  );
}

function CollectorSection() {
  const settings = useSettingsStatus();
  const collector = settings.data?.collector ?? {};
  const state = collectorState(collector.state);
  const counts = collector.last_counts ?? {};

  // Counts mean something only once a check has finished. The backend always
  // sends `last_counts`, as zeros before the first run, so only the finish
  // time tells a real zero from "not run yet".
  const ran = Boolean(collector.last_finished_at);
  const count = (value: number | undefined) => (ran ? formatNumber(value) : "Not run yet");
  const explanation =
    collector.state === "disabled"
      ? "Automatic collection is disabled by configuration."
      : collector.state === "unconfigured"
        ? "No YouTube channel is connected, so the collector has nothing it may read: it only collects videos verified for your channel. Connect it above."
        : collector.dry_run
          ? "Dry run: it plans which linked videos are due for a snapshot but makes no YouTube or Gemini calls and writes nothing."
          : collector.state === "error"
            ? `Collector error: ${collector.last_error || "the collector reported an error."}`
            : "Captures performance snapshots of linked videos at fixed ages, so later learning compares like with like.";

  return (
    <Panel
      id="settings-collector"
      className="scroll-mt-24"
      icon={Radar}
      title="Snapshot collector"
      description="Background job that records how linked videos perform over time."
      aside={settings.isSuccess ? <EvidenceChip tone={state.tone}>{state.label}</EvidenceChip> : null}
    >
      {settings.isPending ? (
        <CardSkeleton rows={2} />
      ) : settings.isError ? (
        <UnavailableNote>Collector status unavailable.</UnavailableNote>
      ) : (
        <div className="space-y-4">
          <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{explanation}</p>
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {([
              ["Mode", collector.enabled ? (collector.dry_run ? "Dry run" : "Live") : "Off"],
              ["Linked videos due", count(counts.links)],
              ["Due windows", count(counts.windows)],
              ["Captured · failed", ran ? `${formatNumber(counts.captured)} · ${formatNumber(counts.failed)}` : "Not run yet"],
            ] satisfies [string, string][]).map(([label, value]) => (
              <Inset key={label}>
                <Field label={label} mono={label !== "Mode"}>
                  {value}
                </Field>
              </Inset>
            ))}
          </dl>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Inset>
              <Field label="Last check">
                <When value={collector.last_finished_at} />
              </Field>
            </Inset>
            <Inset>
              <Field label="Next check">
                <When value={collector.next_run_at} empty="Not scheduled" scheduled />
              </Field>
            </Inset>
          </dl>
        </div>
      )}
    </Panel>
  );
}

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Laptop },
] as const;

function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const radios = useRef<(HTMLButtonElement | null)[]>([]);

  // A radio group is one tab stop; the arrow keys move and select within it.
  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    const last = THEMES.length - 1;
    const next =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? index === last ? 0 : index + 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? index === 0 ? last : index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    const target = THEMES[next];
    if (!target) return;
    setTheme(target.value);
    radios.current[next]?.focus();
  };

  return (
    <Panel
      id="settings-appearance"
      className="scroll-mt-24"
      icon={Palette}
      title="Appearance"
      description="Saved in this browser only."
    >
      <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
        {THEMES.map(({ value, label, icon: Icon }, index) => {
          const checked = theme === value;
          return (
            <button
              key={value}
              ref={(node) => {
                radios.current[index] = node;
              }}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked ? 0 : -1}
              onClick={() => setTheme(value)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={cn(
                "group overflow-hidden rounded-2xl border text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                checked ? "border-brand-border ring-2 ring-brand/30" : "border-border hover:border-foreground/20",
              )}
            >
              <span
                className={cn(
                  "relative block h-24 overflow-hidden",
                  value === "light" && "bg-[oklch(0.984_0.004_286)]",
                  value === "dark" && "bg-[oklch(0.145_0.016_286)]",
                  value === "system" &&
                    "bg-[linear-gradient(115deg,oklch(0.984_0.004_286)_50%,oklch(0.145_0.016_286)_50%)]",
                )}
                aria-hidden="true"
              >
                <span className="absolute inset-y-3 left-3 w-7 rounded-md bg-[oklch(0.175_0.03_286)]" />
                <span className="absolute left-12 right-3 top-3 h-3 rounded bg-brand-gradient opacity-80" />
                <span
                  className={cn(
                    "absolute bottom-3 left-12 right-3 h-9 rounded-md border",
                    value === "dark"
                      ? "border-white/10 bg-[oklch(0.183_0.02_286)]"
                      : "border-black/5 bg-white",
                  )}
                />
              </span>
              <span className="flex items-center gap-2 border-t border-border bg-card px-3.5 py-2.5 text-[0.8125rem] font-medium text-foreground">
                <Icon className={cn("size-4", checked ? "text-brand" : "text-muted-foreground")} aria-hidden="true" />
                {label}
                {checked ? <span className="ml-auto size-2 rounded-full bg-brand-gradient" aria-hidden="true" /> : null}
              </span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}

function AboutSection() {
  const settings = useSettingsStatus();
  const health = useHealth();
  const app = settings.data?.app ?? {};
  const healthy = health.data?.status === "ok";

  return (
    <Panel
      id="settings-about"
      className="scroll-mt-24"
      icon={Info}
      title="About"
      aside={
        health.isSuccess ? (
          <EvidenceChip tone={healthy ? "ok" : "warn"}>{healthy ? "Online" : "Degraded"}</EvidenceChip>
        ) : health.isError ? (
          <EvidenceChip tone="bad">Unreachable</EvidenceChip>
        ) : null
      }
    >
      <div className="space-y-4">
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Inset>
            <Field label="App">{app.name || health.data?.app_name || "Win-Engine"}</Field>
          </Inset>
          <Inset>
            <Field label="Version" mono>
              {app.version || health.data?.version || "Unknown"}
            </Field>
          </Inset>
          <Inset>
            <Field label="Environment">{app.environment || health.data?.environment || "Unknown"}</Field>
          </Inset>
          <Inset>
            <Field label="Uptime">{formatUptime(health.data?.uptime_seconds)}</Field>
          </Inset>
        </dl>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <a href="/app" target="_blank" rel="noreferrer">
              Open the classic dashboard
              <ArrowUpRight aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </Button>
        </div>
      </div>
    </Panel>
  );
}

export default function SettingsPage() {
  const { notice, dismiss } = useOAuthReturnNotice();
  const [active, setActive] = useState<SectionId>("channel");
  // The sticky header's height in rem, so the offset follows the 80% desktop scale.
  const headerOffset = useRemPx()(6);

  // Highlight the section in view. Skipped where IntersectionObserver is absent.
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        const id = visible?.target.id.replace("settings-", "") as SectionId | undefined;
        if (id) setActive(id);
      },
      // IntersectionObserver takes only px or %.
      { rootMargin: `-${headerOffset}px 0px -55% 0px` },
    );
    for (const { id } of SECTIONS) {
      const node = document.getElementById(`settings-${id}`);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [headerOffset]);

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="System"
        icon={Settings2}
        title="Settings"
        description="Connections, sync and system health in one place. Secret values such as keys and tokens are never shown here."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[13.125rem_minmax(0,1fr)]">
        <SectionNav active={active} />
        <div className="min-w-0 space-y-5">
          <OAuthNoticeBanner notice={notice} onDismiss={dismiss} />
          <ChannelSection />
          <CloudSyncSection />
          <ProvidersSection />
          <DatabaseSection />
          <CollectorSection />
          <AppearanceSection />
          <AboutSection />
        </div>
      </div>
    </div>
  );
}
