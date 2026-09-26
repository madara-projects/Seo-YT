import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  ExperimentCreatePayload,
  ExperimentDetailResponse,
  ExperimentListResponse,
  ExperimentResponse,
} from "@/api/experimentTypes";
import { experimentKeys, mutationKeys } from "./queryKeys";

const BASE = "/api/experiment-center/experiments";

export function useExperiments(status: string, mode: string) {
  return useQuery({
    queryKey: experimentKeys.list(status, mode),
    queryFn: ({ signal }) => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (mode) params.set("mode", mode);
      const search = params.toString();
      return apiRequest<ExperimentListResponse>(`${BASE}${search ? `?${search}` : ""}`, { signal });
    },
  });
}

export function useExperiment(id: number | null) {
  return useQuery({
    queryKey: experimentKeys.detail(id ?? 0),
    queryFn: ({ signal }) => apiRequest<ExperimentDetailResponse>(`${BASE}/${id}`, { signal }),
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

/*
 * The changes below are keyed by the experiment (`mutationKeys.recordAction`),
 * so its panel finds one still running after the creator looked at another.
 */

export function useUpdateExperimentStatus(experimentId: number) {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, { id: number; status: string }>({
    mutationKey: mutationKeys.recordAction("experiment", experimentId, "status"),
    mutationFn: ({ id, status }) => apiRequest<ExperimentResponse>(`${BASE}/${id}`, { method: "PATCH", body: { status } }),
    onSuccess: store,
  });
}

export function useAssignVideo(experimentId: number) {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, { id: number; linkId: number; role: string }>({
    mutationKey: mutationKeys.recordAction("experiment", experimentId, "assign"),
    mutationFn: ({ id, linkId, role }) =>
      apiRequest<ExperimentResponse>(`${BASE}/${id}/assignments`, {
        method: "POST",
        body: { published_video_link_id: linkId, role, notes: "" },
      }),
    onSuccess: store,
  });
}

export function useRemoveAssignment(experimentId: number) {
  const queryClient = useQueryClient();
  return useMutation<unknown, unknown, { id: number; assignmentId: number }>({
    mutationKey: mutationKeys.recordAction("experiment", experimentId, "remove"),
    mutationFn: ({ id, assignmentId }) => apiRequest(`${BASE}/${id}/assignments/${assignmentId}`, { method: "DELETE" }),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: experimentKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: experimentKeys.lists() });
    },
  });
}

/** Compares saved completed snapshots only: local, no YouTube call. */
export function useCompareExperiment(experimentId: number) {
  const store = useExperimentUpdater();
  return useMutation<ExperimentResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("experiment", experimentId, "compare"),
    mutationFn: (id) => apiRequest<ExperimentResponse>(`${BASE}/${id}/compare`, { method: "POST" }),
    onSuccess: store,
  });
}
