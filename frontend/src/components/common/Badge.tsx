import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * A plain label for things that are not provenance — "Primary", "Legacy",
 * a keyboard hint. Evidence and status keep using `EvidenceChip`, whose
 * colours carry meaning.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[0.6875rem] font-medium leading-4",
  {
    variants: {
      variant: {
        brand: "bg-brand-soft text-brand ring-1 ring-inset ring-brand-border",
        neutral: "bg-muted text-muted-foreground ring-1 ring-inset ring-border",
        outline: "text-muted-foreground ring-1 ring-inset ring-border",
        solid: "bg-foreground text-background",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export function Badge({
  children,
  variant,
  className,
  title,
}: VariantProps<typeof badgeVariants> & {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} title={title}>
      {children}
    </span>
  );
}
