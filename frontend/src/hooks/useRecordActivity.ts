import { useMutationState, type MutationStatus } from "@tanstack/react-query";
import { mutationKeys } from "./queryKeys";

export interface RecordRun {
  /** The action's name: the last part of its mutation key ("research", "generate"…). */
  action: string;
  status: MutationStatus;
  error: unknown;
  data: unknown;
  submittedAt: number;
}

function newest(runs: RecordRun[]): RecordRun | null {
  return runs.reduce<RecordRun | null>((found, run) => (!found || run.submittedAt >= found.submittedAt ? run : found), null);
}

/**
 * What has been done to one record, read from the mutation cache rather than
 * from component state. A panel keyed by record unmounts when another record
 * is opened; reading the cache means that coming back still shows a request
 * in flight (with its buttons disabled, so it can't be sent twice), its error,
 * or its result.
 */
export function useRecordActivity(kind: string, id: number) {
  const runs = useMutationState({
    filters: { mutationKey: mutationKeys.record(kind, id) },
    select: (mutation): RecordRun => ({
      action: String(mutation.options.mutationKey?.[3] ?? ""),
      status: mutation.state.status,
      error: mutation.state.error,
      data: mutation.state.data,
      submittedAt: mutation.state.submittedAt,
    }),
  });

  const pending = newest(runs.filter((run) => run.status === "pending"));
  return {
    /** The most recently started action, whatever its outcome. */
    latest: newest(runs),
    /** An action still running, if any. */
    pending,
    /** The most recent run of one action. */
    latestOf: (action: string) => newest(runs.filter((run) => run.action === action)),
  };
}
