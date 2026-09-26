import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ClipboardCheck, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { PageHeader } from "@/components/common/PageHeader";
import { AuditDetail } from "@/components/audits/AuditDetail";
import { AuditList } from "@/components/audits/AuditList";
import { useAudit, useAuditCandidates } from "@/hooks/useAudits";
import { useSelectedId } from "@/hooks/useSelection";
import { useUrlState } from "@/hooks/useUrlState";
import { useChannelStatus } from "@/hooks/useSystem";
import { asArray } from "@/lib/utils";
import type { AuditCandidate } from "@/api/auditTypes";

/**
 * Post-publish audits: what went live against the package that was generated,
 * and how the video has performed since. The open video lives in the URL
 * (`?link=`, the History link's id), so it can be linked to.
 */
export default function AuditsPage() {
  const { selectedId, select, detailRef } = useSelectedId("link");
  // The filters live in the URL too, so a reload or shared link keeps them.
  const url = useUrlState();
  const auditState = url.get("state");
  const evidenceState = url.get("evidence");

  const list = useAuditCandidates(auditState, evidenceState);
  // The open video's facts come from the unfiltered list, so a filter that
  // hides it doesn't blank them. Without filters this is the same request.
  const lookup = useAuditCandidates("", "");
  const detail = useAudit(selectedId);
  const channel = useChannelStatus();
  const candidates = useMemo(() => asArray<AuditCandidate>(list.data?.candidates), [list.data]);
  const candidate = asArray<AuditCandidate>(lookup.data?.candidates).find((item) => item.id === selectedId);
  const connected = channel.data ? Boolean(channel.data.connected) : null;
  const total = typeof list.data?.total === "number" ? list.data.total : candidates.length;

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Research lab"
        icon={ClipboardCheck}
        title="Audits"
        description="Check what actually went live against the package you generated, and how each video has performed since. Every audit is a dated record, and none claims to know why a video performed."
        actions={
          <>
            {list.isSuccess && !auditState && !evidenceState ? (
              <EvidenceChip tone="info">
                {total} published {total === 1 ? "video" : "videos"}
              </EvidenceChip>
            ) : null}
            {connected === null ? null : connected ? (
              <EvidenceChip tone="ok">Channel connected</EvidenceChip>
            ) : (
              <EvidenceChip tone="warn">Channel not connected</EvidenceChip>
            )}
          </>
        }
      />

      {connected === false ? (
        <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-tone-warn-border bg-tone-warn-bg p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2.5 text-sm leading-relaxed text-foreground">
            <Unplug className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
            Connect your YouTube channel to run audits: each one reads the video from your channel. Saved audits and
            the list below work without it.
          </p>
          <Button variant="outline" size="sm" asChild className="shrink-0">
            <Link to="/channel">
              Connect your channel
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[23rem_minmax(0,1fr)]">
        <AuditList
          candidates={candidates}
          auditState={auditState}
          onAuditStateChange={(value) => url.set({ state: value })}
          evidenceState={evidenceState}
          onEvidenceStateChange={(value) => url.set({ evidence: value })}
          isPending={list.isPending}
          isFetching={list.isFetching}
          error={list.error}
          selectedId={selectedId}
          onSelect={select}
          onRefresh={() => void list.refetch()}
        />
        <div ref={detailRef} className="min-w-0 scroll-mt-24">
          <AuditDetail
            linkId={selectedId}
            candidate={candidate}
            detail={detail.data ?? null}
            // Wait for the video's facts too, rather than show them as unknown.
            isLoading={selectedId !== null && (detail.isPending || lookup.isPending)}
            error={detail.error}
            connected={connected}
          />
        </div>
      </div>
    </div>
  );
}
