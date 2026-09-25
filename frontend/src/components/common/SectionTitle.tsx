import type { LucideIcon } from "lucide-react";

/** A heading for a section inside a panel, with an optional chip or action. */
export function SectionTitle({
  children,
  icon: Icon,
  aside,
}: {
  children: React.ReactNode;
  icon?: LucideIcon;
  aside?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="inline-flex items-center gap-2 font-display text-sm font-semibold text-foreground">
        {Icon ? <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" /> : null}
        {children}
      </h3>
      {aside}
    </div>
  );
}
