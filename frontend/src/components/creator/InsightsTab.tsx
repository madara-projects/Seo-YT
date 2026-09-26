import { useState } from "react";
import { ChevronDown, ScrollText } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { AngleStage } from "./AngleStage";
import { BriefStage } from "./BriefStage";
import { KeywordResearchPanel } from "./KeywordResearchPanel";
import { ResearchStage } from "./ResearchStage";
import type { AnalyzeResponse, CreatorBrief, PackageOption, ResearchStatus } from "@/api/types";

/**
 * Everything behind the package, in reading order: what YouTube research
 * showed, how the tags were chosen, the angle with its hook, pacing and
 * retention checks, and, folded away, which inputs were the creator's own.
 */
export function InsightsTab({
  data,
  researchStatus,
  errorMessage,
  selected,
  submitted,
}: {
  data: AnalyzeResponse;
  researchStatus: ResearchStatus;
  errorMessage?: string;
  selected: PackageOption | null;
  /** The inputs as sent, with the format the request carried. */
  submitted: Record<string, unknown> | null;
}) {
  const [briefOpen, setBriefOpen] = useState(false);

  return (
    <div className="space-y-8">
      <ResearchStage data={data} status={researchStatus} errorMessage={errorMessage} />
      <KeywordResearchPanel research={data.keyword_research} />
      <AngleStage data={data} selected={selected} />

      <Collapsible open={briefOpen} onOpenChange={setBriefOpen}>
        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-5"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <ScrollText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block font-display text-base font-semibold text-foreground">
                    What you supplied vs inferred
                  </span>
                  <span className="block text-[0.8125rem] text-muted-foreground">
                    Each brief value, labelled by where it came from.
                  </span>
                </span>
              </span>
              <ChevronDown
                className={cn("size-4 shrink-0 text-muted-foreground transition-transform duration-200", briefOpen && "rotate-180")}
                aria-hidden="true"
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="border-t border-border p-4 sm:p-5">
              <BriefStage brief={data.creator_brief ? (data.creator_brief as CreatorBrief) : null} submitted={submitted} />
            </div>
          </CollapsibleContent>
        </section>
      </Collapsible>
    </div>
  );
}
