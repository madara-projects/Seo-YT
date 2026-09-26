import { useMemo, useState } from "react";
import { FlaskConical, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { PageHeader } from "@/components/common/PageHeader";
import { ExperimentDetail } from "@/components/experiments/ExperimentDetail";
import { ExperimentFormSheet } from "@/components/experiments/ExperimentFormSheet";
import { ExperimentList } from "@/components/experiments/ExperimentList";
import { useAuditCandidates } from "@/hooks/useAudits";
import { useExperiment, useExperiments } from "@/hooks/useExperiments";
import { useSelectedId } from "@/hooks/useSelection";
import { useUrlState } from "@/hooks/useUrlState";
import { useChannelStatus } from "@/hooks/useSystem";
import { asArray } from "@/lib/utils";
import type { AuditCandidate } from "@/api/auditTypes";
import type { Experiment } from "@/api/experimentTypes";

/**
 * Structured comparisons across the creator's own published videos. The open
 * comparison lives in the URL (`?experiment=`), so it can be linked to.
 */
export default function ExperimentsPage() {
  const { selectedId, select, detailRef } = useSelectedId("experiment");
  // The filters live in the URL too, so a reload or shared link keeps them.
  const url = useUrlState();
  const status = url.get("status");
  const mode = url.get("mode");
  const [formOpen, setFormOpen] = useState(false);

  const list = useExperiments(status, mode);
  const detail = useExperiment(selectedId);
  const channel = useChannelStatus();
  // Only verified videos from the connected channel can be assigned.
  const linked = useAuditCandidates("", "");

  const experiments = useMemo(() => asArray<Experiment>(list.data?.experiments), [list.data]);
  const candidates = useMemo(() => asArray<AuditCandidate>(linked.data?.candidates), [linked.data]);
  const connected = channel.data ? Boolean(channel.data.connected) : null;
  const channelId = channel.data?.channel?.id ?? null;
  const unfiltered = !status && !mode;
  const total = typeof list.data?.total === "number" ? list.data.total : experiments.length;

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Research lab"
        icon={FlaskConical}
        title="Experiments"
        description="Test one content decision at a time across your own published videos. Results use your verified YouTube analytics and never change your channel."
        actions={
          <>
            {connected === null ? null : connected ? (
              <EvidenceChip tone="ok">Channel connected</EvidenceChip>
            ) : (
              <EvidenceChip tone="warn">Channel not connected</EvidenceChip>
            )}
            <Button variant="gradient" onClick={() => setFormOpen(true)}>
              <Plus aria-hidden="true" />
              New experiment
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[23rem_minmax(0,1fr)] 2xl:grid-cols-[26rem_minmax(0,1fr)]">
        <ExperimentList
          experiments={experiments}
          status={status}
          onStatusChange={(value) => url.set({ status: value })}
          mode={mode}
          onModeChange={(value) => url.set({ mode: value })}
          isPending={list.isPending}
          isFetching={list.isFetching}
          error={list.error}
          selectedId={selectedId}
          onSelect={select}
          onRefresh={() => void list.refetch()}
        />
        <div ref={detailRef} className="min-w-0 scroll-mt-24">
          <ExperimentDetail
            experimentId={selectedId}
            detail={detail.data ?? null}
            isLoading={detail.isPending && selectedId !== null}
            error={detail.error}
            connected={connected}
            channelId={channelId}
            candidates={candidates}
            onNew={() => setFormOpen(true)}
            // Offer to start one only once the list is known to be empty.
            hasExperiments={!(list.isSuccess && unfiltered && total === 0)}
          />
        </div>
      </div>

      <ExperimentFormSheet
        open={formOpen}
        onOpenChange={setFormOpen}
        onCreated={(experiment) => {
          // Clear the filters so the new draft is listed, in one navigation.
          select(experiment.id, { status: null, mode: null });
        }}
      />
    </div>
  );
}
