import { useEffect, useMemo } from "react";
import { TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { DemandForm } from "@/components/demand/DemandForm";
import { SnapshotDetail } from "@/components/demand/SnapshotDetail";
import { SnapshotList } from "@/components/demand/SnapshotList";
import { DEMAND_PAGE_SIZE, useDemandSnapshot, useDemandSnapshots } from "@/hooks/useDemand";
import { useSelectedId } from "@/hooks/useSelection";
import { offsetParam, useUrlState } from "@/hooks/useUrlState";
import { asArray } from "@/lib/utils";
import type { DemandSnapshot } from "@/api/researchTypes";

/**
 * Demand explorer: research a topic, keep a dated snapshot of what was
 * observed, and turn a promising topic into a package. The selected snapshot
 * and the list's page live in the URL (`?snapshot=`, `?offset=`), so they can
 * be linked to and survive a reload.
 */
export default function DemandPage() {
  const { selectedId, select, detailRef } = useSelectedId("snapshot");
  const url = useUrlState();
  const setUrl = url.set;
  const offset = offsetParam(url.get("offset"));

  const list = useDemandSnapshots(offset);
  const detail = useDemandSnapshot(selectedId);
  const snapshots = useMemo(() => asArray<DemandSnapshot>(list.data?.research), [list.data]);

  // Prefer the list's copy while the single snapshot loads: it is the same record.
  const selected =
    detail.data?.research ?? snapshots.find((snapshot) => snapshot.id === selectedId) ?? null;
  const total = typeof list.data?.total === "number" ? list.data.total : snapshots.length;

  // An offset past the end (an old link, a hand-edited URL) shows an empty
  // page with no way back; step back to the last page instead, as Ideas does.
  useEffect(() => {
    if (!list.isPlaceholderData && list.isSuccess && !snapshots.length && offset > 0) {
      setUrl({ offset: Math.max(0, Math.floor((total - 1) / DEMAND_PAGE_SIZE) * DEMAND_PAGE_SIZE) || null });
    }
  }, [snapshots.length, list.isPlaceholderData, list.isSuccess, offset, total, setUrl]);

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Research lab"
        icon={TrendingUp}
        title="Demand"
        description="See how much interest a topic shows before you film it. Every result is a dated snapshot of what YouTube showed that day, with no invented search volume."
        actions={
          list.isSuccess ? (
            <EvidenceChip tone="info">
              {total} {total === 1 ? "snapshot" : "snapshots"}
            </EvidenceChip>
          ) : null
        }
      />

      <div className="space-y-5">
        {/* A new snapshot is the newest, so it lands on the first page. */}
        <DemandForm onResearched={(snapshot) => select(snapshot.id, { offset: null })} />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <SnapshotList
            snapshots={snapshots}
            total={total}
            offset={offset}
            pageSize={DEMAND_PAGE_SIZE}
            onOffsetChange={(next) => url.set({ offset: next || null })}
            isPending={list.isPending}
            error={list.error}
            isFetching={list.isFetching}
            selectedId={selectedId}
            onSelect={select}
            onRefresh={() => void list.refetch()}
          />
          <div ref={detailRef} className="min-w-0 scroll-mt-24">
            <SnapshotDetail
              snapshot={selected}
              isLoading={detail.isPending && selectedId !== null}
              error={detail.error}
              hasSelection={selectedId !== null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
