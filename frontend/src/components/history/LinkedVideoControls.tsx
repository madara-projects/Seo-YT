import { useRef, useState } from "react";
import { useMutationState } from "@tanstack/react-query";
import { RefreshCw, RotateCcw, Tags } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { FormField } from "@/components/common/FormField";
import { OptionSelect } from "@/components/common/OptionSelect";
import { formatApiError } from "@/api/client";
import { useRefreshLinkedVideo, useUpdateComparableMetadata } from "@/hooks/useHistory";
import { mutationKeys } from "@/hooks/queryKeys";
import {
  LABEL_FIELDS,
  LABEL_MAX_LENGTH,
  type LabelDraft,
  type LabelField,
  hasExhaustedWindows,
  labelChanges,
  labelDraft,
  labelErrors,
  labelOptions,
  labelText,
  learningStatus,
} from "@/lib/linkedVideoFormat";
import type { LinkedVideoReport } from "@/api/historyTypes";

function linkIdOf(report: LinkedVideoReport): number | null {
  return typeof report.link_id === "number" && report.link_id > 0 ? report.link_id : null;
}

/**
 * Collects the video's due windows now, from History rather than only from
 * Audits. "Retry failed windows" appears only when a window has used every
 * attempt; it asks the server to try each such window once more.
 */
export function LinkedVideoRefresh({ report }: { report: LinkedVideoReport }) {
  const linkId = linkIdOf(report);
  const refresh = useRefreshLinkedVideo(linkId);
  // Read from the mutation cache, so a refresh started before the panel was
  // reopened still disables both buttons and names itself.
  const pending = useMutationState({
    filters: { mutationKey: mutationKeys.recordAction("published-video", linkId ?? 0, "refresh"), status: "pending" },
    select: (mutation) => mutation.state.variables as { retryFailedWindows?: boolean } | undefined,
  });
  // Set before the first await, so a double click sends one request.
  const inFlight = useRef(false);
  const busy = pending.length > 0 || refresh.isPending;
  const retrying = pending.some((variables) => variables?.retryFailedWindows);
  const exhausted = hasExhaustedWindows(report.snapshots);

  if (!linkId) return null;

  const run = async (retryFailedWindows: boolean) => {
    if (busy || inFlight.current) return;
    inFlight.current = true;
    try {
      const result = await refresh.mutateAsync({ retryFailedWindows });
      toast.success(result.message || "Linked video data refreshed.");
    } catch (error) {
      toast.error(formatApiError(error, "The linked video could not be refreshed."));
    } finally {
      inFlight.current = false;
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Linked video data">
      <Button size="sm" variant="outline" onClick={() => void run(false)} disabled={busy}>
        <RefreshCw aria-hidden="true" className={busy && !retrying ? "animate-spin" : undefined} />
        {busy && !retrying ? "Refreshing…" : "Refresh data"}
      </Button>
      {exhausted ? (
        <Button size="sm" variant="outline" onClick={() => void run(true)} disabled={busy}>
          <RotateCcw aria-hidden="true" />
          {retrying ? "Retrying…" : "Retry failed windows"}
        </Button>
      ) : null}
      <span className="text-xs text-muted-foreground">
        {exhausted
          ? "A window stopped after its last attempt; retrying asks YouTube once more."
          : "Asks YouTube for any window that is due."}
      </span>
    </div>
  );
}

const FIELD_LABELS: Record<LabelField, string> = {
  language: "Language",
  format: "Format",
  duration_bucket: "Duration",
  topic_category: "Topic",
};

function LabelEditor({
  report,
  onDone,
}: {
  report: LinkedVideoReport;
  onDone: () => void;
}) {
  // The labels as the editor opened with them. Changes are measured against
  // these, not the latest report, so a reload while the editor is open (a
  // refresh or relink updating a package label) is never reverted by a label
  // the creator did not touch.
  const [opened] = useState(() => report.comparable_metadata ?? {});
  const save = useUpdateComparableMetadata(linkIdOf(report));
  const [draft, setDraft] = useState<LabelDraft>(() => labelDraft(opened));
  const errors = labelErrors(draft, opened);
  const changes = labelChanges(draft, opened);
  const changed = Object.keys(changes).length > 0;
  const invalid = Object.keys(errors).length > 0;
  const set = (field: LabelField) => (value: string) => setDraft((current) => ({ ...current, [field]: value }));
  // Set before the first await, so a double submit sends one request.
  const sending = useRef(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!changed || invalid || save.isPending || sending.current) return;
    sending.current = true;
    try {
      await save.mutateAsync(changes);
      toast.success("Learning labels saved.");
      onDone();
    } catch (error) {
      toast.error(formatApiError(error, "The labels could not be saved."));
    } finally {
      sending.current = false;
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} noValidate className="space-y-3" aria-label="Edit learning labels">
      <div className="grid gap-3 sm:grid-cols-2">
        {LABEL_FIELDS.map((field) => {
          const id = `labels-${report.link_id}-${field}`;
          return (
            <FormField key={field} id={id} label={FIELD_LABELS[field]} error={errors[field]}>
              {field === "topic_category" ? (
                <Input
                  id={id}
                  value={draft[field]}
                  maxLength={LABEL_MAX_LENGTH[field]}
                  placeholder="Unknown"
                  autoComplete="off"
                  aria-invalid={Boolean(errors[field])}
                  onChange={(event) => set(field)(event.target.value)}
                  disabled={save.isPending}
                />
              ) : (
                <OptionSelect
                  id={id}
                  ariaLabel={FIELD_LABELS[field]}
                  value={draft[field]}
                  onValueChange={set(field)}
                  options={labelOptions(field, draft[field])}
                  disabled={save.isPending}
                />
              )}
            </FormField>
          );
        })}
      </div>
      <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
        Videos are compared only when these match exactly, so use the same topic wording for every video on a topic.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={!changed || invalid || save.isPending}>
          {save.isPending ? "Saving…" : "Save labels"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone} disabled={save.isPending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/**
 * Whether the video is used for learning and, when it is left out for a label
 * nobody set, an editor to set it (the creator's edits are kept over the
 * package's values on a relink).
 */
export function LearningLabels({ report }: { report: LinkedVideoReport }) {
  const [editing, setEditing] = useState(false);
  const status = learningStatus(report);
  const labels = labelDraft(report.comparable_metadata);
  const editable = linkIdOf(report) !== null;

  return (
    <div className="space-y-2 border-t border-border pt-3" data-testid="learning-labels">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
          <Tags className="size-3.5 text-muted-foreground" aria-hidden="true" />
          {status.title}
        </p>
        {status.excluded === true ? (
          <EvidenceChip tone="warn">Excluded</EvidenceChip>
        ) : status.excluded === false ? (
          <EvidenceChip tone="ok">Included</EvidenceChip>
        ) : null}
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{status.body}</p>
      {editing ? (
        <LabelEditor report={report} onDone={() => setEditing(false)} />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {LABEL_FIELDS.map((field) => (
              <div key={field} className="flex gap-1">
                <dt className="text-muted-foreground">{FIELD_LABELS[field]}:</dt>
                <dd className={labels[field] ? "text-foreground" : "text-tone-warn"}>{labelText(field, labels[field])}</dd>
              </div>
            ))}
          </dl>
          {editable ? (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Edit labels
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}
