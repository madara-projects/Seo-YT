import { Tags } from "lucide-react";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { humanize } from "@/lib/labels";
import { asArray, asObject } from "@/lib/utils";
import type { KeywordResearch, SelectedKeyword } from "@/api/types";

/** Tags shown with their evidence; the full list is in the package itself. */
const SHOWN = 10;

const STATUS_LABELS: Record<string, string> = {
  youtube_evidence: "YouTube evidence",
  semantic_only: "Script only",
};

/** The yt/shorts discovery tags are a format choice, not a claim about the subject. */
function isFormatTag(item: SelectedKeyword): boolean {
  return item.classification === "platform_format";
}

function matches(item: SelectedKeyword): number {
  const count = Number(item.evidence_count ?? 0);
  return Number.isFinite(count) && count > 0 ? count : 0;
}

function tagNote(item: SelectedKeyword): string {
  if (isFormatTag(item)) return "Format tag";
  const count = matches(item);
  return count ? `Matched ${count} sampled ${count === 1 ? "result" : "results"}` : "From the script only";
}

/**
 * How the final tags were chosen (`keyword_research`), ported from the
 * classic dashboard. A match means the phrase appears in the metadata of a
 * sampled public result: it supports relevance, and says nothing about how
 * many people search for it. YouTube's API reports no search volume.
 */
export function KeywordResearchPanel({ research }: { research: KeywordResearch | undefined }) {
  const data = asObject(research) as KeywordResearch;
  const hasResearch = Object.keys(data).length > 0;
  const selected = asArray<SelectedKeyword>(data.selected_keywords).filter((item) => item?.keyword);
  const subject = selected.filter((item) => !isFormatTag(item));
  const backed = subject.filter((item) => matches(item) > 0).length;
  const sourceOnly = subject.length - backed;
  const status = String(data.status ?? "").trim();
  const statusLabel = STATUS_LABELS[status] ?? (status ? humanize(status) : "Limited");

  return (
    <Panel
      icon={Tags}
      title="Research-backed tag selection"
      description={
        data.confidence === "observed_youtube_relevance"
          ? "Chosen from the script's topics and checked against sampled YouTube results."
          : "Chosen from the script's topics alone, because YouTube research was limited."
      }
      aside={<EvidenceChip tone={status === "youtube_evidence" ? "ok" : "warn"}>{statusLabel}</EvidenceChip>}
      data-testid="keyword-research"
    >
      {!hasResearch ? (
        <UnavailableNote>Tag research wasn't returned for this run.</UnavailableNote>
      ) : (
        <div className="space-y-3">
          <p className="text-[0.8125rem] leading-relaxed text-foreground">
            {subject.length
              ? `${backed} subject ${backed === 1 ? "tag matches" : "tags match"} sampled public result metadata; ${sourceOnly} ${sourceOnly === 1 ? "is" : "are"} source-only.`
              : "No subject tag was selected."}{" "}
            <span className="font-medium">Search volume: unavailable.</span>
          </p>
          {selected.length ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="Selected tags and their evidence">
              {selected.slice(0, SHOWN).map((item, index) => (
                <li
                  key={`${item.keyword}-${index}`}
                  className="rounded-lg border border-border bg-elevated px-2.5 py-1.5"
                >
                  <span className="block text-xs font-medium text-foreground">{item.keyword}</span>
                  <span className="block text-[0.6875rem] text-muted-foreground">{tagNote(item)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>No strong keyword candidates were available.</UnavailableNote>
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">
            The YouTube Data API returns sampled matching results, not keyword search volume, so no
            tag is ranked by how often it is searched.
          </p>
        </div>
      )}
    </Panel>
  );
}
