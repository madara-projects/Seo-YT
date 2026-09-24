import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-muted",
        "before:absolute before:inset-0 before:animate-shimmer before:bg-linear-to-r before:from-transparent before:via-foreground/[0.06] before:to-transparent",
        className,
      )}
      {...props}
    />
  );
}
