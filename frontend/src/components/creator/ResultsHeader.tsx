import { useState } from "react";
import { AlertTriangle, PenLine, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";

/** The first sentence or so of the idea, so the header names what was packaged. */
function excerpt(script: string, max = 140): string {
  const text = script.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

/**
 * The strip above a result: which idea it is for, how it was made, and the
 * two ways back to the setup (to change this one, or to start another).
 */
export function ResultsHeader({
  script,
  formatText,
  formatTone,
  languageText,
  writtenWithGemini,
  warnings,
  onEdit,
  onNew,
  onOpenResearch,
}: {
  script: string;
  formatText: string;
  /** "ok" when the creator chose the format; "warn" when it was detected. */
  formatTone: EvidenceTone;
  languageText: string;
  writtenWithGemini: boolean;
  warnings: string[];
  onEdit: () => void;
  onNew: () => void;
  onOpenResearch: () => void;
}) {
  const [warningsOpen, setWarningsOpen] = useState(false);
  const count = warnings.length;

  return (
    <section
      aria-label="This package"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5 lg:flex-row lg:items-center lg:justify-between"
    >
      <div className="min-w-0 space-y-2.5">
        <p className="line-clamp-2 font-display text-base font-semibold leading-snug text-foreground" title={script}>
          {excerpt(script) || "Untitled idea"}
        </p>
        <div className="flex flex-wrap items-center gap-1.5">
          <EvidenceChip tone={formatTone}>{formatText}</EvidenceChip>
          <EvidenceChip tone="ok">{languageText}</EvidenceChip>
          {/* Gemini's writing is generated, like the fallback's; neither is an observation. */}
          <EvidenceChip tone="warn">{writtenWithGemini ? "Written with Gemini" : "Local fallback"}</EvidenceChip>
          {count ? (
            <button
              type="button"
              onClick={() => setWarningsOpen(true)}
              className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-haspopup="dialog"
            >
              <EvidenceChip tone="warn" className="cursor-pointer underline decoration-dotted underline-offset-2">
                {count} research {count === 1 ? "warning" : "warnings"}
              </EvidenceChip>
            </button>
          ) : (
            <EvidenceChip tone="neutral">No research warnings</EvidenceChip>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onEdit}>
          <PenLine aria-hidden="true" />
          Edit and regenerate
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onNew}>
          <Plus aria-hidden="true" />
          New package
        </Button>
      </div>

      <Dialog open={warningsOpen} onOpenChange={setWarningsOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Research warnings</DialogTitle>
            <DialogDescription>
              Limits of the research behind this package. They don&apos;t stop you using it, but check them first.
            </DialogDescription>
          </DialogHeader>
          <ul className="max-h-[50vh] space-y-2 overflow-y-auto scrollbar-thin">
            {warnings.map((warning, index) => (
              <li
                key={index}
                className="flex gap-2.5 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-foreground"
              >
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setWarningsOpen(false);
                onOpenResearch();
              }}
            >
              Open research and insights
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
