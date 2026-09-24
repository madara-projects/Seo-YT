import { Delta } from "@/components/common/Delta";
import { cn } from "@/lib/utils";
import { formatMinutes, formatSeconds } from "@/lib/format";
import type { PeriodMetric } from "@/lib/channelFormat";

function formatMetric(metric: PeriodMetric, value: number | null): string {
  if (value === null) return "Unavailable";
  if (metric.key === "estimatedMinutesWatched") return formatMinutes(value);
  if (metric.key === "averageViewDuration") return formatSeconds(value);
  return value.toLocaleString();
}

/**
 * Last 28 days against the 28 before, per metric. Bars are relative change,
 * capped at ±100% so one spike does not flatten the rest; the printed
 * percentage is always exact.
 */
export function PeriodComparison({ metrics }: { metrics: PeriodMetric[] }) {
  return (
    <ul className="space-y-4">
      {metrics.map((metric) => {
        const width = metric.change === null ? 0 : Math.min(Math.abs(metric.change), 100) / 2;
        const up = (metric.change ?? 0) >= 0;
        return (
          <li key={metric.key} className="space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">{metric.label}</p>
                <p className="numeric text-xs text-muted-foreground">
                  {formatMetric(metric, metric.current)}
                  <span className="font-sans"> vs </span>
                  {formatMetric(metric, metric.previous)}
                </p>
              </div>
              <Delta
                value={metric.change}
                label={metric.change === null ? "No comparison" : undefined}
              />
            </div>
            <div className="relative h-1.5 rounded-full bg-muted" aria-hidden="true">
              <span className="absolute inset-y-[-3px] left-1/2 w-px bg-border" />
              {metric.change !== null ? (
                <span
                  className={cn(
                    "absolute inset-y-0",
                    up ? "left-1/2 rounded-r-full bg-tone-ok" : "right-1/2 rounded-l-full bg-tone-bad",
                  )}
                  style={{ width: `${width}%` }}
                />
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
