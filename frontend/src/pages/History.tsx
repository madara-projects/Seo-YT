import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { HistoryRow } from "@/components/history/HistoryRow";
import { HistoryDetail } from "@/components/history/HistoryDetail";
import { DeleteRunsDialog, LinkVideoDialog } from "@/components/history/HistoryDialogs";
import {
  cloudDeletionNote,
  MAX_BULK_DELETE,
  useDeleteRuns,
  useHistoryRun,
  useHistoryRuns,
  useLinkVideo,
} from "@/hooks/useHistory";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { matchesQuery, resultSummary, savedCountLabel } from "@/lib/historyFormat";
import { asArray } from "@/lib/utils";
import type { HistoryRun } from "@/api/historyTypes";

export default function HistoryPage() {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [openRunId, setOpenRunId] = useState<number | null>(null);
  const [deleteTargets, setDeleteTargets] = useState<number[] | null>(null);
  const [linkTarget, setLinkTarget] = useState<HistoryRun | null>(null);
  const selectAllRef = useRef<HTMLButtonElement>(null);

  const runsQuery = useHistoryRuns(50, 0);
  const detailQuery = useHistoryRun(openRunId);
  const deleteRuns = useDeleteRuns();
  const linkVideo = useLinkVideo();

  const runs = useMemo(
    () => asArray<HistoryRun>(runsQuery.data?.runs),
    [runsQuery.data],
  );
  const visibleRuns = useMemo(
    () => runs.filter((run) => matchesQuery(run, query)),
    [runs, query],
  );

  // Drop selections for runs that no longer exist after a refetch, mirroring
  // the legacy updateHistorySelectionControls reconciliation.
  useEffect(() => {
    setSelectedIds((current) => {
      if (!current.size) return current;
      const existing = new Set(runs.map((run) => run.id));
      const next = new Set([...current].filter((id) => existing.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [runs]);

  const selectedVisibleCount = visibleRuns.filter((run) => selectedIds.has(run.id)).length;
  const allVisibleSelected = visibleRuns.length > 0 && selectedVisibleCount === visibleRuns.length;
  const someVisibleSelected = selectedVisibleCount > 0 && !allVisibleSelected;

  // Radix renders a button, so the tri-state has to be set on the DOM node.
  useEffect(() => {
    const node = selectAllRef.current;
    if (node) node.dataset.indeterminate = String(someVisibleSelected);
  }, [someVisibleSelected]);

  const toggleSelection = useCallback((runId: number, checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(runId);
      else next.delete(runId);
      return next;
    });
  }, []);

  const toggleAllVisible = useCallback(
    (checked: boolean) => {
      setSelectedIds((current) => {
        const next = new Set(current);
        for (const run of visibleRuns) {
          if (checked) next.add(run.id);
          else next.delete(run.id);
        }
        return next;
      });
    },
    [visibleRuns],
  );

  const handleDelete = useCallback(async () => {
    if (!deleteTargets?.length) return;
    try {
      const result = await deleteRuns.mutateAsync(deleteTargets);
      const count = deleteTargets.length;
      toast.success(
        `${count === 1 ? "Saved package deleted." : `${count} packages deleted.`} ${cloudDeletionNote(result?.cloud_sync?.state)}`,
      );
      setSelectedIds((current) => {
        const next = new Set(current);
        deleteTargets.forEach((id) => next.delete(id));
        return next;
      });
      if (openRunId !== null && deleteTargets.includes(openRunId)) setOpenRunId(null);
      setDeleteTargets(null);
    } catch (error) {
      toast.error(formatApiError(error, "Could not delete selected package(s)."));
    }
  }, [deleteTargets, deleteRuns, openRunId]);

  const handleLink = useCallback(
    async (youtubeVideoId: string) => {
      if (!linkTarget) return;
      try {
        const result = (await linkVideo.mutateAsync({
          runId: linkTarget.id,
          youtubeVideoId,
        })) as { ownership_message?: string };
        toast.success(result?.ownership_message || "Package linked to YouTube Video ID.");
        setLinkTarget(null);
      } catch (error) {
        toast.error(formatApiError(error, "Could not link video."));
      }
    },
    [linkTarget, linkVideo],
  );

  const total = runs.length;
  const bulkCapped = selectedIds.size > MAX_BULK_DELETE;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Package library"
        description="Review the exact metadata, script, and publishing plan saved for every generation. Link a package after it is published to keep its performance history together."
        actions={
          runsQuery.isSuccess ? (
            <EvidenceChip tone="info">{savedCountLabel(total)}</EvidenceChip>
          ) : runsQuery.isError ? (
            <EvidenceChip tone="bad">Records unavailable</EvidenceChip>
          ) : (
            <EvidenceChip tone="neutral">Loading records</EvidenceChip>
          )
        }
      />

      <p className="mb-4 text-[11px] text-muted-foreground">
        Stored locally and synced when cloud sync is enabled.
      </p>

      <div className="space-y-4">
        <Card>
          <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-0.5">
              <p className="text-sm font-semibold text-foreground">Saved packages</p>
              <p className="text-[11px] text-muted-foreground" data-testid="history-result-summary">
                {runsQuery.isPending
                  ? "Loading saved packages…"
                  : runsQuery.isError
                    ? "Could not load saved packages."
                    : resultSummary(total, visibleRuns.length, query)}
              </p>
            </div>
            <div className="relative sm:w-72">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="history-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title or topic"
                aria-label="Search saved packages"
                autoComplete="off"
                className="pl-8"
              />
            </div>
          </div>

          {total > 0 ? (
            <div
              role="toolbar"
              aria-label="Bulk actions for saved packages"
              className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/30 px-4 py-2.5"
            >
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-foreground">
                <Checkbox
                  ref={selectAllRef}
                  checked={allVisibleSelected}
                  onCheckedChange={(value) => toggleAllVisible(value === true)}
                  aria-label="Select visible packages"
                />
                Select visible
              </label>
              <span className="text-[11px] text-muted-foreground">
                {selectedIds.size} selected
              </span>
              {bulkCapped ? (
                <EvidenceChip tone="warn">
                  Only the first {MAX_BULK_DELETE} will be deleted
                </EvidenceChip>
              ) : null}
              <Button
                size="sm"
                variant="outline"
                disabled={selectedIds.size === 0}
                onClick={() =>
                  setDeleteTargets([...selectedIds].slice(0, MAX_BULK_DELETE))
                }
                className="ml-auto text-tone-bad hover:bg-tone-bad-bg hover:text-tone-bad"
              >
                <Trash2 aria-hidden="true" />
                Delete selected
              </Button>
            </div>
          ) : null}

          <CardContent className="p-0" aria-live="polite">
            {runsQuery.isPending ? (
              <div className="p-5">
                <CardSkeleton rows={4} />
              </div>
            ) : runsQuery.isError ? (
              <div className="p-5">
                <ErrorState
                  message={apiErrorMessage(runsQuery.error, "Could not load saved packages.")}
                  requestId={apiRequestId(runsQuery.error)}
                  onRetry={() => void runsQuery.refetch()}
                />
              </div>
            ) : !visibleRuns.length ? (
              <div className="p-5">
                <EmptyState
                  title={total ? "No matching packages" : "No saved packages yet"}
                  description={
                    total
                      ? "No saved packages match your search."
                      : "No saved packages yet. Generate an SEO package and it will appear here."
                  }
                />
              </div>
            ) : (
              visibleRuns.map((run) => (
                <HistoryRow
                  key={run.id}
                  run={run}
                  selected={selectedIds.has(run.id)}
                  isOpen={openRunId === run.id}
                  onToggleSelect={(checked) => toggleSelection(run.id, checked)}
                  onOpen={() => setOpenRunId(run.id)}
                  onLink={() => setLinkTarget(run)}
                  onDelete={() => setDeleteTargets([run.id])}
                />
              ))
            )}
          </CardContent>
        </Card>

        {openRunId !== null ? (
          <HistoryDetail
            run={detailQuery.data ?? null}
            isLoading={detailQuery.isPending}
            error={detailQuery.error}
            onClose={() => setOpenRunId(null)}
            onLink={() => {
              const run = runs.find((item) => item.id === openRunId);
              if (run) setLinkTarget(run);
            }}
          />
        ) : null}
      </div>

      <DeleteRunsDialog
        open={Boolean(deleteTargets?.length)}
        count={deleteTargets?.length ?? 0}
        pending={deleteRuns.isPending}
        onConfirm={handleDelete}
        onOpenChange={(open) => {
          if (!open) setDeleteTargets(null);
        }}
      />

      <LinkVideoDialog
        open={Boolean(linkTarget)}
        isRelink={Boolean(linkTarget?.linked_youtube_video_id)}
        pending={linkVideo.isPending}
        onSubmit={handleLink}
        onOpenChange={(open) => {
          if (!open) setLinkTarget(null);
        }}
      />
    </div>
  );
}
