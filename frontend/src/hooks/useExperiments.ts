import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  ExperimentCreatePayload,
  ExperimentDetailResponse,
  ExperimentListResponse,
  ExperimentResponse,
} from "@/api/experimentTypes";

export const experimentKeys = {
  all: ["experiments"] as const,
  lists: () => [...experimentKeys.all, "list"] as const,
  list: (status: string, mode: string) => [...experimentKeys.lists(), status, mode] as const,
  detail: (id: number) => [...experimentKeys.all, "detail", id] as const,
};

const BASE = "/api/experiment-center/experiments";

export function useExperiments(status: string, mode: string) {
  return useQuery({
    queryKey: experimentKeys.list(status, mode),
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (mode) params.set("mode", mode);
      const search = params.toString();
      return apiRequest<ExperimentListResponse>(`${BASE}${search ? `?${search}` : ""}`);
    },
  });
}

export function useExperiment(id: number | null) {
  return useQuery({
    queryKey: experimentKeys.detail(id ?? 0),
    queryFn: () => apiRequest<ExperimentDetailResponse>(`${BASE}/${id}`),
    enabled: typeof id === "number" && id > 0,
  });
}

/**
 * Every change returns the updated experiment. Keep it, then refetch the
 * detail (for its saved comparison versions) and the lists around it.
 */
function useExperimentUpdater() {
  const queryClient = useQueryClient();
  return (data: ExperimentResponse) => {
    const experiment = data.experiment;
    if (experiment?.id) {
      queryClient.setQueryData<ExperimentDetailResponse>(experimentKeys.detail(experiment.id), (current) => ({
        result_versions: current?.result_versions ?? [],
        experiment,
      }));
      void queryClient.invalidateQueries({ queryKey: experimentKeys.detail(experiment.id) });
    }
    void queryClient.invalidateQueries({ queryKey: experimentKeys.lists() });
  };
}

export function useCreateExperiment() {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, ExperimentCreatePayload>({
    mutationFn: (body) => apiRequest<ExperimentResponse>(BASE, { method: "POST", body: { ...body, status: "draft" } }),
    onSuccess: store,
  });
}

export function useUpdateExperimentStatus() {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, { id: number; status: string }>({
    mutationFn: ({ id, status }) => apiRequest<ExperimentResponse>(`${BASE}/${id}`, { method: "PATCH", body: { status } }),
    onSuccess: store,
  });
}

export function useAssignVideo() {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, { id: number; linkId: number; role: string }>({
    mutationFn: ({ id, linkId, role }) =>
      apiRequest<ExperimentResponse>(`${BASE}/${id}/assignments`, {
        method: "POST",
        body: { published_video_link_id: linkId, role, notes: "" },
      }),
    onSuccess: store,
  });
}

export function useRemoveAssignment() {
  const queryClient = useQueryClient();
  return useMutation<unknown, unknown, { id: number; assignmentId: number }>({
    mutationFn: ({ id, assignmentId }) => apiRequest(`${BASE}/${id}/assignments/${assignmentId}`, { method: "DELETE" }),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: experimentKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: experimentKeys.lists() });
    },
  });
}

/** Compares saved completed snapshots only: local, no YouTube call. */
export function useCompareExperiment() {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, number>({
    mutationFn: (id) => apiRequest<ExperimentResponse>(`${BASE}/${id}/compare`, { method: "POST" }),
    onSuccess: store,
  });
}
