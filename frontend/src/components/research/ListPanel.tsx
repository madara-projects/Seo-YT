import type { LucideIcon } from "lucide-react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { cn } from "@/lib/utils";

/** A list's records, or an honest loading, error or empty state in their place. */
export function ListBody({
  isPending,
  error,
  errorFallback,
  onRetry,
  isEmpty,
  empty,
  children,
}: {
  isPending: boolean;
  error: unknown;
  errorFallback: string;
  onRetry: () => void;
  isEmpty: boolean;
  empty: React.ReactNode;
  children?: React.ReactNode;
}) {
  if (isPending) {
    return (
      <div className="px-2 pb-2">
        <CardSkeleton rows={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="px-2 pb-2">
        <ErrorState message={apiErrorMessage(error, errorFallback)} requestId={apiRequestId(error)} onRetry={onRetry} />
      </div>
    );
  }
  if (isEmpty) {
    return (
      <div className="px-2 pb-2">
        <UnavailableNote>{empty}</UnavailableNote>
      </div>
    );
  }
  return <>{children}</>;
}

/**
 * The list half of a research page: its filters, then the records. It stays
 * in view beside a long inspector on wide screens. Pass `list` for a single
 * list; omit it and render `ListBody`s yourself when the panel holds tabs.
 */
export function ListPanel({
  icon,
  title,
  description,
  refreshLabel,
  onRefresh,
  isFetching,
  list,
  toolbar,
  footer,
  children,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  refreshLabel: string;
  onRefresh: () => void;
  isFetching: boolean;
  list?: Omit<React.ComponentProps<typeof ListBody>, "onRetry" | "children">;
  toolbar?: React.ReactNode;
  footer?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <Panel
      className={cn("lg:sticky lg:top-24 lg:self-start", className)}
      icon={icon}
      title={title}
      description={description}
      aside={
        <Button variant="ghost" size="icon-sm" onClick={onRefresh} disabled={isFetching} aria-label={refreshLabel}>
          <RefreshCw className={cn(isFetching && "animate-spin")} aria-hidden="true" />
        </Button>
      }
      contentClassName="px-3 pb-3 sm:px-3 sm:pb-3"
    >
      {toolbar ? <div className="space-y-2 px-2 pb-3">{toolbar}</div> : null}
      {list ? (
        <ListBody {...list} onRetry={onRefresh}>
          {children}
        </ListBody>
      ) : (
        children
      )}
      {footer}
    </Panel>
  );
}

/** The scrolling list inside a `ListPanel`. */
export function RecordList({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <ul className="max-h-[36rem] space-y-1 overflow-y-auto scrollbar-thin" aria-label={label}>
      {children}
    </ul>
  );
}
