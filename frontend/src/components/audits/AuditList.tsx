import { BadgeCheck, ClipboardCheck } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { OptionSelect } from "@/components/common/OptionSelect";
import { SelectableItem } from "@/components/common/SelectableItem";
import { VideoThumb } from "@/components/common/VideoThumb";
import { ListPanel, RecordList } from "@/components/research/ListPanel";
import { formatCompact } from "@/lib/format";
import { shortDate } from "@/lib/historyFormat";
import {
  AUDIT_EVIDENCE_FILTERS,
  AUDIT_STATE_FILTERS,
  auditStateLabel,
  candidateTitle,
} from "@/lib/auditFormat";
import type { AuditCandidate } from "@/api/auditTypes";

export function AuditList({
  candidates,
  auditState,
  onAuditStateChange,
  evidenceState,
  onEvidenceStateChange,
  isPending,
  isFetching,
  error,
  selectedId,
  onSelect,
  onRefresh,
}: {
  candidates: AuditCandidate[];
  auditState: string;
  onAuditStateChange: (value: string) => void;
  evidenceState: string;
  onEvidenceStateChange: (value: string) => void;
  isPending: boolean;
  isFetching: boolean;
  error: unknown;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}) {
  const filtered = Boolean(auditState || evidenceState);
  return (
    <ListPanel
      icon={ClipboardCheck}
      title="Published videos"
      description="Packages you linked to a video in History."
      refreshLabel="Refresh published videos"
      onRefresh={onRefresh}
      isFetching={isFetching}
      toolbar={
        <div className="grid grid-cols-2 gap-2">
          <OptionSelect
            ariaLabel="Filter by audit state"
            value={auditState}
            onValueChange={onAuditStateChange}
            options={AUDIT_STATE_FILTERS}
          />
          <OptionSelect
            ariaLabel="Filter by performance evidence"
            value={evidenceState}
            onValueChange={onEvidenceStateChange}
            options={AUDIT_EVIDENCE_FILTERS}
          />
        </div>
      }
      list={{
        isPending,
        error,
        errorFallback: "Published videos are unavailable.",
        isEmpty: !candidates.length,
        empty: filtered
          ? "No published video matches these filters."
          : "No published videos yet. After you publish, use Link on the package in History and it will appear here.",
      }}
    >
      <RecordList label="Published videos">
        {candidates.map((candidate) => {
          const state = auditStateLabel(candidate.audit_state);
          const views = candidate.latest_performance?.views;
          return (
            <li key={candidate.id}>
              <SelectableItem
                selected={candidate.id === selectedId}
                onSelect={() => onSelect(candidate.id)}
                data-testid="audit-candidate"
                className="flex items-center gap-3"
              >
                <VideoThumb videoId={candidate.youtube_video_id} title={candidateTitle(candidate)} className="w-20" />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-foreground">
                    {candidateTitle(candidate)}
                  </span>
                  <span className="numeric mt-0.5 block text-[0.6875rem] text-muted-foreground">
                    {shortDate(candidate.published_at)}
                    {typeof views === "number" ? ` · ${formatCompact(views)} views` : ""}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5">
                    <EvidenceChip tone={state.tone}>{state.label}</EvidenceChip>
                    {candidate.ownership_verified ? (
                      <span className="inline-flex items-center gap-1 text-[0.6875rem] text-tone-ok">
                        <BadgeCheck className="size-3" aria-hidden="true" />
                        Verified
                      </span>
                    ) : null}
                  </span>
                </span>
              </SelectableItem>
            </li>
          );
        })}
      </RecordList>
    </ListPanel>
  );
}
