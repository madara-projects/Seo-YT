import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  CircleCheck,
  CircleDashed,
  Library,
  RefreshCw,
  Wand2,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { historyDate } from "@/lib/historyFormat";
import { outputLanguageLabel } from "@/lib/creatorFormat";
import {
  allPromptsText,
  checkFindings,
  packageFindings,
  partsLabel,
  planAdjustments,
  planStatus,
  sourceChip,
  type CheckFinding,
} from "@/lib/aiShortsFormat";
import { cn } from "@/lib/utils";
import type { AiShortsPlan, AiShortsShot } from "@/api/aiShortsTypes";

const PILL_TONES: Record<EvidenceTone, string> = {
  ok: "border-tone-ok-border bg-tone-ok-bg text-tone-ok",
  warn: "border-tone-warn-border bg-tone-warn-bg text-tone-warn",
  bad: "border-tone-bad-border bg-tone-bad-bg text-tone-bad",
  info: "border-tone-info-border bg-tone-info-bg text-tone-info",
  neutral: "border-border bg-muted text-muted-foreground",
};

const PILL_ICONS: Record<EvidenceTone, LucideIcon> = {
  ok: CircleCheck,
  warn: AlertTriangle,
  bad: XCircle,
  info: CircleCheck,
  neutral: CircleDashed,
};

