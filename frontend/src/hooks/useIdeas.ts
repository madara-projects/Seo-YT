import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  Idea,
  IdeaCreatePayload,
  IdeaDemandResponse,
  IdeaGenerateResponse,
  IdeaListResponse,
  IdeaResponse,
} from "@/api/ideaTypes";
import { demandKeys, historyKeys, ideaKeys, mutationKeys, systemKeys } from "./queryKeys";

/** The legacy page's page size. */
export const IDEAS_PAGE_SIZE = 20;

export function useIdeas(status: string, offset: number) {
  return useQuery({
    queryKey: ideaKeys.list(status, offset),
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ limit: String(IDEAS_PAGE_SIZE), offset: String(offset) });
      if (status) query.set("status", status);
      return apiRequest<IdeaListResponse>(`/api/ideas?${query.toString()}`, { signal });
    },
    // Paging keeps the current page on screen until the next one arrives. A
    // different status filter doesn't: its old rows and total would describe
    // the wrong filter.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === status ? previous : undefined,
  });
}

export function useIdea(id: number | null) {
  return useQuery({
    queryKey: ideaKeys.detail(id ?? 0),
    queryFn: ({ signal }) => apiRequest<IdeaResponse>(`/api/ideas/${id}`, { signal }),
    enabled: typeof id === "number" && id > 0,
  });
}

/** Every action returns the updated idea; store it and refresh the lists around it. */
function useIdeaUpdater() {
  const queryClient = useQueryClient();
  return (idea: Idea | undefined) => {
    if (idea?.id) queryClient.setQueryData(ideaKeys.detail(idea.id), { idea });
    void queryClient.invalidateQueries({ queryKey: ideaKeys.lists() });
    // Settings counts ideas.
    void queryClient.invalidateQueries({ queryKey: systemKeys.settings });
  };
}

export function useCreateIdea() {
  const store = useIdeaUpdater();
  return useMutation<IdeaResponse, unknown, IdeaCreatePayload>({
    mutationFn: (payload) => apiRequest<IdeaResponse>("/api/ideas", { method: "POST", body: payload }),
    onSuccess: (data) => store(data.idea),
  });
}

/*
 * The idea actions below are keyed by the idea (`mutationKeys.recordAction`),
 * so the idea's panel can find one still running after the creator looked at
 * another idea and came back.
 */

export function useUpdateIdeaStatus(ideaId: number) {
  const store = useIdeaUpdater();
  return useMutation<IdeaResponse, unknown, { id: number; status: string }>({
    mutationKey: mutationKeys.recordAction("idea", ideaId, "status"),
    mutationFn: ({ id, status }) =>
      apiRequest<IdeaResponse>(`/api/ideas/${id}`, { method: "PATCH", body: { status } }),
    onSuccess: (data) => store(data.idea),
  });
}

/**
 * Runs live YouTube research for an idea and saves a dated snapshot. It spends
 * API quota, so a failure is surfaced rather than retried.
 */
export function useResearchIdea(ideaId: number) {
  const store = useIdeaUpdater();
  return useMutation<IdeaResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("idea", ideaId, "research"),
    retry: false,
    mutationFn: (id) => apiRequest<IdeaResponse>(`/api/ideas/${id}/research`, { method: "POST" }),
    onSuccess: (data) => store(data.idea),
  });
}

/**
 * Writes a package from the idea with the Creator engine (Gemini), researching
 * first when the idea has no current research. Never retried, like `/analyze`.
 */
export function useGenerateIdeaPackage(ideaId: number) {
  const store = useIdeaUpdater();
  const queryClient = useQueryClient();
  return useMutation<IdeaGenerateResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("idea", ideaId, "generate"),
    retry: false,
    mutationFn: (id) =>
      apiRequest<IdeaGenerateResponse>(`/api/ideas/${id}/generate`, { method: "POST", body: {} }),
    onSuccess: (data) => {
      store(data.idea);
      void queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}

/** Runs the Demand explorer on the idea's own fields; spends quota, never retried. */
export function useIdeaDemandResearch(ideaId: number) {
  const queryClient = useQueryClient();
  return useMutation<IdeaDemandResponse, unknown, number>({
    mutationKey: mutationKeys.recordAction("idea", ideaId, "demand"),
    retry: false,
    mutationFn: (id) =>
      apiRequest<IdeaDemandResponse>(`/api/ideas/${id}/demand-research`, { method: "POST" }),
    onSuccess: (data, id) => {
      if (data.research?.id) {
        queryClient.setQueryData(demandKeys.snapshot(data.research.id), { research: data.research });
      }
      void queryClient.invalidateQueries({ queryKey: demandKeys.lists() });
      // The idea's detail carries its latest demand snapshot.
      void queryClient.invalidateQueries({ queryKey: ideaKeys.detail(id) });
    },
  });
}
