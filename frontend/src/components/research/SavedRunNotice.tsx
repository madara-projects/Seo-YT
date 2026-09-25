import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Confirms a generated package was saved, with a way straight to it. */
export function SavedRunNotice({ runId }: { runId: number | null }) {
  return (
    <div
      role="status"
      className="flex flex-col gap-3 rounded-xl border border-tone-ok-border bg-tone-ok-bg p-3.5 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <CheckCircle2 className="size-4 shrink-0 text-tone-ok" aria-hidden="true" />
        {runId ? `Package saved to History as run #${runId}.` : "Package generated and saved to History."}
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link to={runId ? `/history?run=${runId}` : "/history"}>
          Open in History
          <ArrowRight aria-hidden="true" />
        </Link>
      </Button>
    </div>
  );
}
