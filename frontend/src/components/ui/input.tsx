import * as React from "react";
import { cn } from "@/lib/utils";

/** Shared field chrome, so inputs, textareas and select triggers match. */
export const fieldClasses = cn(
  "w-full rounded-xl border border-input bg-card text-sm text-foreground",
  "shadow-[0_1px_2px_oklch(0.2_0.03_286/0.04)] transition-[border-color,box-shadow]",
  "placeholder:text-muted-foreground/75 hover:border-foreground/20",
  "focus-visible:outline-none focus-visible:border-ring focus-visible:ring-4 focus-visible:ring-ring/15",
  "aria-[invalid=true]:border-tone-bad aria-[invalid=true]:focus-visible:ring-tone-bad/15",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(fieldClasses, "flex h-10 px-3.5 py-2", className)}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
