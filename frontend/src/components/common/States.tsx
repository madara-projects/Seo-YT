import { AlertTriangle, Inbox } from "lucide-react";
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
        "relative flex flex-col items-center justify-center gap-4 overflow-hidden rounded-2xl border border-dashed border-border bg-card/50 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 bg-dots opacity-60 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" aria-hidden="true" />
      <div className="relative isolate">
        <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-brand-gradient opacity-15 blur-xl" aria-hidden="true" />
        <span className="grid size-12 place-items-center rounded-2xl border border-border bg-card text-brand shadow-card">
          <Icon className="size-5" aria-hidden="true" />
        </span>
      </div>
      <div className="relative space-y-1.5">
        <p className="font-display text-base font-semibold text-foreground">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-[0.8125rem] leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="relative">{action}</div> : null}
    </div>
  );
}

export function UnavailableNote({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-border bg-muted/40 px-3.5 py-3 text-[0.8125rem] leading-relaxed text-muted-foreground",
        className,
      )}
    >
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
        "flex flex-col gap-3 rounded-2xl border border-tone-bad-border bg-tone-bad-bg p-4 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-card/70 text-tone-bad">
          <AlertTriangle className="size-4" aria-hidden="true" />
        </span>
        <div className="space-y-0.5 pt-1">
          <p className="text-sm font-medium text-foreground">{message}</p>
          {requestId ? (
            <p className="numeric text-[0.6875rem] text-muted-foreground">Request ID: {requestId}</p>
          ) : null}
        </div>
      </div>
      {onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry} className="self-start sm:self-center">
          Try again
        </Button>
      ) : null}
    </div>
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
        <div key={index} className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="flex items-center gap-2.5">
            <Skeleton className="size-7 rounded-lg" />
            <Skeleton className="h-3 w-24" />
          </div>
          <Skeleton className="mt-5 h-7 w-28" />
          <Skeleton className="mt-3 h-3 w-full" />
        </div>
      ))}
    </div>
  );
}

/** Full-page placeholder while a lazy route loads. */
export function PageSkeleton() {
  return (
    <div className="mx-auto w-full max-w-page space-y-6" role="status" aria-label="Loading page">
      <div className="space-y-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-full max-w-lg" />
      </div>
      <GridSkeleton cards={4} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-56 rounded-2xl" />
        <Skeleton className="h-56 rounded-2xl" />
      </div>
    </div>
  );
}
