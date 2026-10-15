import { useState } from "react";
import { Clapperboard, ListChecks, Package, Palette, type LucideIcon } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PLAN_TABS, isPlanTab, packageFindings, readPlanTab, rememberPlanTab, type PlanTab } from "@/lib/aiShortsFormat";
import { asArray, cn } from "@/lib/utils";
import type { AiShortsPlan, AiShortsShot } from "@/api/aiShortsTypes";
import { FlowGuide } from "./FlowGuide";
import { PlanHeader } from "./PlanHeader";
import { PromptsTab } from "./PromptsTab";
import { SceneNotes } from "./SceneNotes";
import { ShortsPackage } from "./ShortsPackage";

const TAB_ICONS: Record<PlanTab, LucideIcon> = {
  prompts: Clapperboard,
  package: Package,
  flow: ListChecks,
  notes: Palette,
};

/** A panel's keyboard focus shows, as everywhere else in the app. */
const PANEL_FOCUS =
  "rounded-2xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/** What the creator did on this screen for one plan: ticked Flow steps and the title chosen for the package. */
interface PlanScreenState {
  planId: number;
  done: ReadonlySet<number>;
  title: number;
}

const freshState = (planId: number): PlanScreenState => ({ planId, done: new Set(), title: 0 });

/**
 * One AI Short: a compact header, then tabs for the prompts, the upload
 * package, the Flow steps and the scene notes. The last tab is remembered;
 * ticks and the chosen title survive a tab change and reset for another plan.
 * `context="history"` drops Write again and the link back to History.
 */
export function PlanView({
  plan,
  onRetry,
  retrying = false,
  context = "page",
}: {
  plan: AiShortsPlan;
  onRetry?: () => void;
  retrying?: boolean;
  context?: "page" | "history";
}) {
  const [tab, setTab] = useState<PlanTab>(readPlanTab);
  const [screen, setScreen] = useState<PlanScreenState>(() => freshState(plan.id));
  const current = screen.planId === plan.id ? screen : freshState(plan.id);
  const onPage = context === "page";

  const shots = asArray<AiShortsShot>(plan.shots);
  const steps = asArray<string>(plan.flow_steps);
  const cautions = asArray<string>(plan.cautions);
  const doneCount = steps.filter((_, index) => current.done.has(index)).length;
  const notes = packageFindings(plan.package?.generation_quality);
  const notesFailed = notes.some((note) => note.severity === "issue");

  const update = (change: (state: PlanScreenState) => PlanScreenState) =>
    setScreen((prior) => change(prior.planId === plan.id ? prior : freshState(plan.id)));

  const toggleStep = (index: number, checked: boolean) =>
    update((state) => {
      const done = new Set(state.done);
      if (checked) done.add(index);
      else done.delete(index);
      return { ...state, done };
    });

  const changeTab = (value: string) => {
    if (!isPlanTab(value)) return;
    setTab(value);
    rememberPlanTab(value);
  };

  return (
    <div className="space-y-4" data-testid="plan-results">
      <PlanHeader
        key={plan.id}
        plan={plan}
        shots={shots}
        onRetry={onPage ? onRetry : undefined}
        retrying={retrying}
        showHistoryLink={onPage}
        onOpenPackage={() => changeTab("package")}
      />

      <Tabs value={tab} onValueChange={changeTab}>
        {/* The tabs scroll sideways on a narrow screen rather than wrap. */}
        <div className="overflow-x-auto pb-1 scrollbar-none">
          <TabsList aria-label="AI Short sections">
            {PLAN_TABS.map((item) => {
              const Icon = TAB_ICONS[item.value];
              return (
                <TabsTrigger key={item.value} value={item.value}>
                  <Icon aria-hidden="true" />
                  {item.label}
                  {/* The package's quality notes show from any tab. */}
                  {item.value === "package" && notes.length ? (
                    <>
                      <span
                        className={cn(
                          "numeric grid h-4 min-w-4 place-items-center rounded-full border px-1 text-[0.625rem] font-semibold leading-none",
                          notesFailed
                            ? "border-tone-bad-border bg-tone-bad-bg text-tone-bad"
                            : "border-tone-warn-border bg-tone-warn-bg text-tone-warn",
                        )}
                        aria-hidden="true"
                        data-testid="package-notes-badge"
                      >
                        {notes.length}
                      </span>
                      <span className="sr-only">{` (${notes.length} ${notes.length === 1 ? "note" : "notes"})`}</span>
                    </>
                  ) : null}
                  {item.value === "flow" && steps.length ? (
                    <>
                      <span className="numeric text-[0.6875rem] text-muted-foreground" aria-hidden="true">
                        {doneCount}/{steps.length}
                      </span>
                      <span className="sr-only">{` (${doneCount} of ${steps.length} steps done)`}</span>
                    </>
                  ) : null}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </div>

        <TabsContent value="prompts" className={PANEL_FOCUS}>
          <PromptsTab key={plan.id} plan={plan} shots={shots} />
        </TabsContent>
        <TabsContent value="package" className={PANEL_FOCUS}>
          <ShortsPackage
            plan={plan}
            chosenTitle={current.title}
            onChooseTitle={(title) => update((state) => ({ ...state, title }))}
          />
        </TabsContent>
        <TabsContent value="flow" className={PANEL_FOCUS}>
          <FlowGuide steps={steps} cautions={cautions} shots={shots} done={current.done} onToggle={toggleStep} />
        </TabsContent>
        <TabsContent value="notes" className={PANEL_FOCUS}>
          <SceneNotes plan={plan} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
