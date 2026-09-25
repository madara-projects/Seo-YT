import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Clock,
  Eye,
  GraduationCap,
  History,
  ListVideo,
  Trophy,
  Users,
  Youtube,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Meter } from "@/components/common/Meter";
import { Inset, Panel } from "@/components/common/Panel";
import { CardSkeleton, UnavailableNote } from "@/components/common/States";
import { cn, formatNumber } from "@/lib/utils";
import { initialOf } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { riskTone } from "@/lib/dashboardFormat";
import type {
  CohortLearning,
  OwnedPerformance,
  RecentRun,
  RetentionPattern,
  WinningTitle,
} from "@/api/historyTypes";

export function ChannelSnapshot({
  owned,
  channelTitle,
  isConnected,
  syncedAt,
  isPending,
  className,
}: {
  owned: OwnedPerformance;
  channelTitle: string;
  isConnected: boolean;
  syncedAt: string | null;
  isPending: boolean;
  className?: string;
}) {
  return (
    <Panel
      className={className}
      icon={Youtube}
      iconTone={isConnected ? "brand" : "neutral"}
      title="Connected channel"
      aside={
        <EvidenceChip tone={isConnected ? "ok" : "neutral"}>
          {isConnected ? "Connected" : "Not connected"}
        </EvidenceChip>
      }
    >
      {isPending ? (
        <CardSkeleton rows={2} />
      ) : isConnected ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3.5">
            <span
              className="grid size-12 shrink-0 place-items-center rounded-full bg-brand-gradient p-0.5"
              aria-hidden="true"
            >
              <span className="grid size-full place-items-center rounded-full bg-card font-display text-lg font-semibold text-foreground">
                {initialOf(channelTitle)}
              </span>
            </span>
            <div className="min-w-0">
              <p className="truncate font-display text-lg font-semibold text-foreground">
                {channelTitle}
              </p>
              <p className="text-xs text-muted-foreground">
                Read-only access. This tool never uploads or edits.
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-2.5">
            {[
              ["Subscribers", formatNumber(owned.subscribers)],
              ["Lifetime views", formatNumber(owned.lifetime_views)],
              ["Linked videos", formatNumber(owned.linked_videos_count ?? 0)],
              ["Last synced", syncedAt ? historyDate(syncedAt) : "Never"],
            ].map(([label, value]) => (
              <Inset key={label} className="p-3">
                <dt className="text-[0.6875rem] text-muted-foreground">{label}</dt>
                <dd
                  className={cn(
                    "mt-0.5 font-semibold text-foreground",
                    label === "Last synced" ? "text-xs" : "numeric text-sm",
                  )}
                >
                  {value}
                </dd>
              </Inset>
            ))}
          </dl>
          <Button variant="soft" size="sm" asChild>
            <Link to="/channel">
              Open channel stats
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <UnavailableNote>
            No YouTube channel is connected, so real performance data is unavailable. The packaging
            tools work without it.
          </UnavailableNote>
          <ul className="grid grid-cols-2 gap-2">
            {[
              { icon: Eye, label: "28-day views" },
              { icon: Clock, label: "Watch time" },
              { icon: Users, label: "Subscribers" },
              { icon: ListVideo, label: "Per-video counts" },
            ].map(({ icon: Icon, label }) => (
              <li
                key={label}
                className="flex items-center gap-2 rounded-xl border border-dashed border-border px-3 py-2.5 text-xs text-muted-foreground"
              >
                <Icon className="size-3.5 shrink-0 text-brand" aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/settings">Connect in Settings</Link>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/channel">
                See what it unlocks
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
      )}
    </Panel>
  );
}

export function LearningPanel({
  data,
  isPending,
  isError,
  className,
}: {
  data: CohortLearning | undefined;
  isPending: boolean;
  isError: boolean;
  className?: string;
}) {
  const sample = typeof data?.sample_size === "number" ? data.sample_size : 0;
  const threshold = typeof data?.next_threshold === "number" ? data.next_threshold : null;

  return (
    <Panel
      className={className}
      icon={GraduationCap}
      title="Learning confidence"
      description="Learning from results starts only once enough comparable videos have matured."
      aside={
        <EvidenceChip tone={data?.learning_allowed ? "ok" : "warn"}>
          {data?.confidence_label ?? "Unavailable"}
        </EvidenceChip>
      }
    >
      {isPending ? (
        <CardSkeleton rows={2} />
      ) : isError ? (
        <UnavailableNote>Learning status could not be loaded.</UnavailableNote>
      ) : (
        <div className="space-y-4">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-display text-4xl font-semibold leading-none tracking-tight text-foreground">
                {formatNumber(sample)}
              </p>
              <p className="mt-1.5 text-xs text-muted-foreground">Comparable videos</p>
            </div>
            <div className="text-right">
              <p className="numeric text-sm font-semibold text-foreground">
                {formatNumber(data?.next_threshold)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">Needed for the next level</p>
            </div>
          </div>
          <Meter
            value={sample}
            max={threshold ?? Math.max(sample, 1)}
            label="Comparable videos collected toward the next learning level"
          />
          <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
            {data?.recommendation ?? "Learning status is unavailable for this window."}
          </p>
        </div>
      )}
    </Panel>
  );
}

export function RecentPackages({
  runs,
  isPending,
  className,
}: {
  runs: RecentRun[];
  isPending: boolean;
  className?: string;
}) {
  return (
    <Panel
      className={className}
      icon={History}
      title="Recent packages"
      aside={
        <Button variant="ghost" size="sm" asChild>
          <Link to="/history">
            View all
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      }
    >
      {isPending ? (
        <CardSkeleton rows={3} />
      ) : runs.length ? (
        <ul className="-mx-2 space-y-0.5">
          {runs.slice(0, 6).map((run) => (
            <li key={run.id}>
              <Link
                to={`/history?run=${run.id}`}
                className="group flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span
                  className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-soft font-display text-sm font-semibold text-brand ring-1 ring-inset ring-brand-border"
                  aria-hidden="true"
                >
                  {initialOf(run.title)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">
                    {run.title || "Untitled package"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {historyDate(run.created_at)}
                  </span>
                </span>
                <span className="hidden shrink-0 gap-5 text-right sm:flex">
                  <span>
                    <span className="numeric block text-sm font-semibold text-foreground">
                      {formatNumber(run.opportunity_score)}
                    </span>
                    <span className="block text-[0.6875rem] text-muted-foreground">Opportunity</span>
                  </span>
                  <span>
                    <span className="numeric block text-sm font-semibold text-foreground">
                      {formatNumber(run.title_score)}
                    </span>
                    <span className="block text-[0.6875rem] text-muted-foreground">Title</span>
                  </span>
                </span>
                <ArrowRight
                  className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                  aria-hidden="true"
                />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <UnavailableNote>
          No saved packages yet. Generate one in Creator and it will appear here.
        </UnavailableNote>
      )}
    </Panel>
  );
}

const RISK_BAR: Record<string, string> = {
  bad: "bg-tone-bad",
  warn: "bg-tone-warn",
  info: "bg-tone-info",
  neutral: "bg-muted-foreground/40",
};

export function RetentionSpread({
  rows,
  isPending,
  className,
}: {
  rows: RetentionPattern[];
  isPending: boolean;
  className?: string;
}) {
  const total = rows.reduce((sum, row) => sum + (Number(row.count) || 0), 0);

  return (
    <Panel
      className={className}
      icon={Activity}
      title="Retention risk spread"
      aside={<EvidenceChip tone="warn">Pre-publish</EvidenceChip>}
    >
      {isPending ? (
        <CardSkeleton rows={2} />
      ) : rows.length && total > 0 ? (
        <div className="space-y-4">
          <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
            {rows.map((row) => {
              const risk = String(row.retention_risk ?? "Unknown");
              const share = ((Number(row.count) || 0) / total) * 100;
              return (
                <span
                  key={risk}
                  className={cn("h-full first:rounded-l-full last:rounded-r-full", RISK_BAR[riskTone(risk)])}
                  style={{ width: `${share}%` }}
                />
              );
            })}
          </div>
          <ul className="space-y-2">
            {rows.map((row) => {
              const risk = String(row.retention_risk ?? "Unknown");
              const count = Number(row.count) || 0;
              return (
                <li key={risk} className="flex items-center justify-between gap-2">
                  <EvidenceChip tone={riskTone(risk)}>{risk}</EvidenceChip>
                  <span className="text-xs text-muted-foreground">
                    <span className="numeric font-semibold text-foreground">
                      {formatNumber(count)}
                    </span>{" "}
                    · {Math.round((count / total) * 100)}%
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Counts of saved packages by their pre-publish risk assessment. This is not measured
            audience retention.
          </p>
        </div>
      ) : (
        <UnavailableNote>No retention assessments recorded yet.</UnavailableNote>
      )}
    </Panel>
  );
}

export function TopTitles({
  titles,
  scoreTrend,
  isPending,
  className,
}: {
  titles: WinningTitle[];
  scoreTrend?: string;
  isPending: boolean;
  className?: string;
}) {
  return (
    <Panel
      className={className}
      icon={Trophy}
      title="Highest-scoring titles"
      aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
    >
      {isPending ? (
        <CardSkeleton rows={3} />
      ) : titles.length ? (
        <div className="space-y-4">
          <ol className="space-y-2">
            {titles.slice(0, 5).map((item, index) => (
              <li
                key={`${item.title}-${index}`}
                className="flex items-center gap-3 rounded-xl border border-border/80 bg-elevated p-3"
              >
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-full font-display text-xs font-semibold",
                    index === 0 ? "bg-brand-gradient text-white" : "bg-muted text-muted-foreground",
                  )}
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <p className="min-w-0 flex-1 text-sm text-foreground">{item.title}</p>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="numeric text-xs font-semibold text-foreground">
                    {formatNumber(item.title_score)}/10
                  </span>
                  {item.opportunity_label ? (
                    <EvidenceChip tone="neutral" className="hidden sm:inline-flex">
                      {item.opportunity_label}
                    </EvidenceChip>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Ranked by the local title-quality heuristic at generation time — not by views, CTR, or
            any published result.
          </p>
          {scoreTrend ? (
            <p className="rounded-xl border border-dashed border-border px-3.5 py-2.5 text-xs leading-relaxed text-muted-foreground">
              <strong className="font-semibold text-foreground">Score trend:</strong> {scoreTrend}
            </p>
          ) : null}
        </div>
      ) : (
        <UnavailableNote>No scored titles yet.</UnavailableNote>
      )}
    </Panel>
  );
}
