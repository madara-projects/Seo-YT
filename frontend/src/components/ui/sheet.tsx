import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";
import { DialogOverlay } from "./dialog";

/**
 * A panel that slides in from the right, for reading one record without
 * leaving the list behind it. Built on the Radix dialog, so focus is trapped
 * and Escape closes it.
 */
const Sheet = DialogPrimitive.Root;
const SheetClose = DialogPrimitive.Close;
const SheetTitle = DialogPrimitive.Title;
const SheetDescription = DialogPrimitive.Description;

const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex h-full w-full flex-col border-l border-border bg-background shadow-elevated sm:max-w-2xl",
        "focus-visible:outline-none data-[state=open]:animate-sheet-in",
        className,
      )}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

export { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle };
