import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { cn } from "@/lib/utils";

interface Health {
  status?: string;
  version?: string;
  environment?: string;
  database_ok?: boolean;
  cache_ok?: boolean;
}

/**
 * Backend reachability in the sidebar. Polls slowly: this is an at-a-glance
 * reassurance, not a monitor, and the backend rate-limits per path.
 */
export function HealthIndicator() {
  const { data, isError, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiRequest<Health>("/health"),
    refetchInterval: 60_000,
    retry: 1,
  });

  const healthy = !isError && data?.status === "ok";
  const label = isPending ? "Checking" : isError ? "Unreachable" : healthy ? "Connected" : "Degraded";
  const tone = isPending
    ? "bg-muted-foreground"
    : healthy
      ? "bg-tone-ok"
      : isError
        ? "bg-tone-bad"
        : "bg-tone-warn";

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2">
      <span className={cn("h-2 w-2 shrink-0 rounded-full", tone)} aria-hidden="true" />
      <div className="min-w-0 leading-tight">
        <p className="text-[11px] font-semibold text-foreground">{label}</p>
        <p className="truncate text-[10px] text-muted-foreground">
          {data?.version ? `v${data.version}` : "Local backend"}
          {data?.cache_ok === false ? " · cache off" : ""}
        </p>
      </div>
    </div>
  );
}
