import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { ErrorState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AnalysisProgress } from "@/components/creator/AnalysisProgress";
import { AngleStage } from "@/components/creator/AngleStage";
import { BriefStage } from "@/components/creator/BriefStage";
import { ChecklistStage } from "@/components/creator/ChecklistStage";
import { CompareStage } from "@/components/creator/CompareStage";
import { DecisionStage } from "@/components/creator/DecisionStage";
import { IdeaStage } from "@/components/creator/IdeaStage";
import { PackagingStage } from "@/components/creator/PackagingStage";
import { ResearchStage } from "@/components/creator/ResearchStage";
import { StageNav } from "@/components/creator/StageNav";
import { useAnalyze, useSelectPackage } from "@/hooks/useAnalyze";
import { useElapsedSeconds } from "@/hooks/useElapsed";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { buildPackageOptions, researchHasEvidence } from "@/lib/packages";
import { STAGES, freshChecklist, type ChecklistKey, type StageKey } from "@/lib/creatorConstants";
import { asArray, asObject } from "@/lib/utils";
import {
  creatorFormDefaults,
  creatorFormSchema,
  type CreatorFormValues,
} from "@/schemas/creator";
import type { CreatorBrief, ResearchStatus, SelectionStatus } from "@/api/types";

export default function CreatorPage() {
  const [stage, setStage] = useState<StageKey>("idea");
  const [submitted, setSubmitted] = useState<CreatorFormValues | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionStatus, setSelectionStatus] = useState<SelectionStatus>("unrecorded");
  const [checklist, setChecklist] = useState(freshChecklist);

  const form = useForm<CreatorFormValues>({
    resolver: zodResolver(creatorFormSchema),
    defaultValues: creatorFormDefaults,
    mode: "onBlur",
  });

  const analyze = useAnalyze();
  const selectPackage = useSelectPackage();
  const elapsed = useElapsedSeconds(analyze.isPending);

  // The Dashboard's quick launcher hands a draft over through router state
  // rather than running its own analysis, so there is one place that spends
  // quota. It prefills only; submitting stays an explicit action here.
  const location = useLocation();
  const handoff = location.state as Partial<CreatorFormValues> | null;

  useEffect(() => {
    if (!handoff?.script) return;
    form.reset({
      ...creatorFormDefaults,
      ...handoff,
      script: handoff.script,
    });
    // `form` is stable across renders; re-running on it would clobber edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handoff?.script, handoff?.language, handoff?.region]);

  const data = analyze.data ?? null;

  const options = useMemo(
    () => (data ? buildPackageOptions(data, submitted ?? {}) : []),
    [data, submitted],
  );

  const selected = useMemo(
    () => options.find((option) => option.id === selectedId) ?? options[0] ?? null,
    [options, selectedId],
  );

  // Land on Packaging as soon as a run completes: it is the first stage with
  // something actionable in it.
  useEffect(() => {
    if (!analyze.isSuccess || !data) return;
    setSelectedId(options[0]?.id ?? null);
    setSelectionStatus("unrecorded");
    setChecklist(freshChecklist());
    setStage("packaging");

    const warnings = asArray<string>(data.research_warnings);
    if (data.generation_source === "fallback") {
      toast.warning("Gemini was unavailable; review the local fallback carefully before publishing.");
    } else if (warnings.length) {
      toast.warning(`Package generated with ${warnings.length} research warning(s) to review.`);
    } else {
      toast.success("Package generated. Review each stage before manual publishing.");
    }
    // `options` is derived from `data`; re-running on its identity would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyze.isSuccess, data]);

  const researchStatus: ResearchStatus = analyze.isPending
    ? "loading"
    : analyze.isError
      ? "error"
      : data
        ? researchHasEvidence(data)
          ? "available"
          : "unavailable"
        : "no-research";

  const handleSubmit = form.handleSubmit((values) => {
    setSubmitted(values);
    setSelectedId(null);
    setSelectionStatus("unrecorded");
    setChecklist(freshChecklist());
    analyze.mutate(values);
  });

  const handleSelect = useCallback(
    async (packageId: string) => {
      if (!options.some((option) => option.id === packageId)) return;
      if (packageId !== selectedId) setChecklist(freshChecklist());

      setSelectedId(packageId);
      setSelectionStatus("saving");

      const runId = Number(data?.history_run_id ?? 0);
      if (!runId) {
        setSelectionStatus("error");
        toast.error("The saved analysis ID is unavailable; selection was not recorded.");
        return;
      }

      try {
        await selectPackage.mutateAsync({ runId, packageId });
        setSelectionStatus("saved");
      } catch (error) {
        setSelectionStatus("error");
        toast.error(formatApiError(error, "Package selection could not be saved."));
      }
    },
    [options, selectedId, data, selectPackage],
  );

  const handleExport = useCallback(() => {
    if (!data || !selected) {
      toast.error("Run Analyze and select a package before exporting.");
      return;
    }

    const payload = {
      ...data,
      creator_workflow_local: {
        selected_package_id: selected.id,
        selected_package: { ...selected },
        checklist: { ...checklist },
        persistence:
          selectionStatus === "saved"
            ? "Creator selection saved to SQLite History; never sent to YouTube."
            : "Selection was not confirmed as saved.",
        publishing: "Manual publishing outside Win-Engine OS.",
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `seo-analysis-${Date.now()}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    toast.success("Full analysis and local decision exported.");
  }, [data, selected, checklist, selectionStatus]);

  const handleToggleChecklist = useCallback((key: ChecklistKey, checked: boolean) => {
    setChecklist((current) => ({ ...current, [key]: checked }));
  }, []);

  // A new stage starts at the top of the page, not wherever the last one ended.
  useEffect(() => {
    if (window.scrollY <= 120) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  }, [stage]);

  const stageIndex = STAGES.findIndex((item) => item.key === stage);
  const currentStage = STAGES[stageIndex] ?? STAGES[0];
  const unlocked = Boolean(data);

  const move = (offset: number) => {
    const nextIndex = Math.max(0, Math.min(STAGES.length - 1, stageIndex + offset));
    const next = STAGES[nextIndex];
    if (next) setStage(next.key);
  };

  const warningCount = asArray<string>(data?.research_warnings).length;
  const previousStage = STAGES[stageIndex - 1];
  const nextStage = STAGES[stageIndex + 1];

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Studio"
        icon={Sparkles}
        title="Creator"
        description="Turn a script or idea into a reviewed, comparable SEO package. Nothing here uploads, publishes, or changes a YouTube video."
        actions={
          data ? (
            <>
              <EvidenceChip tone={data.generation_source === "gemini" ? "info" : "warn"}>
                {data.generation_source === "gemini" ? "Written with Gemini" : "Local fallback"}
              </EvidenceChip>
              <EvidenceChip tone={warningCount ? "warn" : "ok"}>
                {warningCount
                  ? `${warningCount} research ${warningCount === 1 ? "warning" : "warnings"}`
                  : "No research warnings"}
              </EvidenceChip>
            </>
          ) : undefined
        }
      />

      <div className="space-y-5">
        <Card className="p-2 sm:p-2.5">
          <StageNav current={stage} unlocked={unlocked} onSelect={setStage} />

          <div className="mt-1.5 flex flex-wrap items-center justify-between gap-3 border-t border-border px-2 pt-2.5 sm:px-2.5">
            <p className="min-w-0 text-[0.8125rem] text-muted-foreground">
              <span className="font-semibold text-foreground">
                Stage {currentStage.step} / {STAGES.length} · {currentStage.label}
              </span>{" "}
              <span className="hidden sm:inline">— {currentStage.hint}</span>
            </p>
            <div className="flex gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => move(-1)}
                disabled={stageIndex <= 0}
              >
                <ChevronLeft aria-hidden="true" />
                Back
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => move(1)}
                disabled={stageIndex >= STAGES.length - 1 || !unlocked}
              >
                Next
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </div>
        </Card>

        {analyze.isPending ? <AnalysisProgress elapsed={elapsed} /> : null}

        {analyze.isError ? (
          <ErrorState
            message={apiErrorMessage(analyze.error, "Analysis failed.")}
            requestId={apiRequestId(analyze.error)}
            onRetry={() => handleSubmit()}
          />
        ) : null}

        {/* The input stage stays mounted so a refined run can be submitted from
            any later stage without losing what was typed. */}
        <div className={stage === "idea" ? "" : "hidden"}>
          <IdeaStage form={form} onSubmit={handleSubmit} isPending={analyze.isPending} />
        </div>

        <div key={stage} className="animate-fade-up">
          {stage === "brief" ? (
            <BriefStage
              brief={(asObject(data?.creator_brief) as CreatorBrief) ?? null}
              submitted={submitted}
            />
          ) : null}

          {stage === "research" ? (
            <ResearchStage
              data={data}
              status={researchStatus}
              errorMessage={
                analyze.isError ? formatApiError(analyze.error, "Analysis failed.") : undefined
              }
            />
          ) : null}

          {stage === "angle" ? (
            <AngleStage data={data} submitted={submitted} selected={selected} />
          ) : null}

          {stage === "packaging" ? (
            <PackagingStage
              data={data}
              options={options}
              selected={selected}
              selectionStatus={selectionStatus}
              onSelect={handleSelect}
              durationSeconds={submitted?.duration_seconds}
            />
          ) : null}

          {stage === "compare" ? (
            <CompareStage
              options={options}
              selectedId={selected?.id ?? null}
              selectionStatus={selectionStatus}
              onSelect={handleSelect}
            />
          ) : null}

          {stage === "decision" ? (
            <DecisionStage
              data={data}
              selected={selected}
              selectionStatus={selectionStatus}
              onExport={handleExport}
            />
          ) : null}

          {stage === "checklist" ? (
            <ChecklistStage
              selected={selected}
              checklist={checklist}
              onToggle={handleToggleChecklist}
              onExport={handleExport}
            />
          ) : null}
        </div>

        {stage !== "idea" && unlocked ? (
          <nav
            aria-label="Stage pages"
            className="grid grid-cols-2 items-center gap-3 border-t border-border pt-5"
          >
            {previousStage ? (
              <Button variant="ghost" onClick={() => move(-1)} className="min-w-0 justify-self-start">
                <ChevronLeft aria-hidden="true" />
                <span className="truncate">{previousStage.label}</span>
              </Button>
            ) : (
              <span />
            )}
            {nextStage ? (
              <Button variant="outline" onClick={() => move(1)} className="min-w-0 max-w-full justify-self-end">
                <span className="truncate">
                  <span className="hidden sm:inline">Continue to </span>
                  {nextStage.label}
                </span>
                <ChevronRight aria-hidden="true" />
              </Button>
            ) : null}
          </nav>
        ) : null}
      </div>
    </div>
  );
}
