import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium",
    "transition-[color,background-color,border-color,box-shadow,filter,transform] duration-150",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    "disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
    "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[inset_0_1px_0_oklch(1_0_0/0.16),0_1px_2px_oklch(0.2_0.06_286/0.3)] hover:bg-primary/90",
        gradient:
          "bg-cta-gradient text-white shadow-[inset_0_1px_0_oklch(1_0_0/0.2),0_8px_24px_-10px_oklch(0.5_0.25_300/0.7)] hover:brightness-110",
        outline:
          "border border-border bg-card text-foreground shadow-[0_1px_2px_oklch(0.2_0.03_286/0.05)] hover:border-foreground/20 hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/70",
        soft: "bg-brand-soft text-brand hover:bg-brand-soft/70",
        ghost: "text-muted-foreground hover:bg-accent hover:text-foreground",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        danger:
          "border border-transparent text-tone-bad hover:border-tone-bad-border hover:bg-tone-bad-bg",
        link: "h-auto px-0 text-brand underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4",
        xs: "h-7 rounded-lg px-2.5 text-xs [&_svg]:size-3.5",
        sm: "h-8 rounded-lg px-3 text-xs [&_svg]:size-3.5",
        lg: "h-11 px-5 text-[0.9375rem]",
        xl: "h-12 rounded-2xl px-6 text-[0.9375rem] font-semibold",
        icon: "size-9",
        "icon-sm": "size-8 rounded-lg",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button };
