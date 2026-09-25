import { cn } from "@/lib/utils";

/**
 * One record in a list-and-inspector page. The open record is marked for
 * assistive tech with `aria-current` and visually with the gradient edge.
 */
export function SelectableItem({
  selected,
  onSelect,
  children,
  className,
  ...rest
}: {
  selected: boolean;
  onSelect: () => void;
  children: React.ReactNode;
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "type">) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "relative w-full rounded-xl px-3 py-3 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "bg-brand-soft/60 ring-1 ring-inset ring-brand-border" : "hover:bg-accent",
        className,
      )}
      {...rest}
    >
      {selected ? (
        <span className="absolute inset-y-3 left-0 w-1 rounded-r-full bg-brand-gradient" aria-hidden="true" />
      ) : null}
      {children}
    </button>
  );
}
