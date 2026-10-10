import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The page's title block. The `<h1>` holds only the page name — tests and
 * assistive tech find pages by it — while the eyebrow and description sit
 * around it.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  icon: Icon,
  actions,
  className,
  compact = false,
}: {
  title: string;
  description?: React.ReactNode;
  eyebrow?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <header
      className={cn(
        "mb-7 flex flex-col gap-4 sm:mb-8 md:flex-row md:items-end md:justify-between",
        compact && "mb-4 shrink-0 gap-2 sm:mb-4",
        className,
      )}
    >
      <div className={cn("min-w-0 space-y-2", compact && "space-y-1")}>
        {eyebrow ? (
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-brand">
            {Icon ? <Icon className="size-3.5" aria-hidden="true" /> : null}
            {eyebrow}
          </p>
        ) : null}
        <h1 className={cn("font-display text-3xl font-semibold tracking-tight text-foreground sm:text-[2.5rem] sm:leading-[1.1]", compact && "text-2xl sm:text-[1.75rem] sm:leading-tight")}>
          {title}
        </h1>
        {description ? (
          <p className={cn("max-w-2xl text-[0.9375rem] leading-relaxed text-muted-foreground", compact && "max-w-4xl text-[0.8125rem] leading-normal")}>
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
