import { cn } from "@/lib/utils";

/** The Win-Engine mark: a "W" drawn as a rising signal on the brand gradient. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative grid size-9 shrink-0 place-items-center overflow-hidden rounded-xl bg-brand-gradient shadow-[0_6px_18px_-6px_oklch(0.55_0.25_300/0.8)] ring-1 ring-inset ring-white/20",
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 32 32" className="size-[62%]" fill="none">
        <path
          d="M5 9.5 9 23l7-12.5L23 23l4-13.5"
          stroke="white"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="absolute inset-x-0 top-0 h-1/2 bg-white/15" />
    </span>
  );
}
