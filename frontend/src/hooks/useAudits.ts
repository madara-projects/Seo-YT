import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { AuditDetailResponse, AuditListResponse, AuditRefreshResponse } from "@/api/auditTypes";
import { historyKeys } from "./useHistory";

export const auditKeys = {
  all: ["audits"] as const,
  lists: () => [...auditKeys.all, "list"] as const,
  list: (auditState: string, evidenceState: string) => [...auditKeys.lists(), auditState, evidenceState] as const,
  detail: (linkId: number) => [...auditKeys.all, "detail", linkId] as const,
};

export function useAuditCandidates(auditState: string, evidenceState: string) {
  return useQuery({
    queryKey: auditKeys.list(auditState, evidenceState),
    queryFn: () => {
      const params = new URLSearchParams();
      if (auditState) params.set("audit_state", auditState);
      if (evidenceState) params.set("evidence_state", evidenceState);
      const search = params.toString();
      return apiRequest<AuditListResponse>(`/api/audits${search ? `?${search}` : ""}`);
    },
  });
}

export function useAudit(linkId: number | null) {
  return useQuery({
    queryKey: auditKeys.detail(linkId ?? 0),
    queryFn: () => apiRequest<AuditDetailResponse>(`/api/audits/${linkId}`),
    enabled: typeof linkId === "number" && linkId > 0,
  });
}

/**
 * Reads the video from the connected channel, captures any due analytics
 * windows, and saves a new audit version. Spends quota; never retried.
 */
export function useRefreshAudit() {
  const queryClient = useQueryClient();
  return useMutation<AuditRefreshResponse, unknown, number>({
    retry: false,
    mutationFn: (linkId) => apiRequest<AuditRefreshResponse>(`/api/audits/${linkId}/refresh`, { method: "POST" }),
    onSuccess: (data, linkId) => {
      queryClient.setQueryData(auditKeys.detail(linkId), {
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
