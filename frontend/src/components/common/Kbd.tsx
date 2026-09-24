import { cn } from "@/lib/utils";

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-border bg-muted px-1.5 font-sans text-[10px] font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

/** "⌘" on Apple platforms, "Ctrl" elsewhere. */
export function modifierKeyLabel(): string {
  if (typeof navigator === "undefined") return "Ctrl";
  const platform =
    (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ??
    navigator.platform ??
    "";
  return /mac|iphone|ipad|ipod/i.test(platform) ? "⌘" : "Ctrl";
}
