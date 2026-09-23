import { AlertTriangle, Inbox, Loader2, SearchX } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

/**
 * Shared empty / error / loading states.
 *
 * "Unavailable" is a real, meaningful result in this product — it means the
 * pipeline returned nothing it could evidence — so it gets a first-class state
 * rather than an empty div.
 */

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ElementType;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center",
        className,
      )}
    >
      <Icon className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function UnavailableNote({ children }: { children?: React.ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-border bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
      {children ?? "Unavailable — this field was not returned by the analysis pipeline."}
    </div>
  );
}

export function ErrorState({
  message,
  requestId,
  onRetry,
  className,
}: {
  message: string;
  requestId?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-tone-bad-border bg-tone-bad-bg p-4",
        className,
      )}
    >
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-tone-bad" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">{message}</p>
          {requestId ? (
            <p className="numeric text-[11px] text-muted-foreground">Request ID: {requestId}</p>
          ) : null}
        </div>
      </div>
      {onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry} className="self-start">
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function NoResults({ label = "No results" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-1 py-6 text-xs text-muted-foreground">
      <SearchX className="h-4 w-4" aria-hidden="true" />
      {label}
    </div>
  );
}

export function InlineSpinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      {label}
    </span>
  );
}

export function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-3 w-full" />
      ))}
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

export function GridSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      role="status"
      aria-label="Loading content"
    >
      {Array.from({ length: cards }).map((_, index) => (
        <div key={index} className="rounded-xl border border-border bg-card p-5">
          <CardSkeleton rows={2} />
        </div>
      ))}
    </div>
  );
}
