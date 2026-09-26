import { useEffect, useState } from "react";
import { Link2, Trash2, TriangleAlert } from "lucide-react";
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
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { extractVideoId } from "@/schemas/watchlist";
import type { RelinkConflict } from "@/api/historyTypes";

/** What a delete also removes: every child row of a linked video cascades with its package. */
function linkedEvidenceNote(count: number, linked: number): string {
  if (linked <= 0) return "";
  if (count === 1) return " Its linked video's collected snapshots, audits and experiment assignments are deleted with it.";
  return ` ${linked === count ? "All of them are" : `${linked} of them are`} linked to a video; those videos' collected snapshots, audits and experiment assignments are deleted with them.`;
}

/**
 * Replaces the legacy `confirm()` call. It says that a delete propagates to
 * the creator's other synced devices, and what a linked video loses with it:
 * neither can be undone from here.
 */
export function DeleteRunsDialog({
  open,
  count,
  linked = 0,
  pending,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  count: number;
  /** How many of the packages are linked to a YouTube video. */
  linked?: number;
  pending: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      icon={Trash2}
      title={count === 1 ? "Delete saved package" : `Delete ${count} packages`}
      description={
        (count === 1
          ? "Delete this saved package? It will be removed from this device and marked deleted for your synced devices."
          : `Delete ${count} selected packages? They will be removed locally and marked deleted in cloud sync for every synced device.`) +
        linkedEvidenceNote(count, linked)
      }
      confirmLabel={count === 1 ? "Delete package" : `Delete ${count} packages`}
      pendingLabel="Deleting…"
      pending={pending}
      destructive
      onConfirm={onConfirm}
    />
  );
}

/**
 * Accepts a YouTube video ID or a link, read exactly as the backend reads it,
 * so an ID it would refuse is caught here rather than after a request.
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
  const videoId = extractVideoId(trimmed);
  const invalid = trimmed.length > 0 && videoId === null;
  const canSubmit = videoId !== null && !pending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit && videoId) onSubmit(videoId);
          }}
          className="space-y-5"
        >
          <DialogHeader>
            <span
              className="mb-1 grid size-11 place-items-center rounded-2xl bg-brand-soft text-brand ring-1 ring-inset ring-brand-border"
              aria-hidden="true"
            >
              <Link2 className="size-5" />
            </span>
            <DialogTitle>{isRelink ? "Change linked video" : "Link published video"}</DialogTitle>
            <DialogDescription>
              Enter the YouTube video ID or URL for the video you published from this package.
              Linking only records the association locally so performance evidence stays with the
              package — it does not change anything on YouTube.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="youtube-video-id">YouTube video ID or URL</Label>
            <Input
              id="youtube-video-id"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="dQw4w9WgXcQ or https://youtube.com/watch?v=…"
              autoFocus
              aria-invalid={invalid}
              aria-describedby="youtube-video-id-help"
            />
            <p
              id="youtube-video-id-help"
              className={invalid ? "text-xs text-tone-bad" : "text-xs text-muted-foreground"}
            >
              {invalid
                ? "Enter an 11-character video ID, or a youtube.com, youtu.be or Shorts link."
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

/** "3 snapshots", "1 audit": the evidence a relink would delete, in words. */
function evidenceLines(evidence: Record<string, number> | undefined): string[] {
  return Object.entries(evidence ?? {})
    .filter(([, count]) => typeof count === "number" && count > 0)
    .map(([label, count]) => {
      // The server's labels are plural nouns ("snapshots", "metadata edits").
      const noun = count === 1 ? label.replace(/s$/, "") : label;
      return `${count.toLocaleString()} ${noun}`;
    });
}

/**
 * The server refuses to relink a package whose current video has collected
 * evidence, because linking another video deletes it. This says what would be
 * lost and asks for an explicit, destructive confirmation.
 */
export function RelinkConfirmDialog({
  conflict,
  newVideoId,
  pending,
  onConfirm,
  onCancel,
}: {
  conflict: RelinkConflict | null;
  newVideoId: string;
  pending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const lines = evidenceLines(conflict?.evidence);
  const current = conflict?.youtube_video_id || "its current video";

  return (
    <ConfirmDialog
      open={conflict !== null}
      onOpenChange={(open) => (open ? undefined : onCancel())}
      icon={TriangleAlert}
      title="Replace the linked video?"
      description={`This package is linked to ${current}, which has collected evidence. Linking ${newVideoId} instead deletes that evidence for good; it can't be restored from the app.`}
      confirmLabel="Delete evidence and relink"
      pendingLabel="Relinking…"
      pending={pending}
      destructive
      onConfirm={onConfirm}
    >
      {lines.length ? (
        <div className="rounded-xl border border-tone-bad-border bg-tone-bad-bg px-3.5 py-3">
          <p className="text-xs font-medium text-foreground">What would be deleted</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-[0.8125rem] text-foreground">
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </ConfirmDialog>
  );
}
