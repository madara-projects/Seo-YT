import { asArray } from "@/lib/utils";
import type { AiShortsPlan, AiShortsShot } from "@/api/aiShortsTypes";
import { FlowGuide } from "./FlowGuide";
import { MoodAudio } from "./MoodAudio";
import { PlanHeader } from "./PlanHeader";
import { ShortsPackage } from "./ShortsPackage";
import { ShotCards } from "./ShotCards";
import { TextOverlay } from "./TextOverlay";

/**
 * One plan, top to bottom: what it is for, the prompts, how to run them in
 * Flow, the mood behind them, the text on screen, and the package to upload
 * with. Mount it keyed by plan id so the Flow checklist starts afresh.
 */
export function PlanResults({
  plan,
  onRetry,
  retrying,
}: {
  plan: AiShortsPlan;
  onRetry: () => void;
  retrying: boolean;
}) {
  return (
    <div className="space-y-5" data-testid="plan-results">
      <PlanHeader plan={plan} onRetry={onRetry} retrying={retrying} />
      <ShotCards shots={asArray<AiShortsShot>(plan.shots)} />
      <FlowGuide steps={asArray<string>(plan.flow_steps)} cautions={asArray<string>(plan.cautions)} />
      {/* Side by side only where the results column is wide enough for two readable cards. */}
      <div className="grid gap-5 2xl:grid-cols-2">
        <MoodAudio plan={plan} />
        <TextOverlay plan={plan} />
      </div>
      <ShortsPackage plan={plan} />
    </div>
  );
}
