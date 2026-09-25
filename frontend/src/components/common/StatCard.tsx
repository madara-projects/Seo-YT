import type { LucideIcon } from "lucide-react";
import { cn, UNAVAILABLE } from "@/lib/utils";
import { EvidenceChip, type EvidenceTone } from "./EvidenceChip";
import { IconBadge, type IconBadgeTone } from "./IconBadge";

/**
 * Analytics tile. `caption` is mandatory in spirit: a bare number in this
 * product is misleading without the note saying what it is and is not.
 *
 * An unavailable value is rendered quieter than a real one, so a missing
 * measurement never looks like a headline figure. The label gets its own
 * line so it is never truncated to make room for the source chip.
 */
export function StatCard({
  label,
  value,
  caption,
  tone,
  toneLabel,
  icon,
  iconTone = "brand",
  footer,
  className,
}: {
  label: string;
  value: React.ReactNode;
  caption?: string;
  tone?: EvidenceTone;
  toneLabel?: string;
  icon?: LucideIcon;
  iconTone?: IconBadgeTone;
  footer?: React.ReactNode;
  className?: string;
}) {
  const unavailable = value === UNAVAILABLE;

  return (
    <div
      data-testid="stat-card"
      data-stat={label}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-card",
        className,
      )}
    >
      <div
        className="pointer-events-none absolute -right-10 -top-12 size-32 rounded-full bg-brand-gradient opacity-[0.07] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.14] dark:opacity-[0.12]"
        aria-hidden="true"
      />
      {icon || toneLabel ? (
        <div className="relative flex min-h-7 items-center justify-between gap-2">
          {icon ? <IconBadge icon={icon} tone={iconTone} size="sm" /> : <span />}
          {toneLabel ? <EvidenceChip tone={tone}>{toneLabel}</EvidenceChip> : null}
        </div>
      ) : null}
      <p className="relative mt-3 text-[0.8125rem] font-medium leading-snug text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "relative mt-1.5 break-words",
          unavailable
            ? "text-lg font-medium text-muted-foreground"
            : "font-display text-[1.75rem] font-semibold leading-tight tracking-tight text-foreground",
        )}
      >
        {value}
      </p>
      {footer ? <div className="relative mt-2">{footer}</div> : null}
      {caption ? (
        <p className="relative mt-auto pt-2 text-xs leading-relaxed text-muted-foreground">
          {caption}
        </p>
      ) : null}
    </div>
  );
}
