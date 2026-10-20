import { beforeEach, describe, expect, it } from "vitest";
import { queueSave, resetSaveQueues } from "./saveQueue";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}

// A queued task starts a few microtasks after the earlier save settles, so a
// macrotask turn is the reliable way to let the chain advance.
const flush = () => new Promise<void>((done) => setTimeout(done, 0));

describe("queueSave", () => {
  beforeEach(() => resetSaveQueues());

  it("starts a later save only after the earlier one settles, across callers", async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const started: string[] = [];

    // Queued from "one mount"…
    const a = queueSave(42, () => {
      started.push("A");
      return first.promise;
    });
    // …and from "another mount" of the same page, with no shared state.
    const b = queueSave(42, () => {
      started.push("B");
      return second.promise;
    });

    await flush();
    expect(started).toEqual(["A"]);
    expect(a.isLatest()).toBe(false);
    expect(b.isLatest()).toBe(true);

    first.resolve("a");
    await expect(a.result).resolves.toBe("a");
    await flush();
    expect(started).toEqual(["A", "B"]);

    second.resolve("b");
    await expect(b.result).resolves.toBe("b");
  });

  it("keeps saving after a failed save, and keeps runs apart", async () => {
    const failed = queueSave("run-1", () => Promise.reject(new Error("offline")));
    await expect(failed.result).rejects.toThrow("offline");

    const next = queueSave("run-1", () => Promise.resolve("ok"));
    await expect(next.result).resolves.toBe("ok");

    const other = queueSave("run-2", () => Promise.resolve("other"));
    expect(next.isLatest()).toBe(true);
    expect(other.isLatest()).toBe(true);
  });
});
