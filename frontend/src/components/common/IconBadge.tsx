import type { LucideIcon } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const iconBadgeVariants = cva("grid shrink-0 place-items-center ring-1 ring-inset", {
  variants: {
    tone: {
      brand: "bg-brand-soft text-brand ring-brand-border",
      ok: "bg-tone-ok-bg text-tone-ok ring-tone-ok-border",
      warn: "bg-tone-warn-bg text-tone-warn ring-tone-warn-border",
      info: "bg-tone-info-bg text-tone-info ring-tone-info-border",
      bad: "bg-tone-bad-bg text-tone-bad ring-tone-bad-border",
      neutral: "bg-muted text-muted-foreground ring-border",
      gradient: "bg-brand-gradient text-white ring-white/15",
    },
    size: {
      sm: "size-7 rounded-lg [&_svg]:size-3.5",
      md: "size-9 rounded-xl [&_svg]:size-4",
      lg: "size-11 rounded-2xl [&_svg]:size-5",
    },
  },
  defaultVariants: { tone: "brand", size: "md" },
});

export type IconBadgeTone = NonNullable<VariantProps<typeof iconBadgeVariants>["tone"]>;

/** A tinted square holding an icon; decorative, so hidden from assistive tech. */
export function IconBadge({
  icon: Icon,
  tone,
  size,
  className,
}: VariantProps<typeof iconBadgeVariants> & { icon: LucideIcon; className?: string }) {
  return (
    <span className={cn(iconBadgeVariants({ tone, size }), className)} aria-hidden="true">
      <Icon />
    </span>
  );
}
