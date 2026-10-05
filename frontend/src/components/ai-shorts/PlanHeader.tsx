import { Link } from "react-router-dom";
import { AlertTriangle, Library, RefreshCw, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { historyDate } from "@/lib/historyFormat";
import { outputLanguageLabel } from "@/lib/creatorFormat";
import { partsLabel, sourceChip } from "@/lib/aiShortsFormat";
import { asArray } from "@/lib/utils";
import type { AiShortsChecks, AiShortsPlan } from "@/api/aiShortsTypes";

/** The plan's own checks as one chip: a pass is confirmed, warnings are flagged, issues are a failure. */
function checksChip(checks: AiShortsChecks | undefined): { label: string; tone: EvidenceTone } {
  if (!checks) return { label: "Checks unavailable", tone: "neutral" };
  const issues = asArray<string>(checks.issues).length;
  const warnings = asArray<string>(checks.warnings).length;
  if (checks.passed === false || issues) {
    return { label: issues ? `${issues} ${issues === 1 ? "issue" : "issues"}` : "Checks failed", tone: "bad" };
  }
  if (warnings) return { label: `Passed with ${warnings} ${warnings === 1 ? "warning" : "warnings"}`, tone: "warn" };
  return { label: "Checks passed", tone: "ok" };
}

/**
 * The strip above a plan: the quote it is for, how long it runs, how it was
 * written and what the checks found. A built-in template draft says so and
 * offers the retry.
 */
export function PlanHeader({
  plan,
  onRetry,
  retrying,
}: {
  plan: AiShortsPlan;
  onRetry: () => void;
  retrying: boolean;
}) {
  const source = sourceChip(plan.generation_source);
  const checks = checksChip(plan.checks);
  const issues = asArray<string>(plan.checks?.issues);
  const warnings = asArray<string>(plan.checks?.warnings);

  return (
    <section
      aria-label="This AI Short"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5"
      data-testid="plan-header"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2.5">
          <p className="break-words font-display text-lg font-semibold leading-snug text-foreground sm:text-xl">“{plan.quote}”</p>
          <div className="flex flex-wrap items-center gap-1.5">
            <EvidenceChip tone="ok">{partsLabel(plan.parts, plan.total_seconds)}</EvidenceChip>
            <EvidenceChip tone="ok">{outputLanguageLabel(plan.language)}</EvidenceChip>
            {/* Gemini's writing is generated, like the template's; neither is an observation. */}
            <EvidenceChip tone={source.tone}>{source.label}</EvidenceChip>
            <EvidenceChip tone={checks.tone}>{checks.label}</EvidenceChip>
          </div>
          <p className="text-xs text-muted-foreground">
            Written {historyDate(plan.created_at)}
            {plan.analysis_run_id ? ` · saved to History as run #${plan.analysis_run_id}` : " · not saved to History"}
          </p>
        </div>
        {plan.analysis_run_id ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <Link to={`/history?run=${plan.analysis_run_id}`}>
                <Library aria-hidden="true" />
                Open in History
              </Link>
            </Button>
          </div>
        ) : null}
      </div>

      {plan.generation_source === "fallback" ? (
        <div className="flex flex-col gap-3 rounded-xl border border-tone-warn-border bg-tone-warn-bg p-3.5 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-foreground">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
            <span>
              Gemini was unavailable, so this draft comes from the built-in template. Retry for prompts written for
              this quote.
            </span>
          </p>
          <Button type="button" size="sm" variant="outline" onClick={onRetry} disabled={retrying} className="shrink-0 self-start sm:self-center">
            <RefreshCw aria-hidden="true" />
            Retry with Gemini
          </Button>
        </div>
      ) : null}

      {issues.length || warnings.length ? (
        <ul className="space-y-1.5" aria-label="Check results">
          {issues.map((issue, index) => (
            <li
              key={`issue-${index}`}
              className="flex gap-2.5 rounded-xl border border-tone-bad-border bg-tone-bad-bg px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-foreground"
            >
              <XCircle className="mt-0.5 size-4 shrink-0 text-tone-bad" aria-hidden="true" />
              <span>{issue}</span>
            </li>
          ))}
          {warnings.map((warning, index) => (
            <li
              key={`warning-${index}`}
              className="flex gap-2.5 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-foreground"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-tone-warn" aria-hidden="true" />
              <span>{warning}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
