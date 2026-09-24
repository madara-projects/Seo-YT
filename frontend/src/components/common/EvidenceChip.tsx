import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Provenance label.
 *
 * The product's core promise is that it never presents a guess as a
 * measurement, so every value on screen is paired with where it came from.
 * The tone is the meaning, not styling: `ok` is creator-supplied fact, `info`
 * is a public observation, `warn` is a heuristic or inference, and `bad` is a
 * failure. Keep them distinguishable by text as well as colour.
 */
const chipVariants = cva(
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4",
  {
    variants: {
      tone: {
        neutral: "border-border bg-muted text-muted-foreground",
        ok: "border-tone-ok-border bg-tone-ok-bg text-tone-ok",
        warn: "border-tone-warn-border bg-tone-warn-bg text-tone-warn",
        info: "border-tone-info-border bg-tone-info-bg text-tone-info",
        bad: "border-tone-bad-border bg-tone-bad-bg text-tone-bad",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type EvidenceTone = NonNullable<VariantProps<typeof chipVariants>["tone"]>;

interface EvidenceChipProps extends VariantProps<typeof chipVariants> {
  children: React.ReactNode;
  className?: string;
  title?: string;
}

export function EvidenceChip({ children, tone, className, title }: EvidenceChipProps) {
  return (
    <span className={cn(chipVariants({ tone }), className)} title={title}>
      <span className="size-1.5 shrink-0 rounded-full bg-current opacity-80" aria-hidden="true" />
      {children}
    </span>
  );
}

/** Maps the backend's provenance vocabulary onto a tone and a readable label. */
export function provenanceLabel(source: string): { label: string; tone: EvidenceTone } {
  switch (source) {
    case "creator_supplied":
      return { label: "Creator-entered", tone: "ok" };
    case "inferred":
      return { label: "Inferred", tone: "warn" };
    case "unavailable":
      return { label: "Unavailable", tone: "warn" };
    case "unknown":
      return { label: "Unknown", tone: "warn" };
    default:
      return { label: source || "Unknown", tone: "warn" };
  }
}

/** Legend explaining the tones, shown at the foot of evidence-heavy panels. */
export function SourceLegend({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-2xl border border-dashed border-border bg-card/60 px-4 py-3",
        className,
      )}
    >
      <span className="mr-1 text-xs font-medium text-muted-foreground">How to read the labels</span>
      <EvidenceChip tone="ok">Creator-entered</EvidenceChip>
      <EvidenceChip tone="info">Public observation</EvidenceChip>
      <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
      <EvidenceChip tone="warn">Inferred</EvidenceChip>
      <EvidenceChip tone="neutral">Unavailable</EvidenceChip>
    </div>
  );
}
