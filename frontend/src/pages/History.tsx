import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BadgeCheck,
  Cloud,
  Library,
  Link2,
  Package,
  Plus,
  Search,
  Target,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { HistoryRow } from "@/components/history/HistoryRow";
import { HistoryDetail } from "@/components/history/HistoryDetail";
import { DeleteRunsDialog, LinkVideoDialog, RelinkConfirmDialog } from "@/components/history/HistoryDialogs";
import {
  cloudDeletionNote,
  MAX_BULK_DELETE,
  useDeleteRuns,
  useHistoryRun,
  useHistoryRuns,
  useLinkVideo,
} from "@/hooks/useHistory";
import { useSelectedId } from "@/hooks/useSelection";
import { ApiError, apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { matchesQuery, resultSummary, runTitle, savedCountLabel } from "@/lib/historyFormat";
import { UNAVAILABLE } from "@/lib/utils";
import { toFiniteNumber } from "@/lib/format";
import type { HistoryRun, RelinkConflict } from "@/api/historyTypes";

function LibraryStat({
  icon: Icon,
  label,
  value,
  pending,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  pending: boolean;
}) {
  return (
    <div className="flex items-center gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-card">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand ring-1 ring-inset ring-brand-border" aria-hidden="true">
        <Icon className="size-4.5" />
      </span>
      <div className="min-w-0">
        {pending ? (
          <Skeleton className="h-6 w-12" />
        ) : (
          <p
            className={
              value === UNAVAILABLE
                ? "text-sm font-medium text-muted-foreground"
                : "font-display text-2xl font-semibold leading-none tracking-tight text-foreground"
            }
          >
            {value}
          </p>
        )}
        <p className="mt-1 truncate text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

/** The package a link dialog is for: from its row, or from the open detail. */
interface LinkTarget {
  id: number;
  isRelink: boolean;
}

export default function HistoryPage() {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleteTargets, setDeleteTargets] = useState<number[] | null>(null);
  const [linkTarget, setLinkTarget] = useState<LinkTarget | null>(null);
  const [relink, setRelink] = useState<{ videoId: string; conflict: RelinkConflict } | null>(null);

  // The open package lives in the URL (`?run=12`), so the Dashboard, Ideas,
  // Audits and Channel can link straight to one and a reload keeps it open.
  const { selectedId: openRunId, select: setOpenRunId } = useSelectedId("run");

  const runsQuery = useHistoryRuns();
  const detailQuery = useHistoryRun(openRunId);
  const deleteRuns = useDeleteRuns();
  const linkVideo = useLinkVideo();

  const runs = useMemo(() => runsQuery.data?.runs ?? [], [runsQuery.data]);
  const total = runsQuery.data?.total ?? runs.length;
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
        `${count === 1 ? "Saved package deleted." : `${count} packages deleted.`} ${cloudDeletionNote(result?.cloud_sync, count)}`,
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
  }, [deleteTargets, deleteRuns, openRunId, setOpenRunId]);

  const linkTo = useCallback(
    async (runId: number, youtubeVideoId: string, replaceExistingEvidence = false) => {
      try {
        const result = await linkVideo.mutateAsync({ runId, youtubeVideoId, replaceExistingEvidence });
        toast.success(result?.ownership_message || "Package linked to YouTube Video ID.");
        // Linked, but its first analytics read failed: say so rather than imply fresh numbers.
        if (result?.refresh_warning) toast.warning(result.refresh_warning);
        setLinkTarget(null);
        setRelink(null);
      } catch (error) {
        if (error instanceof ApiError && error.code === "relink_would_delete_evidence") {
          // Replacing the link deletes the old video's evidence, so ask first.
          setRelink({ videoId: youtubeVideoId, conflict: (error.details as RelinkConflict) ?? {} });
          return;
        }
        toast.error(formatApiError(error, "Could not link video."));
      }
    },
    [linkVideo],
  );

  const bulkCapped = selectedIds.size > MAX_BULK_DELETE;
  const withSelection = runs.filter((run) => run.selected_package_id).length;
  const linked = runs.filter((run) => run.linked_youtube_video_id).length;
  const scored = runs
    .map((run) => toFiniteNumber(run.opportunity_score))
    .filter((value): value is number => value !== null);
  // Whole numbers, as the Dashboard shows opportunity; unmeasured runs are left out.
  const avgOpportunity = scored.length
    ? String(Math.round(scored.reduce((sum, value) => sum + value, 0) / scored.length))
    : UNAVAILABLE;
  const openRun = runs.find((run) => run.id === openRunId);
  const partial = runs.length < total;
  // Without a loaded list the counts are unknown, not zero.
  const loaded = Boolean(runsQuery.data);
  const countText = (value: number) => (loaded ? value.toLocaleString() : UNAVAILABLE);

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Studio"
        icon={Library}
        title="Package library"
        description="Review the exact metadata, script, and publishing plan saved for every generation. Link a package after it is published to keep its performance history together."
        actions={
          <>
            {runsQuery.isSuccess ? (
              <EvidenceChip tone="info">{savedCountLabel(total)}</EvidenceChip>
            ) : runsQuery.isError ? (
              <EvidenceChip tone="bad">Records unavailable</EvidenceChip>
            ) : (
              <EvidenceChip tone="neutral">Loading records</EvidenceChip>
            )}
            <Button variant="gradient" size="sm" asChild>
              <Link to="/creator">
                <Plus aria-hidden="true" />
                New package
              </Link>
            </Button>
          </>
        }
      />

      <div className="space-y-5">
        <section aria-label="Library summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <LibraryStat icon={Package} label="Total packages" value={countText(total)} pending={runsQuery.isPending} />
          <LibraryStat icon={BadgeCheck} label="With a recorded choice" value={countText(withSelection)} pending={runsQuery.isPending} />
          <LibraryStat icon={Link2} label="Linked to YouTube" value={countText(linked)} pending={runsQuery.isPending} />
          <LibraryStat icon={Target} label="Avg opportunity" value={loaded ? avgOpportunity : UNAVAILABLE} pending={runsQuery.isPending} />
        </section>
        {partial ? (
          <p className="text-xs text-muted-foreground">
            Showing the newest {runs.length.toLocaleString()} of {total.toLocaleString()} saved packages; search and
            the figures above cover those. Older packages still open from a link.
          </p>
        ) : null}

        <Card className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div className="space-y-0.5">
              <h2 className="font-display text-base font-semibold text-foreground">Saved packages</h2>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Cloud className="size-3.5 shrink-0" aria-hidden="true" />
                {/* Only the summary is announced: wrapping the list would re-read every row on each refetch. */}
                <span data-testid="history-result-summary" aria-live="polite">
                  {runsQuery.isPending
                    ? "Loading saved packages…"
                    : runsQuery.isError
                      ? "Could not load saved packages."
                      : resultSummary(runs.length, visibleRuns.length, query)}
                </span>
                <span className="hidden md:inline">· stored locally, synced when cloud sync is on</span>
              </p>
            </div>
            <div className="relative sm:w-80">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
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
                className="pl-9"
              />
            </div>
          </div>

          {runs.length > 0 ? (
            <div
              role="toolbar"
              aria-label="Bulk actions for saved packages"
              className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/40 px-4 py-2.5 sm:px-5"
            >
              <label className="flex cursor-pointer items-center gap-2.5 text-[0.8125rem] font-medium text-foreground">
                <Checkbox
                  checked={allVisibleSelected ? true : someVisibleSelected ? "indeterminate" : false}
                  onCheckedChange={(value) => toggleAllVisible(value === true)}
                  aria-label="Select visible packages"
                />
                Select visible
              </label>
              <span className="rounded-full bg-card px-2.5 py-0.5 text-xs text-muted-foreground ring-1 ring-inset ring-border">
                {selectedIds.size} selected
              </span>
              {bulkCapped ? (
                <EvidenceChip tone="warn">
                  Only the first {MAX_BULK_DELETE} will be deleted
                </EvidenceChip>
              ) : null}
              <Button
                size="sm"
                variant="danger"
                disabled={selectedIds.size === 0}
                onClick={() => setDeleteTargets([...selectedIds].slice(0, MAX_BULK_DELETE))}
                className="ml-auto"
              >
                <Trash2 aria-hidden="true" />
                Delete selected
              </Button>
            </div>
          ) : null}

          <div>
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
                  icon={runs.length ? Search : Library}
                  title={runs.length ? "No matching packages" : "No saved packages yet"}
                  description={
                    runs.length
                      ? "No saved packages match your search."
                      : "No saved packages yet. Generate an SEO package and it will appear here."
                  }
                  action={
                    runs.length ? undefined : (
                      <Button variant="gradient" asChild>
                        <Link to="/creator">
                          <Plus aria-hidden="true" />
                          Create your first package
                        </Link>
                      </Button>
                    )
                  }
                />
              </div>
            ) : (
              visibleRuns.map((run: HistoryRun) => (
                <HistoryRow
                  key={run.id}
                  run={run}
                  selected={selectedIds.has(run.id)}
                  isOpen={openRunId === run.id}
                  onToggleSelect={(checked) => toggleSelection(run.id, checked)}
                  onOpen={() => setOpenRunId(run.id)}
                  onLink={() => setLinkTarget({ id: run.id, isRelink: Boolean(run.linked_youtube_video_id) })}
                  onDelete={() => setDeleteTargets([run.id])}
                />
              ))
            )}
          </div>
        </Card>
      </div>

      <HistoryDetail
        open={openRunId !== null}
        run={detailQuery.data ?? null}
        fallbackTitle={openRun ? runTitle(openRun) : undefined}
        isLoading={detailQuery.isPending}
        error={detailQuery.error}
        onClose={() => setOpenRunId(null)}
        onLink={() => {
          // The detail is the source: a package opened from a link may be older than the loaded list.
          const detail = detailQuery.data;
          if (detail) setLinkTarget({ id: detail.id, isRelink: Boolean(detail.linked_video_report?.linked) });
        }}
      />

      <DeleteRunsDialog
        open={Boolean(deleteTargets?.length)}
        count={deleteTargets?.length ?? 0}
        linked={runs.filter((run) => deleteTargets?.includes(run.id) && run.linked_youtube_video_id).length}
        pending={deleteRuns.isPending}
        onConfirm={handleDelete}
        onOpenChange={(open) => {
          if (!open) setDeleteTargets(null);
        }}
      />

      <LinkVideoDialog
        open={Boolean(linkTarget) && relink === null}
        isRelink={Boolean(linkTarget?.isRelink)}
        pending={linkVideo.isPending}
        onSubmit={(videoId) => {
          if (linkTarget) void linkTo(linkTarget.id, videoId);
        }}
        onOpenChange={(open) => {
          if (!open) setLinkTarget(null);
        }}
      />

      <RelinkConfirmDialog
        conflict={relink?.conflict ?? null}
        newVideoId={relink?.videoId ?? ""}
        pending={linkVideo.isPending}
        onConfirm={() => {
          if (linkTarget && relink) void linkTo(linkTarget.id, relink.videoId, true);
        }}
        onCancel={() => {
          // Nothing was changed; the package stays linked to its current video.
          setRelink(null);
          setLinkTarget(null);
        }}
      />
    </div>
  );
}
