import { cn } from "@/lib/utils";
import { useHealth } from "@/hooks/useSystem";

/**
 * Backend reachability, shown in the sidebar footer. Polls slowly: this is an
 * at-a-glance reassurance, not a monitor, and the backend rate-limits per path.
 */
export function HealthIndicator({ className }: { className?: string }) {
  const { data, isError, isPending } = useHealth();

  const healthy = !isError && data?.status === "ok";
  const label = isPending
    ? "Checking backend"
    : isError
      ? "Backend unreachable"
      : healthy
        ? "Backend online"
        : "Backend degraded";
  const tone = isPending
    ? "bg-sidebar-muted"
    : healthy
      ? "bg-tone-ok"
      : isError
        ? "bg-tone-bad"
        : "bg-tone-warn";

  return (
    <div className={cn("flex items-center gap-2.5 px-1", className)}>
      <span className="relative flex size-2 shrink-0" aria-hidden="true">
        {healthy ? (
          <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60", tone)} />
        ) : null}
        <span className={cn("relative inline-flex size-2 rounded-full", tone)} />
      </span>
      <p className="min-w-0 truncate text-xs text-sidebar-muted">
        <span className="font-medium text-sidebar-foreground">{label}</span>
        {data?.version ? ` · v${data.version}` : ""}
        {data?.cache_ok === false ? " · cache off" : ""}
      </p>
    </div>
  );
}
