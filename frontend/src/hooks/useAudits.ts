import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { AuditDetailResponse, AuditListResponse, AuditRefreshResponse } from "@/api/auditTypes";
import { auditKeys, historyKeys, mutationKeys } from "./queryKeys";

export function useAuditCandidates(auditState: string, evidenceState: string) {
  return useQuery({
    queryKey: auditKeys.list(auditState, evidenceState),
    queryFn: ({ signal }) => {
      const params = new URLSearchParams();
      if (auditState) params.set("audit_state", auditState);
      if (evidenceState) params.set("evidence_state", evidenceState);
      const search = params.toString();
      return apiRequest<AuditListResponse>(`/api/audits${search ? `?${search}` : ""}`, { signal });
    },
  });
}

export function useAudit(linkId: number | null) {
  return useQuery({
    queryKey: auditKeys.detail(linkId ?? 0),
    queryFn: ({ signal }) => apiRequest<AuditDetailResponse>(`/api/audits/${linkId}`, { signal }),
    enabled: typeof linkId === "number" && linkId > 0,
  });
}

/**
 * Reads the video from the connected channel, captures any due analytics
 * windows, and saves a new audit version. Spends quota; never retried. Keyed
 * by the video, so its panel finds a refresh still running after switching.
 */
export function useRefreshAudit(linkId: number) {
  const queryClient = useQueryClient();
  return useMutation<AuditRefreshResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("audit", linkId, "refresh"),
    retry: false,
    mutationFn: (id) => apiRequest<AuditRefreshResponse>(`/api/audits/${id}/refresh`, { method: "POST" }),
    onSuccess: (data, id) => {
      queryClient.setQueryData(auditKeys.detail(id), {
        audit: data.audit,
        versions: data.versions,
        status: data.audit ? "available" : "not_run",
      });
      void queryClient.invalidateQueries({ queryKey: auditKeys.lists() });
      // The refresh also updates the linked video's metadata and snapshots.
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}
