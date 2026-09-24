import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatSignedPercent } from "@/lib/format";

/**
 * A change indicator. Direction is carried by the arrow and the sign as well
 * as the colour. `unit` switches between a percentage and a raw difference.
 */
export function Delta({
  value,
  label,
  unit = "percent",
  digits = 1,
  className,
}: {
  value: number | null;
  label?: string;
  unit?: "percent" | "points";
  digits?: number;
  className?: string;
}) {
  if (value === null || !Number.isFinite(value)) {
    return label ? (
      <span className={cn("text-xs text-muted-foreground", className)}>{label}</span>
    ) : null;
  }

  const rounded = Number(value.toFixed(digits));
  const direction = rounded > 0 ? "up" : rounded < 0 ? "down" : "flat";
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  const text =
    unit === "percent"
      ? formatSignedPercent(value)
      : `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(rounded).toFixed(digits)}`;

  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-semibold tabular",
          direction === "up" && "bg-tone-ok-bg text-tone-ok",
          direction === "down" && "bg-tone-bad-bg text-tone-bad",
          direction === "flat" && "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="size-3" aria-hidden="true" />
        {text}
      </span>
      {label ? <span className="text-muted-foreground">{label}</span> : null}
    </span>
  );
}
