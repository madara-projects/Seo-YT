import { Timer } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Field, Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { humanize } from "@/lib/labels";
import { toFiniteNumber } from "@/lib/format";
import { asObject, displayValue, UNAVAILABLE } from "@/lib/utils";
import type { PacingAnalysis } from "@/api/types";

/** The three readings, named for what they measure in each kind of video. */
const LABELS = {
  spoken_script: { pace: "Pacing assessment", length: "Avg sentence length", hooks: "Hook density" },
  quote_short: { pace: "Format assessment", length: "Quote length", hooks: "Hook structure" },
} as const;

function words(value: unknown): string {
  const count = toFiniteNumber(value);
  if (count === null) return UNAVAILABLE;
  return `${count.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${count === 1 ? "word" : "words"}`;
}

function wording(value: unknown): string {
  const text = String(value ?? "").trim();
  return text ? humanize(text) : UNAVAILABLE;
}

/**
 * The script's pacing (`pacing_analysis`), ported from the classic dashboard.
 * A local count of sentence length and contrast words, or of a quote's length
 * for a quote Short: guidance on the text, never measured retention.
 */
export function PacingPanel({ pacing }: { pacing: PacingAnalysis | undefined }) {
  const data = asObject(pacing) as PacingAnalysis;
  const quote = data.analysis_type === "quote_short";
  const labels = quote ? LABELS.quote_short : LABELS.spoken_script;
  // A script with no sentences comes back as "unknown" with placeholder
  // zeros and "low": nothing was measured, so none of it is shown as a reading.
  const measured = String(data.pace_label ?? "").trim().toLowerCase() !== "unknown";

  return (
    <Panel
      icon={Timer}
      title={quote ? "Quote Short pacing" : "Script pacing"}
      description={
        quote
          ? "How readable the on-screen quote is. Counted from the text, not measured on viewers."
          : "Sentence length and contrast words counted in the script, not measured on viewers."
      }
      aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
      data-testid="pacing-analysis"
    >
      {Object.keys(data).length ? (
        <div className="space-y-4">
          <dl className="grid gap-4 sm:grid-cols-3">
            <Field label={labels.pace}>{measured ? wording(data.pace_label) : UNAVAILABLE}</Field>
            <Field label={labels.length}>{measured ? words(data.avg_sentence_length) : UNAVAILABLE}</Field>
            <Field label={labels.hooks}>{measured ? wording(data.hook_density) : UNAVAILABLE}</Field>
          </dl>
          <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
            {displayValue(data.recommendation, "No pacing recommendation was returned.")}
          </p>
        </div>
      ) : (
        <UnavailableNote>No pacing analysis was returned for this run.</UnavailableNote>
      )}
    </Panel>
  );
}
