import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Replaces the legacy `confirm()` / `prompt()` calls.
 *
 * The confirmation wording is preserved verbatim: it tells the creator that a
 * delete propagates to their other synced devices, which is the one
 * consequence they cannot undo from here.
 */
export function DeleteRunsDialog({
  open,
  count,
  pending,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  count: number;
  pending: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  const message =
    count === 1
      ? "Delete this saved package? It will be removed from this device and marked deleted for your synced devices."
      : `Delete ${count} selected packages? They will be removed locally and marked deleted in cloud sync for every synced device.`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-tone-bad" aria-hidden="true" />
            {count === 1 ? "Delete saved package" : `Delete ${count} packages`}
          </DialogTitle>
          <DialogDescription>{message}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={pending}>
            {pending ? "Deleting…" : count === 1 ? "Delete package" : `Delete ${count} packages`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Accepts a YouTube video ID or a URL. The backend requires at least 11
 * characters (a bare video ID), so the field enforces the same floor rather
 * than letting the request fail with a 422.
 */
export function LinkVideoDialog({
  open,
  isRelink,
  pending,
  onSubmit,
  onOpenChange,
}: {
  open: boolean;
  isRelink: boolean;
  pending: boolean;
  onSubmit: (videoId: string) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (open) setValue("");
  }, [open]);

  const trimmed = value.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < 11;
  const canSubmit = trimmed.length >= 11 && !pending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit) onSubmit(trimmed);
          }}
          className="space-y-4"
        >
          <DialogHeader>
            <DialogTitle>{isRelink ? "Change linked video" : "Link published video"}</DialogTitle>
            <DialogDescription>
              Enter the YouTube video ID or URL for the video you published from this package.
              Linking only records the association locally so performance evidence stays with the
              package — it does not change anything on YouTube.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="youtube-video-id">YouTube video ID or URL</Label>
            <Input
              id="youtube-video-id"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="dQw4w9WgXcQ or https://youtube.com/watch?v=…"
              autoFocus
              aria-invalid={tooShort}
              aria-describedby="youtube-video-id-help"
            />
            <p
              id="youtube-video-id-help"
              className={tooShort ? "text-[11px] text-tone-bad" : "text-[11px] text-muted-foreground"}
            >
              {tooShort
                ? "A YouTube video ID is at least 11 characters."
                : "Ownership is verified against your connected channel where possible."}
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={pending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {pending ? "Linking…" : isRelink ? "Update link" : "Link video"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
