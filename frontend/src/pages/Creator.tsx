import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutationState, type MutationStatus } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/States";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AnalysisProgress } from "@/components/creator/AnalysisProgress";
import { ChecklistStage } from "@/components/creator/ChecklistStage";
import { CompareStage } from "@/components/creator/CompareStage";
import { DecisionStage } from "@/components/creator/DecisionStage";
import { InsightsTab } from "@/components/creator/InsightsTab";
import { PackagingStage } from "@/components/creator/PackagingStage";
import { ResultsHeader } from "@/components/creator/ResultsHeader";
import { SetupScreen } from "@/components/creator/SetupScreen";
import { useAnalyze, useSelectPackage } from "@/hooks/useAnalyze";
import { useElapsedSeconds } from "@/hooks/useElapsed";
import { useHistoryRun } from "@/hooks/useHistory";
import { mutationKeys } from "@/hooks/queryKeys";
import { useUrlState } from "@/hooks/useUrlState";
import { apiErrorMessage, apiRequestId, formatApiError } from "@/api/client";
import { buildPackageOptions, researchHasEvidence } from "@/lib/packages";
import {
  RESULT_TABS,
  STAGE_TO_TAB,
  freshChecklist,
  type ChecklistKey,
  type ChecklistState,
  type ResultTab,
} from "@/lib/creatorConstants";
import { formatLabel, outputLanguageLabel, readRememberedFormat, regionLabel } from "@/lib/creatorFormat";
import { asArray, asObject } from "@/lib/utils";
import {
  creatorFormDefaults,
  creatorFormSchema,
  videoFormatFor,
  type CreatorFormValues,
} from "@/schemas/creator";
import type { AnalyzeResponse, ResearchStatus, SelectionStatus } from "@/api/types";
import type { EvidenceTone } from "@/components/common/EvidenceChip";

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

const TAB_KEYS = new Set<string>(RESULT_TABS.map((item) => item.key));

function isResultTab(value: string): value is ResultTab {
  return TAB_KEYS.has(value);
}

const LONG_FORMATS = new Set(["long_form", "talking_head", "tutorial", "vlog", "review", "story", "challenge"]);

