import { useCallback, useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { DemandForm } from "@/components/demand/DemandForm";
import { SnapshotDetail } from "@/components/demand/SnapshotDetail";
import { SnapshotList } from "@/components/demand/SnapshotList";
import { useDemandSnapshot, useDemandSnapshots } from "@/hooks/useDemand";
import { asArray } from "@/lib/utils";
import type { DemandSnapshot } from "@/api/researchTypes";

/**
 * Demand explorer: research a topic, keep a dated snapshot of what was
 * observed, and turn a promising topic into a package. The selected snapshot
 * lives in the URL (`?snapshot=`), so it can be linked to and survives a reload.
 */
export default function DemandPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = Number(searchParams.get("snapshot"));
  const selectedId = Number.isInteger(requested) && requested > 0 ? requested : null;
  const detailRef = useRef<HTMLDivElement>(null);

  const list = useDemandSnapshots();
  const detail = useDemandSnapshot(selectedId);
  const snapshots = useMemo(() => asArray<DemandSnapshot>(list.data?.research), [list.data]);

  const select = useCallback(
    (id: number) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set("snapshot", String(id));
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  // When the list and the inspector are stacked, bring the inspector into view.
  const pendingScroll = useRef(false);
  const selectAndReveal = useCallback(
    (id: number) => {
      pendingScroll.current = true;
      select(id);
    },
    [select],
  );
  useEffect(() => {
    if (!pendingScroll.current || selectedId === null) return;
    pendingScroll.current = false;
    if (window.matchMedia?.("(max-width: 63.99rem)").matches) {
      detailRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
  }, [selectedId]);

  // Prefer the list's copy while the single snapshot loads: it is the same record.
  const selected =
    detail.data?.research ?? snapshots.find((snapshot) => snapshot.id === selectedId) ?? null;
  const total = typeof list.data?.total === "number" ? list.data.total : snapshots.length;

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
        <DemandForm onResearched={(snapshot) => selectAndReveal(snapshot.id)} />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <SnapshotList
            snapshots={snapshots}
            isPending={list.isPending}
            error={list.error}
            isFetching={list.isFetching}
            selectedId={selectedId}
            onSelect={selectAndReveal}
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
