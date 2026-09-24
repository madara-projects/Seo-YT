import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { IconBadge, type IconBadgeTone } from "./IconBadge";

/**
 * The standard content card: an icon, a title, an optional description and a
 * right-hand slot for a status chip or actions. Keeping every section on this
 * one shape is what makes the pages read as one product.
 */
export function Panel({
  title,
  description,
  icon,
  iconTone = "brand",
  aside,
  children,
  className,
  contentClassName,
  headingLevel = 2,
  ...rest
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: LucideIcon;
  iconTone?: IconBadgeTone;
  aside?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  headingLevel?: 2 | 3;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "title">) {
  const Heading = headingLevel === 2 ? "h2" : "h3";

  return (
    <Card className={cn("flex flex-col", className)} {...rest}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 p-5 pb-4 sm:px-6 sm:pt-6">
        <div className="flex min-w-0 items-start gap-3">
          {icon ? <IconBadge icon={icon} tone={iconTone} /> : null}
          <div className="min-w-0 space-y-1 pt-0.5">
            <Heading className="font-display text-base font-semibold leading-snug tracking-tight text-foreground">
              {title}
            </Heading>
            {description ? (
              <p className="text-[13px] leading-relaxed text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </div>
        {aside ? <div className="flex shrink-0 flex-wrap items-center gap-2">{aside}</div> : null}
      </div>
      {children !== undefined && children !== null ? (
        <div className={cn("flex-1 px-5 pb-5 sm:px-6 sm:pb-6", contentClassName)}>{children}</div>
      ) : null}
    </Card>
  );
}

/** A labelled value inside a panel. */
export function Field({
  label,
  children,
  className,
  mono = false,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
  mono?: boolean;
}) {
  return (
    <div className={cn("min-w-0 space-y-1", className)}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "break-words text-sm font-medium text-foreground",
          mono && "numeric text-[13px]",
        )}
      >
        {children}
      </dd>
    </div>
  );
}

/** A quiet inset surface for grouped detail inside a panel. */
export function Inset({
  children,
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-xl border border-border/80 bg-elevated p-3.5", className)}
      {...rest}
    >
      {children}
    </div>
  );
}
