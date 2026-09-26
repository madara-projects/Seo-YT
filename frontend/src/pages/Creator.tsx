import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutationState, type MutationStatus } from "@tanstack/react-query";
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
import { useHistoryRun } from "@/hooks/useHistory";
import { mutationKeys } from "@/hooks/queryKeys";
import { useUrlState } from "@/hooks/useUrlState";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { buildPackageOptions, researchHasEvidence } from "@/lib/packages";
import {
  STAGES,
  freshChecklist,
  type ChecklistKey,
  type ChecklistState,
  type StageKey,
} from "@/lib/creatorConstants";
import { asArray, asObject } from "@/lib/utils";
import {
  creatorFormDefaults,
  creatorFormSchema,
  type CreatorFormValues,
} from "@/schemas/creator";
import type { AnalyzeResponse, CreatorBrief, ResearchStatus, SelectionStatus } from "@/api/types";

interface AnalyzeRun {
  status: MutationStatus;
  data: AnalyzeResponse | undefined;
  error: unknown;
  variables: CreatorFormValues | undefined;
  submittedAt: number;
}

/**
 * The newest `/analyze` run, read from the mutation cache rather than from
 * this page's own state. A run started before the creator left the page is
 * still found when they return: its progress while it runs (so Generate
 * stays disabled and quota is not spent twice), then its result.
 */
function useLatestAnalyzeRun(): AnalyzeRun | null {
  const runs = useMutationState({
    filters: { mutationKey: mutationKeys.analyze },
    select: (mutation): AnalyzeRun => ({
      status: mutation.state.status,
      data: mutation.state.data as AnalyzeResponse | undefined,
      error: mutation.state.error,
      variables: mutation.state.variables as CreatorFormValues | undefined,
      submittedAt: mutation.state.submittedAt,
    }),
  });
  return runs.reduce<AnalyzeRun | null>(
    (newest, run) => (run.status !== "idle" && (!newest || run.submittedAt >= newest.submittedAt) ? run : newest),
    null,
  );
}

const STAGE_KEYS = new Set<string>(STAGES.map((item) => item.key));

function isStageKey(value: string): value is StageKey {
  return STAGE_KEYS.has(value);
}

/** The creator's choice for one run. Keyed by run, so a new run starts with none. */
interface Choice {
  run: number;
  optionId: string;
  status: SelectionStatus;
}

/** Checklist answers for one package of one run: choosing another package starts afresh. */
interface Checks {
  run: number;
  optionId: string;
  state: ChecklistState;
}