/** One group of notes in the status details: the prompts' or the package's. */
function FindingGroup({
  title,
  findings,
  listLabel,
  action,
  children,
}: {
  title: string;
  findings: CheckFinding[];
  listLabel: string;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5" data-testid={`status-group-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[0.6875rem] font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
        {action}
      </div>
      {findings.length ? (
        <ul className="space-y-2" aria-label={listLabel}>
          {findings.map((finding, index) => {
            const FindingIcon = finding.severity === "issue" ? XCircle : AlertTriangle;
            return (
              <li key={`${finding.severity}-${index}`} className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-foreground">
                <FindingIcon
                  className={cn("mt-0.5 size-4 shrink-0", finding.severity === "issue" ? "text-tone-bad" : "text-tone-warn")}
                  aria-hidden="true"
                />
                <span className="min-w-0 break-words">
                  {finding.part !== null ? (
                    <Badge variant="neutral" className="mr-1.5 align-[0.0625rem]">
                      Part {finding.part}
                    </Badge>
                  ) : null}
                  {finding.text}
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">Nothing to check.</p>
      )}
      {children}
    </div>
  );
}

/**
 * One status pill beside the meta line, over the prompts and the package; it
 * opens to what was found, in plain words, grouped by where it applies.
 */
function CheckStatus({ plan, meta, onOpenPackage }: { plan: AiShortsPlan; meta: string[]; onOpenPackage?: () => void }) {
  const quality = plan.package?.generation_quality;
  const status = planStatus(plan.checks, quality);
  const findings = checkFindings(plan.checks);
  const notes = packageFindings(quality);
  const general = planAdjustments(plan.checks).general;
  const expandable = findings.length > 0 || notes.length > 0 || general.length > 0;
  // A failed check is opened for the creator; warnings wait for a click.
  const [open, setOpen] = useState(status.tone === "bad");
  const Icon = PILL_ICONS[status.tone];
  const pill = cn(
    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium leading-4",
    PILL_TONES[status.tone],
  );

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="min-w-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {expandable ? (
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className={cn(
                pill,
                "cursor-pointer transition-[filter] hover:brightness-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              )}
            >
              <Icon className="size-3.5 shrink-0" aria-hidden="true" />
              {status.label}
              <ChevronDown
                className={cn("size-3.5 shrink-0 transition-transform duration-200", open && "rotate-180")}
                aria-hidden="true"
              />
            </button>
          </CollapsibleTrigger>
        ) : (
          <span className={pill}>
            <Icon className="size-3.5 shrink-0" aria-hidden="true" />
            {status.label}
          </span>
        )}
        <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground" data-testid="plan-meta">
          {meta.map((item, index) => (
            <Fragment key={`${index}-${item}`}>
              {index ? <span aria-hidden="true">·</span> : null}
              <span>{item}</span>
            </Fragment>
          ))}
        </p>
      </div>

      {expandable ? (
        <CollapsibleContent>
          <div className="mt-3 space-y-3 rounded-xl border border-border bg-elevated p-3 sm:p-3.5">
            <FindingGroup title="Prompts" findings={findings} listLabel="Things to check">
              {general.map((item, index) => (
                <p key={`fix-${index}`} className="flex gap-2.5 text-xs leading-relaxed text-muted-foreground">
                  <Wand2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 break-words">
                    <span className="font-medium">Adjusted automatically:</span> {item}
                  </span>
                </p>
              ))}
            </FindingGroup>
            <FindingGroup
              title="Upload package"
              findings={notes}
              listLabel="Package notes"
              action={
                notes.length && onOpenPackage ? (
                  <button
                    type="button"
                    onClick={onOpenPackage}
                    className="inline-flex items-center gap-1 rounded-md text-xs font-medium text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Open Upload package
                    <ArrowRight className="size-3.5" aria-hidden="true" />
                  </button>
                ) : null
              }
            />
            {status.tone === "warn" ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Warnings don&apos;t block anything; look at them before you generate in Flow and upload.
              </p>
            ) : null}
          </div>
        </CollapsibleContent>
      ) : null}
    </Collapsible>
  );
}

/**
 * The strip above a plan: the quote, one line on how it was made, one status
 * that opens to what the checks found, and the actions for the whole plan. A
 * built-in template draft says so and offers Gemini instead.
 */
export function PlanHeader({
  plan,
  shots,
  onRetry,
  retrying = false,
  showHistoryLink = true,
  onOpenPackage,
}: {
  plan: AiShortsPlan;
  shots: AiShortsShot[];
  onRetry?: () => void;
  retrying?: boolean;
  showHistoryLink?: boolean;
  /** Opens the Upload package tab from the status details. */
  onOpenPackage?: () => void;
}) {
  const draft = plan.generation_source === "fallback";
  const quote = String(plan.quote ?? "");
  const historyLink = showHistoryLink && plan.analysis_run_id ? `/history?run=${plan.analysis_run_id}` : null;
  const copyAll = shots.length > 1;
  const meta = [
    partsLabel(plan.parts, plan.total_seconds),
    outputLanguageLabel(plan.language),
    sourceChip(plan.generation_source).label,
    historyDate(plan.created_at),
    ...(showHistoryLink && !plan.analysis_run_id ? ["Not saved to History"] : []),
  ];

  return (
    <section
      aria-label="This AI Short"
      className="@container rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5"
      data-testid="plan-header"
    >
      {/* Narrow: quote, status, then the actions. Wide: the actions sit beside the quote. */}
      <div className="grid gap-x-5 gap-y-3 @2xl:grid-cols-[minmax(0,1fr)_auto]">
        <p
          className={cn(
            "min-w-0 break-words text-balance font-display font-semibold leading-snug tracking-tight text-foreground @2xl:col-start-1 @2xl:row-start-1",
            quote.length > 160 ? "text-lg sm:text-xl" : "text-xl sm:text-2xl",
          )}
        >
          “{quote}”
        </p>

        {copyAll || historyLink || onRetry ? (
          <div className="order-last flex flex-wrap items-center gap-2 @2xl:order-none @2xl:col-start-2 @2xl:row-start-1 @2xl:justify-end">
            {copyAll ? (
              <CopyButton
                value={allPromptsText(shots)}
                label="Copy all prompts"
                variant="soft"
                successMessage="All prompts copied, labelled by part."
              />
            ) : null}
            {historyLink ? (
              <Button asChild variant="outline" size="sm">
                <Link to={historyLink}>
                  <Library aria-hidden="true" />
                  Open in History
                </Link>
              </Button>
            ) : null}
            {onRetry ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onRetry}
                disabled={retrying}
                title="Writes this quote again with Gemini (up to 6 Gemini calls)."
              >
                <RefreshCw aria-hidden="true" />
                {draft ? "Retry with Gemini" : "Write again"}
              </Button>
            ) : null}
          </div>
        ) : null}

        <div className="min-w-0 @2xl:col-span-2 @2xl:row-start-2">
          <CheckStatus plan={plan} meta={meta} onOpenPackage={onOpenPackage} />
        </div>

        {draft ? (
          <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground @2xl:col-span-2 @2xl:row-start-3">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-tone-warn" aria-hidden="true" />
            <span>
              Gemini was unavailable, so this draft comes from the built-in template.
              {onRetry ? " Retry for prompts written for this quote." : null}
            </span>
          </p>
        ) : null}
      </div>
    </section>
  );
}
