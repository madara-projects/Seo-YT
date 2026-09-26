import { useRef } from "react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Asks before an action that cannot be undone from the app. Focus starts on
 * Cancel, so pressing Enter straight away never confirms it.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  icon: Icon,
  title,
  description,
  children,
  confirmLabel,
  pendingLabel,
  pending,
  destructive = false,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icon: LucideIcon;
  title: string;
  description: string;
  /** Detail shown between the description and the buttons, such as what would be lost. */
  children?: React.ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  pending: boolean;
  destructive?: boolean;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelRef.current?.focus();
        }}
      >
        <DialogHeader>
          <span
            className={
              destructive
                ? "mb-1 grid size-11 place-items-center rounded-2xl bg-tone-bad-bg text-tone-bad ring-1 ring-inset ring-tone-bad-border"
                : "mb-1 grid size-11 place-items-center rounded-2xl bg-tone-warn-bg text-tone-warn ring-1 ring-inset ring-tone-warn-border"
            }
            aria-hidden="true"
          >
            <Icon className="size-5" />
          </span>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
        <DialogFooter>
          <Button ref={cancelRef} variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} disabled={pending}>
            {pending ? pendingLabel : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
