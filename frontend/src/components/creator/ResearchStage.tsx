import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceChip, SourceLegend, type EvidenceTone } from "@/components/common/EvidenceChip";
import { EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { asArray, asObject, displayValue, formatNumber } from "@/lib/utils";
import type { AnalyzeResponse, ResearchStatus } from "@/api/types";
import type {
  EntitySignal,
  KeywordSignal,
  RepeatedTitlePattern,
  ResearchQuery,
  SmallChannelWinner,
  TopOpportunity,
  YoutubeResult,
} from "@/api/types";

function Panel({
  title,
  chip,
  tone,
  children,
  wide,
}: {
  title: string;
  chip: string;
  tone?: EvidenceTone;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <Card className={wide ? "lg:col-span-2" : undefined}>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle>{title}</CardTitle>
        <EvidenceChip tone={tone}>{chip}</EvidenceChip>
      </CardHeader>
      <CardContent className="space-y-2.5">{children}</CardContent>
    </Card>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <p className="text-xs font-semibold text-foreground">{label}</p>
      <div className="mt-1 text-xs leading-relaxed text-muted-foreground">{children}</div>
    </div>
  );
}

const STATUS_COPY: Record<ResearchStatus, string> = {
  loading:
    "The Analyze request is running. Opening this stage never starts a separate research request.",
  available:
    "Research returned by the analysis pipeline, shown with its source and limitations.",
  "no-research":
    "Run Analyze first. Stage navigation never calls YouTube, Gemini, OAuth, or another research endpoint.",
  unavailable:
    "The analysis completed, but no research evidence was returned. No substitute score or competitor claim is shown.",
  error: "The Analyze request failed; research is unavailable for this run.",
};

export function ResearchStage({
  data,
  status,
  errorMessage,
}: {
  data: AnalyzeResponse | null;
  status: ResearchStatus;
  errorMessage?: string;
}) {
  if (status === "error") {
    return <ErrorState message={errorMessage || STATUS_COPY.error} />;
  }

  if (status !== "available" || !data) {
    return (
      <EmptyState
        title={status === "unavailable" ? "No research evidence returned" : "No research yet"}
        description={STATUS_COPY[status]}
      />
    );
  }

  const decision = asObject(data.research_decision);
  const queries = asArray<ResearchQuery>(data.research_queries);
  const results = asArray<YoutubeResult>(data.youtube_results);
  const opportunities = asArray<TopOpportunity>(data.top_opportunities);
  const keywords = asArray<KeywordSignal>(data.keyword_signals);
  const entities = asArray<EntitySignal>(data.entity_signals);
  const thumbnails = asObject(data.thumbnail_intelligence);
  const warnings = asArray<string>(data.research_warnings);
  const counts = asObject(thumbnails.quality_counts);

  const generationSource =
    data.generation_source === "gemini"
      ? "AI suggestion / Gemini"
      : data.generation_source === "fallback"
        ? "Local fallback"
        : "Unavailable";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Research synthesis" chip="Local heuristic" tone="warn" wide>
          <Item label="Recommended angle">{displayValue(decision.recommended_angle)}</Item>
          <Item label="Reasoning">{displayValue(decision.reason)}</Item>
          <div className="grid gap-2.5 sm:grid-cols-2">
            <Item label="Synthesis confidence">{displayValue(decision.confidence)}</Item>
            <Item label="Dominant public title pattern">
              {displayValue(decision.dominant_competitor_pattern)}
            </Item>
          </div>

          {asArray<RepeatedTitlePattern>(decision.repeated_title_patterns).length ? (
            <div className="space-y-2">
              {asArray<RepeatedTitlePattern>(decision.repeated_title_patterns).map((row, index) => (
                <Item key={index} label={displayValue(row.pattern)}>
                  Observed in {displayValue(row.count, "an unavailable number of")} returned public
                  result titles.
                </Item>
              ))}
            </div>
          ) : (
            <UnavailableNote>No repeated title pattern was returned.</UnavailableNote>
          )}

          {asArray<SmallChannelWinner>(decision.small_channel_winners).length ? (
            <div className="space-y-2">
              {asArray<SmallChannelWinner>(decision.small_channel_winners).map((row, index) => (
                <Item key={index} label={displayValue(row.title)}>
                  {displayValue(row.channel)} · {formatNumber(row.views)} views reported by YouTube
                </Item>
              ))}
            </div>
          ) : (
            <UnavailableNote>No small-channel outlier observation was returned.</UnavailableNote>
          )}

          {asArray<string>(decision.avoid).length ? (
            <div className="space-y-2">
              {asArray<string>(decision.avoid).map((row, index) => (
                <Item key={index} label="Avoid">
                  {displayValue(row)}
                </Item>
              ))}
            </div>
          ) : (
            <UnavailableNote>No avoidance guidance was returned.</UnavailableNote>
          )}
        </Panel>

        <Panel title="Public YouTube observations" chip="Public observation" tone="info" wide>
          {results.length ? (
            <>
              <div className="-mx-1 overflow-x-auto scrollbar-thin">
                <table className="w-full min-w-[34rem] text-left text-xs">
                  <thead>
                    <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                      <th scope="col" className="px-1 pb-2 font-semibold">Public result</th>
                      <th scope="col" className="px-1 pb-2 font-semibold">Published</th>
                      <th scope="col" className="px-1 pb-2 font-semibold">Views</th>
                      <th scope="col" className="px-1 pb-2 font-semibold">Outlier</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {results.slice(0, 8).map((row, index) => (
                      <tr key={row.video_id ?? index}>
                        <td className="px-1 py-2.5">
                          <p className="font-semibold text-foreground">{displayValue(row.title)}</p>
                          <p className="text-muted-foreground">{displayValue(row.channel_title)}</p>
                        </td>
                        <td className="px-1 py-2.5 text-muted-foreground">
                          {displayValue(row.published_at)}
                        </td>
                        <td className="numeric px-1 py-2.5 text-muted-foreground">
                          {formatNumber(row.view_count)}
                        </td>
                        <td className="numeric px-1 py-2.5 text-muted-foreground">
                          {displayValue(row.outlier_score)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                These are public observations returned by YouTube research. They do not prove
                causation, ranking, or future performance.
              </p>
            </>
          ) : (
            <UnavailableNote>
              No public YouTube results were returned for this analysis.
            </UnavailableNote>
          )}
        </Panel>

        <Panel title="Executed research queries" chip="Research context" tone="info" wide>
          {queries.length ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {queries.map((row, index) => (
                <Item key={index} label={displayValue(row.type)}>
                  {displayValue(row.query)}
                </Item>
              ))}
            </div>
          ) : (
            <UnavailableNote>No research queries were returned.</UnavailableNote>
          )}
        </Panel>

        <Panel title="Local scoring candidates" chip="Local heuristic" tone="warn">
          {opportunities.length ? (
            opportunities.slice(0, 3).map((row, index) => (
              <Item key={index} label={displayValue(row.title)}>
                Score {displayValue(row.outlier_score)} ·{" "}
                {displayValue(asArray<string>(row.opportunity_reasons).join("; "), "No reason returned")}
              </Item>
            ))
          ) : (
            <UnavailableNote>No local scoring candidates were returned.</UnavailableNote>
          )}
        </Panel>

        <Panel title="Keyword signals" chip="Local heuristic" tone="warn">
          {keywords.length ? (
            keywords.slice(0, 10).map((row, index) => (
              <Item key={index} label={displayValue(row.keyword)}>
                Mentions: {displayValue(row.mentions)} · Strength: {displayValue(row.strength)}
              </Item>
            ))
          ) : (
            <UnavailableNote>No keyword signals were returned.</UnavailableNote>
          )}
        </Panel>

        <Panel title="Entity signals" chip="Local heuristic" tone="warn">
          {entities.length ? (
            entities.slice(0, 10).map((row, index) => (
              <Item key={index} label={displayValue(row.entity)}>
                Type: {displayValue(row.type)} · Mentions: {displayValue(row.mentions)}
              </Item>
            ))
          ) : (
            <UnavailableNote>No entity signals were returned.</UnavailableNote>
          )}
        </Panel>

        <Panel title="Thumbnail research context" chip="Public metadata" tone="info">
          {Object.keys(thumbnails).length ? (
            <>
              <Item label="Available thumbnail metadata">
                Max: {displayValue(counts.maxres)} · High: {displayValue(counts.high)} · Medium:{" "}
                {displayValue(counts.medium)} · Default: {displayValue(counts.default)}
              </Item>
              <Item label="Low-resolution observations">
                {displayValue(thumbnails.low_resolution_count)}
              </Item>
              <Item label="Local setup suggestion">{displayValue(thumbnails.recommendation)}</Item>
            </>
          ) : (
            <UnavailableNote>No thumbnail metadata was returned.</UnavailableNote>
          )}
        </Panel>

        <Panel
          title="Generation context"
          chip={generationSource}
          tone={data.generation_source === "gemini" ? "info" : "warn"}
        >
          <Item label="Intent">{displayValue(data.intent)}</Item>
          <Item label="Content angle">{displayValue(data.content_angle)}</Item>
          <Item label="Cache policy">
            {displayValue(data.cache_policy)} — technical context, not evidence quality.
          </Item>
        </Panel>

        <Panel
          title="Research warnings and limits"
          chip={warnings.length ? "Review required" : "No warnings"}
          tone={warnings.length ? "warn" : "ok"}
          wide
        >
          {warnings.length ? (
            <ul className="space-y-2">
              {warnings.map((warning, index) => (
                <li
                  key={index}
                  className="rounded-md border border-tone-warn-border bg-tone-warn-bg px-3 py-2 text-xs text-foreground"
                >
                  {warning}
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>
              No research warning was returned; absence of a warning is not proof of quality or
              causation.
            </UnavailableNote>
          )}
        </Panel>
      </div>

      <SourceLegend />
    </div>
  );
}