export default function CreatorPage() {
  const latest = useLatestAnalyzeRun();
  const analyze = useAnalyze();
  const selectPackage = useSelectPackage();
  const saveSelection = selectPackage.mutateAsync;
  const url = useUrlState();

  const form = useForm<CreatorFormValues>({
    resolver: zodResolver(creatorFormSchema),
    // Back on the page during or after a run, the form shows that run's input.
    defaultValues: latest?.variables ? { ...creatorFormDefaults, ...latest.variables } : creatorFormDefaults,
    mode: "onBlur",
  });

  const isPending = latest?.status === "pending";
  const data = latest?.status === "success" ? (latest.data ?? null) : null;
  const failure = latest?.status === "error" ? latest.error : null;
  const submitted = latest?.variables ?? null;
  const runKey = data ? (latest?.submittedAt ?? null) : null;
  const elapsed = useElapsedSeconds(isPending, latest?.submittedAt);

  // The Dashboard's quick launcher hands a draft over through router state
  // rather than running its own analysis, so there is one place that spends
  // quota. It prefills only; submitting stays an explicit action here.
  const location = useLocation();
  const handoff = location.state as Partial<CreatorFormValues> | null;
  const setUrl = url.set;

  useEffect(() => {
    if (!handoff?.script) return;
    form.reset({
      ...creatorFormDefaults,
      ...handoff,
      script: handoff.script,
    });
    // The draft is edited on the Idea stage, even when an earlier result is still shown.
    setUrl({ stage: "idea" });
  }, [form, setUrl, handoff?.script, handoff?.language, handoff?.region]);

  const options = useMemo(
    () => (data ? buildPackageOptions(data, submitted ?? {}) : []),
    [data, submitted],
  );

  const [choice, setChoice] = useState<Choice | null>(null);
  const [checks, setChecks] = useState<Checks | null>(null);
  const current = choice && choice.run === runKey ? choice : null;

  // A choice recorded before the creator left the page is still on the server.
  const runId = typeof data?.history_run_id === "number" ? data.history_run_id : null;
  const savedRun = useHistoryRun(data && !current ? runId : null);
  const recorded = savedRun.data?.selected_package?.generated_package_id ?? null;
  const restored = !current && recorded ? (options.find((option) => option.packageId === recorded) ?? null) : null;

  // Only an explicit choice is "selected"; until then the primary is a preview.
  const chosen = current ? (options.find((option) => option.id === current.optionId) ?? null) : restored;
  const selectionStatus: SelectionStatus = current?.status ?? (restored ? "saved" : "unrecorded");
  const preview = chosen ?? options[0] ?? null;
  const checklist =
    checks && chosen && checks.run === runKey && checks.optionId === chosen.id ? checks.state : freshChecklist();

  const researchStatus: ResearchStatus = isPending
    ? "loading"
    : failure
      ? "error"
      : data
        ? researchHasEvidence(data)
          ? "available"
          : "unavailable"
        : "no-research";

  const handleSubmit = form.handleSubmit((values) => {
    // A new run opens on Packaging once it completes.
    setUrl({ stage: null });
    analyze.mutate(values);
  });

  // Saves run one after another, so the last click is also the last write;
  // only the newest click reports its outcome.
  const saveChain = useRef<Promise<unknown>>(Promise.resolve());
  const saveSeq = useRef(0);

  const handleSelect = useCallback(
    (optionId: string) => {
      const option = options.find((item) => item.id === optionId);
      // A title-only alternative has no server package to record.
      if (!option?.packageId || runKey === null) return;
      const packageId = option.packageId;
      const seq = ++saveSeq.current;

      if (!runId) {
        setChoice({ run: runKey, optionId, status: "error" });
        toast.error("The saved analysis ID is unavailable; selection was not recorded.");
        return;
      }

      setChoice({ run: runKey, optionId, status: "saving" });
      const save = saveChain.current
        .catch(() => undefined)
        .then(() => saveSelection({ runId, packageId }));
      saveChain.current = save;
      save.then(
        () => {
          if (seq === saveSeq.current) setChoice({ run: runKey, optionId, status: "saved" });
        },
        (error: unknown) => {
          if (seq !== saveSeq.current) return;
          setChoice({ run: runKey, optionId, status: "error" });
          toast.error(formatApiError(error, "Package selection could not be saved."));
        },
      );
    },
    [options, runKey, runId, saveSelection],
  );

  const handleExport = useCallback(() => {
    if (!data || !chosen) {
      toast.error("Run Analyze and select a package before exporting.");
      return;
    }

    const payload = {
      ...data,
      creator_workflow_local: {
        selected_package_id: chosen.packageId,
        selected_package: { ...chosen },
        checklist: { ...checklist },
        persistence:
          selectionStatus === "saved"
            ? "Creator selection saved to SQLite History; never sent to YouTube."
            : "Selection was not confirmed as saved.",
        publishing: "Manual publishing outside Win-Engine OS.",
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `seo-analysis-${Date.now()}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 0);
    toast.success("Full analysis and local decision exported.");
  }, [data, chosen, checklist, selectionStatus]);

  const handleToggleChecklist = useCallback(
    (key: ChecklistKey, checked: boolean) => {
      if (runKey === null || !chosen) return;
      setChecks((prior) => ({
        run: runKey,
        optionId: chosen.id,
        state: {
          ...(prior && prior.run === runKey && prior.optionId === chosen.id ? prior.state : freshChecklist()),
          [key]: checked,
        },
      }));
    },
    [runKey, chosen],
  );

  // The stage lives in the URL; later stages open only once there is a result.
  const unlocked = Boolean(data);
  const requested = url.get("stage");
  const stage: StageKey = !unlocked ? "idea" : isStageKey(requested) ? requested : "packaging";
  const setStage = (next: StageKey) => setUrl({ stage: next });

  // A new stage starts at the top of the page, not wherever the last one ended.
  useEffect(() => {
    if (window.scrollY <= 120) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  }, [stage]);

  const stageIndex = STAGES.findIndex((item) => item.key === stage);
  const currentStage = STAGES[stageIndex] ?? STAGES[0];

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
              {/* Gemini's writing is generated, like the fallback's; neither is an observation. */}
              <EvidenceChip tone="warn">
                {data.generation_source === "gemini" ? "Written with Gemini" : "Local fallback"}
              </EvidenceChip>
              <EvidenceChip tone={warningCount ? "warn" : "neutral"}>
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

        {isPending ? <AnalysisProgress elapsed={elapsed} /> : null}

        {failure ? (
          <ErrorState
            message={apiErrorMessage(failure, "Analysis failed.")}
            requestId={apiRequestId(failure)}
            onRetry={() => handleSubmit()}
          />
        ) : null}

        {/* The input stage stays mounted so a refined run can be submitted from
            any later stage without losing what was typed. */}
        <div className={stage === "idea" ? "" : "hidden"}>
          <IdeaStage form={form} onSubmit={handleSubmit} isPending={isPending} />
        </div>

        <div key={stage} className="animate-fade-up">
          {stage === "brief" ? (
            <BriefStage
              brief={data ? (asObject(data.creator_brief) as CreatorBrief) : null}
              submitted={submitted}
            />
          ) : null}

          {stage === "research" ? (
            <ResearchStage
              data={data}
              status={researchStatus}
              errorMessage={failure ? formatApiError(failure, "Analysis failed.") : undefined}
            />
          ) : null}

          {stage === "angle" ? <AngleStage data={data} selected={chosen} /> : null}

          {stage === "packaging" ? (
            <PackagingStage
              data={data}
              options={options}
              preview={preview}
              chosen={chosen}
              selectionStatus={selectionStatus}
              onSelect={handleSelect}
              durationSeconds={submitted?.duration_seconds}
            />
          ) : null}

          {stage === "compare" ? (
            <CompareStage
              options={options}
              chosenId={chosen?.id ?? null}
              selectionStatus={selectionStatus}
              onSelect={handleSelect}
            />
          ) : null}

          {stage === "decision" ? (
            <DecisionStage
              data={data}
              selected={chosen}
              selectionStatus={selectionStatus}
              onExport={handleExport}
            />
          ) : null}

          {stage === "checklist" ? (
            <ChecklistStage
              selected={chosen}
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
