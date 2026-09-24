import { cn } from "@/lib/utils";

/**
 * A horizontal proportion bar with an accessible value. The number is always
 * printed next to it by the caller, so the bar is never the only carrier.
 */
export function Meter({
  value,
  max,
  label,
  tone = "brand",
  className,
  size = "md",
}: {
  value: number | null;
  max: number;
  label: string;
  tone?: "brand" | "ok" | "warn" | "info" | "bad" | "muted";
  className?: string;
  size?: "sm" | "md";
}) {
  const safeMax = max > 0 ? max : 1;
  const ratio = value === null ? 0 : Math.max(0, Math.min(1, value / safeMax));

  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-valuenow={value ?? undefined}
      aria-valuetext={value === null ? "Unavailable" : undefined}
      className={cn(
        "w-full overflow-hidden rounded-full bg-muted",
        size === "sm" ? "h-1.5" : "h-2",
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500",
          tone === "brand" && "bg-brand-gradient",
          tone === "ok" && "bg-tone-ok",
          tone === "warn" && "bg-tone-warn",
          tone === "info" && "bg-tone-info",
          tone === "bad" && "bg-tone-bad",
          tone === "muted" && "bg-muted-foreground/50",
        )}
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  );
}