/** The header's format chip: the creator's choice, or what the backend detected when asked to. */
function formatChip(submitted: CreatorFormValues, brief: Record<string, unknown>): { text: string; tone: EvidenceTone } {
  if (submitted.format_choice !== "auto") return { text: formatLabel(submitted), tone: "ok" };
  const detected = String(brief.video_format ?? "").trim();
  if (detected === "youtube_shorts") return { text: "Short · detected", tone: "warn" };
  if (LONG_FORMATS.has(detected)) return { text: "Long video · detected", tone: "warn" };
  return { text: "Format not detected", tone: "neutral" };
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

/**
 * The Creator: a setup screen that asks what is being made and for the
 * script, then a results screen with the package and everything behind it in
 * four tabs. Which screen and tab are showing live in the URL (`?edit=1`,
 * `?tab=`); links to the old eight stages (`?stage=`) land on the tab that now
 * holds that stage.
 */
export default function CreatorPage() {
  const latest = useLatestAnalyzeRun();
  const analyze = useAnalyze();
  const selectPackage = useSelectPackage();
  const saveSelection = selectPackage.mutateAsync;
  const url = useUrlState();
  const setUrl = url.set;

  const form = useForm<CreatorFormValues>({
    resolver: zodResolver(creatorFormSchema),
    // Back on the page during or after a run, the form shows that run's input;
    // otherwise it starts from the last format chosen.
    defaultValues: latest?.variables
      ? { ...creatorFormDefaults, ...latest.variables }
      : { ...creatorFormDefaults, ...readRememberedFormat() },
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

  useEffect(() => {
    if (!handoff?.script) return;
    form.reset({
      ...creatorFormDefaults,
      ...readRememberedFormat(),
      ...handoff,
      script: handoff.script,
    });
    // The draft is edited on the setup screen, even when an earlier result exists.
    setUrl({ edit: "1", tab: null, stage: null });
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
    // A new run opens on its Package tab once it completes.
    setUrl({ edit: null, tab: null, stage: null });
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
      toast.error("Choose a package with \"Use\" before exporting.");
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

  // Which screen and tab: the results once there is a result, unless the
  // creator went back to edit; an old `?stage=` link picks the matching tab.
  const legacyStage = STAGE_TO_TAB[url.get("stage")];
  const editing = url.get("edit") === "1" || legacyStage === "setup";
  const showResults = Boolean(data) && !editing;
  const requestedTab = url.get("tab");
  const tab: ResultTab = isResultTab(requestedTab)
    ? requestedTab
    : legacyStage && legacyStage !== "setup"
      ? legacyStage
      : "package";
  const setTab = (next: string) => setUrl({ tab: next === "package" ? null : next, stage: null });

  // A new screen starts at the top of the page, not wherever the last one ended.
  useEffect(() => {
    if (window.scrollY <= 120) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  }, [showResults]);

  const warnings = asArray<string>(data?.research_warnings);
  const brief = asObject(data?.creator_brief);
  const sent: Record<string, unknown> | null = submitted ? { ...submitted, video_format: videoFormatFor(submitted) } : null;
  const chip = submitted ? formatChip(submitted, brief) : { text: "Format unknown", tone: "neutral" as EvidenceTone };

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Studio"
        icon={Sparkles}
        title="Creator"
        description="Turn a script or idea into a ready-to-upload title, description and tags. Nothing here uploads, publishes, or changes a YouTube video."
      />

      {showResults && data ? (
        <div className="space-y-5">
          <ResultsHeader
            script={String(submitted?.script ?? "")}
            formatText={chip.text}
            formatTone={chip.tone}
            languageText={
              submitted ? `${outputLanguageLabel(submitted.language)} · ${regionLabel(submitted.region)}` : "Language unknown"
            }
            writtenWithGemini={data.generation_source === "gemini"}
            warnings={warnings}
            onEdit={() => setUrl({ edit: "1", stage: null })}
            onNew={() => {
              form.reset({ ...creatorFormDefaults, ...readRememberedFormat() });
              setUrl({ edit: "1", tab: null, stage: null });
            }}
            onOpenResearch={() => setTab("research")}
          />

          <Tabs value={tab} onValueChange={setTab}>
            <div className="-mx-4 overflow-x-auto px-4 pb-1 scrollbar-none sm:mx-0 sm:px-0">
              <TabsList aria-label="Package results">
                {RESULT_TABS.map((item) => (
                  <TabsTrigger key={item.key} value={item.key}>
                    {item.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            <TabsContent value="package">
              <PackagingStage
                data={data}
                options={options}
                chosen={chosen}
                selectionStatus={selectionStatus}
                onSelect={handleSelect}
                durationSeconds={submitted?.duration_seconds}
              />
            </TabsContent>
            <TabsContent value="compare">
              <CompareStage
                options={options}
                chosenId={chosen?.id ?? null}
                selectionStatus={selectionStatus}
                onSelect={handleSelect}
              />
            </TabsContent>
            <TabsContent value="research">
              <InsightsTab
                data={data}
                researchStatus={researchStatus}
                errorMessage={failure ? formatApiError(failure, "Analysis failed.") : undefined}
                selected={chosen}
                submitted={sent}
              />
            </TabsContent>
            <TabsContent value="publish">
              <div className="space-y-5">
                <DecisionStage data={data} selected={chosen} selectionStatus={selectionStatus} onExport={handleExport} />
                <ChecklistStage
                  selected={chosen}
                  checklist={checklist}
                  onToggle={handleToggleChecklist}
                  onExport={handleExport}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      ) : (
        <div className="space-y-5">
          {isPending ? <AnalysisProgress elapsed={elapsed} /> : null}
          {failure ? (
            <ErrorState
              message={apiErrorMessage(failure, "Analysis failed.")}
              requestId={apiRequestId(failure)}
              onRetry={() => handleSubmit()}
            />
          ) : null}
          <SetupScreen
            form={form}
            onSubmit={handleSubmit}
            isPending={isPending}
            onBackToResults={data ? () => setUrl({ edit: null, stage: null }) : undefined}
          />
        </div>
      )}
    </div>
  );
}
