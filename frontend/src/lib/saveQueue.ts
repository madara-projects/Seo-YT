/**
 * Ordered saves that outlive the component that started them.
 *
 * A save chain kept in component state resets when the page is left and
 * reopened, so a choice made after returning could be overwritten by an
 * older request that was still in flight. The chain and the click counter
 * live here instead, keyed by what the server overwrites (the run), so the
 * last click is the last write whatever the component did in between.
 */

type Key = string | number;

const chains = new Map<Key, Promise<unknown>>();
const sequences = new Map<Key, number>();

export interface QueuedSave<T> {
  /** Settles with this save's own outcome, after every earlier save for the key. */
  result: Promise<T>;
  /** False once a later save was queued for the key: its outcome is then stale. */
  isLatest: () => boolean;
}

export function queueSave<T>(key: Key, task: () => Promise<T>): QueuedSave<T> {
  const seq = (sequences.get(key) ?? 0) + 1;
  sequences.set(key, seq);
  const prior = chains.get(key) ?? Promise.resolve();
  const result = prior.catch(() => undefined).then(task);
  chains.set(key, result);
  return { result, isLatest: () => sequences.get(key) === seq };
}

/** Test hook: forgets every chain, as a fresh page load would. */
export function resetSaveQueues(): void {
  chains.clear();
  sequences.clear();
}
