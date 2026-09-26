import { useEffect, useState } from "react";

/**
 * Seconds elapsed while `active`; resets when it goes false. Pass `since`
 * (ms) when the work began before this component mounted, so returning to a
 * page mid-request shows the real elapsed time rather than restarting at 0.
 */
export function useElapsedSeconds(active: boolean, since?: number): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) {
      setElapsed(0);
      return;
    }
    const startedAt = since && since > 0 ? since : Date.now();
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [active, since]);

  return elapsed;
}

export function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}
