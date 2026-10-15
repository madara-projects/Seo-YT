import { useRef } from "react";
import { Clapperboard, Gauge, Package, Target, Trash2, Type, X } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { CardSkeleton, ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, displayValue } from "@/lib/utils";
import { opportunityText, titleScoreText } from "@/lib/dashboardFormat";
import { historyDate } from "@/lib/historyFormat";
import { outputLanguageLabel } from "@/lib/creatorFormat";
import { uploadBundleText } from "@/lib/packages";
import type { HistoryRunDetail } from "@/api/historyTypes";
import { HistoryOpportunityBreakdown } from "./HistoryOpportunityBreakdown";
import { StudioTestPanel } from "@/components/learning/StudioTestPanel";
import { AiShortsBody, aiShortsMarker, useRunPlan } from "./AiShortsDetail";
import {
  LinkCallout,
  PublishedVideo,
  RetentionCallout,
  SavedPackageFields,
  ScoreTile,
  SelectionCallout,
} from "./HistoryDetailParts";

/** A package written on the Creator page: its scores, what it led to, then the package itself. */
function CreatorBody({ run, onLink }: { run: HistoryRunDetail; onLink: () => void }) {
  const pkg = asObject(run.package);
  const hasPackage = Object.keys(pkg).length > 0;
  const selection = run.selected_package ?? null;
  const report = run.linked_video_report ?? null;
  const isLinked = Boolean(report?.linked);
  const unmeasured = run.opportunity_label === "UNMEASURED";

  return (
    <div className="space-y-6">
      {!hasPackage ? (
        <div className="rounded-xl border border-tone-warn-border bg-tone-warn-bg p-3.5 text-xs leading-relaxed text-foreground">
          This package was created before full-package history was added. Its saved title, script,
          and scores are shown below; future packages retain the complete generated output.
        </div>
      ) : null}

      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <ScoreTile
            icon={Target}
            label="Opportunity"
            // An unmeasured score was once stored as 0; the label says it was never measured.
            value={unmeasured ? "Unavailable" : opportunityText(run.opportunity_score)}
            note={unmeasured ? "Not measured: no competitor results" : displayValue(run.opportunity_label, "Unavailable")}
          />
          <ScoreTile icon={Type} label="Title quality" value={titleScoreText(run.title_score)} note="Local heuristic" />
          <ScoreTile
            icon={Gauge}
            label="Retention risk"
            value={displayValue(run.retention_risk, "Unavailable")}
            note="Pre-publish guidance"
          />
        </div>
        <HistoryOpportunityBreakdown run={run} />
      </div>

      <div className="space-y-2.5">
        <SelectionCallout selection={selection} />
        <RetentionCallout pkg={pkg} />
        {!isLinked ? <LinkCallout onLink={onLink} /> : null}
      </div>

      {isLinked && report ? (
        <PublishedVideo
          report={report}
          fallbackTitle={String(selection?.package?.title || pkg.title || run.title || "Saved package")}
        />
      ) : null}

      {hasPackage ? <StudioTestPanel runId={run.id} /> : null}

      <SavedPackageFields run={run} />
    </div>
  );
}

/**
 * One saved package, in a panel that slides over the list. Opening it is a
 * URL change (`?run=`), so a package can be linked to and survives a reload.
 * A package written on the AI Shorts page opens with its Flow prompts.
 */
