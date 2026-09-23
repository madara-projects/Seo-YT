import { cn } from "@/lib/utils";
import { EvidenceChip, type EvidenceTone } from "./EvidenceChip";

/**
 * Compact analytics tile. `caption` is mandatory in spirit: a bare number in
 * this product is misleading without the note saying what it is and is not.
 */
export function StatCard({
  label,
  value,
  caption,
  tone,
  toneLabel,
  className,
}: {
  label: string;
  value: React.ReactNode;
  caption?: string;
  tone?: EvidenceTone;
  toneLabel?: string;
  className?: string;
}) {
  return (
    <div
      data-testid="stat-card"
      data-stat={label}
      className={cn("rounded-xl border border-border bg-card p-4", className)}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {toneLabel ? <EvidenceChip tone={tone}>{toneLabel}</EvidenceChip> : null}
      </div>
      <p className="numeric mt-2 text-xl font-bold text-foreground">{value}</p>
      {caption ? (
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{caption}</p>
      ) : null}
    </div>
  );
}