export function HistoryDetail({
  open,
  run,
  fallbackTitle,
  isLoading,
  error,
  onClose,
  onLink,
  onDelete,
}: {
  open: boolean;
  run: HistoryRunDetail | null;
  fallbackTitle?: string;
  isLoading: boolean;
  error: unknown;
  onClose: () => void;
  onLink: () => void;
  onDelete?: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const pkg = asObject(run?.package);
  const hasPackage = Object.keys(pkg).length > 0;
  const isLinked = Boolean(run?.linked_video_report?.linked);
  const title = run ? displayValue(run.title, "Untitled package") : fallbackTitle || "Saved package";
  // The creator's recorded choice is what they meant to publish, so it is what gets copied.
  const chosen = run?.selected_package?.package ?? null;
  const aiShorts = aiShortsMarker(run);
  const plan = useRunPlan(run, aiShorts);
  // A plan that is gone, or another run's, can't be opened on the AI Shorts page either.
  const canOpenPlan = aiShorts?.planId != null && plan?.status !== "gone" && plan?.status !== "elsewhere";
  // A Short is described by its language; a Creator package by its angle.
  const kind = aiShorts
    ? aiShorts.language && outputLanguageLabel(aiShorts.language)
    : displayValue(run?.content_angle, "General");
  const meta = run
    ? [`Saved ${historyDate(run.created_at)}`, kind].filter(Boolean).join(" · ")
    : "Package details from your local History.";

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      {/* Full width on phones; wide enough on desktop for a Flow prompt to read as a paragraph. */}
      <SheetContent
        data-testid="history-detail"
        className="lg:max-w-4xl xl:max-w-5xl"
        // Focus starts on Close, never on the Delete beside it.
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          closeRef.current?.focus();
        }}
      >
        <div className="relative shrink-0 overflow-hidden border-b border-border px-4 pb-4 pt-3 sm:px-7 sm:pb-5 sm:pt-4">
          <div
            className="pointer-events-none absolute -right-16 -top-24 size-64 rounded-full bg-brand-gradient opacity-15 blur-3xl"
            aria-hidden="true"
          />
          <div className="relative flex items-center justify-between gap-3">
            <p className="flex min-w-0 items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em] text-brand">
              {aiShorts ? (
                <Clapperboard className="size-3.5 shrink-0" aria-hidden="true" />
              ) : (
                <Package className="size-3.5 shrink-0" aria-hidden="true" />
              )}
              <span className="truncate">{aiShorts ? "Saved AI Short" : "Saved package"}</span>
            </p>
            <div className="-mr-2 flex shrink-0 items-center gap-1">
              {run && onDelete ? (
                <Button size="sm" variant="danger" onClick={onDelete} aria-label="Delete this package">
                  <Trash2 aria-hidden="true" />
                  Delete
                </Button>
              ) : null}
              <SheetClose asChild>
                <Button ref={closeRef} variant="ghost" size="icon" aria-label="Close package detail">
                  <X aria-hidden="true" />
                </Button>
              </SheetClose>
            </div>
          </div>

          <div className="relative mt-1 min-w-0 space-y-1">
            <SheetTitle className="break-words font-display text-lg font-semibold leading-snug tracking-tight text-foreground sm:text-xl">
              {isLoading && !run ? "Loading saved package…" : title}
            </SheetTitle>
            <SheetDescription className="text-xs text-muted-foreground">{meta}</SheetDescription>
          </div>

          {run ? (
            <div className="relative mt-3 flex flex-wrap items-center gap-2">
              {aiShorts ? (
                <Badge variant="brand" title="Written on the AI Shorts page">
                  {aiShorts.label}
                </Badge>
              ) : null}
              <EvidenceChip tone={isLinked ? "ok" : "neutral"}>{isLinked ? "YouTube linked" : "Not linked"}</EvidenceChip>
            </div>
          ) : null}

          {run ? (
            <div role="group" aria-label="Package actions" className="relative mt-4 flex flex-wrap items-center gap-2">
              {/* The page promises the saved package can be reused; without this the
                  only route was selecting text inside a scroll box. */}
              <CopyButton
                value={uploadBundleText({
                  title: String(chosen?.title || pkg.title || run.title || ""),
                  description: String(chosen?.description ?? pkg.description ?? ""),
                  tags: asArray<string>(chosen?.tags ?? pkg.tags),
                  hashtags: asArray<string>(chosen?.hashtags ?? pkg.hashtags),
                })}
                label={chosen ? "Copy selected upload package" : "Copy upload package"}
                variant="gradient"
                size="sm"
                disabled={!hasPackage}
              />
              {canOpenPlan ? (
                <Button asChild variant="outline" size="sm">
                  <Link to={`/ai-shorts?plan=${aiShorts?.planId}`}>
                    <Clapperboard aria-hidden="true" />
                    Open in AI Shorts
                  </Link>
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 scrollbar-thin sm:px-7 sm:py-6" data-testid="history-detail-body">
          {isLoading ? (
            <CardSkeleton rows={6} />
          ) : error ? (
            <ErrorState
              message={apiErrorMessage(error, "Could not load this saved package.")}
              requestId={apiRequestId(error)}
            />
          ) : run ? (
            plan ? (
              <AiShortsBody key={run.id} run={run} plan={plan} onLink={onLink} />
            ) : (
              <CreatorBody run={run} onLink={onLink} />
            )
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
