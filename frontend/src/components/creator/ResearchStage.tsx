import {
  AlertTriangle,
  Brain,
  Cpu,
  Hash,
  Image as ImageIcon,
  Search,
  Sigma,
  Tags,
  Telescope,
  Youtube,
} from "lucide-react";
import { EvidenceChip, SourceLegend, type EvidenceTone } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { EmptyState, ErrorState, UnavailableNote } from "@/components/common/States";
import { VideoThumb } from "@/components/common/VideoThumb";
import { asArray, asObject, displayValue, formatNumber, UNAVAILABLE } from "@/lib/utils";
import { shortDate } from "@/lib/historyFormat";
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

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Inset>
      <p className="text-[0.8125rem] font-medium text-foreground">{label}</p>
      <div className="mt-1 text-[0.8125rem] leading-relaxed text-muted-foreground">{children}</div>
    </Inset>
  );
}

function Summary({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-card">
      <span className="grid size-9 place-items-center rounded-xl bg-brand-soft text-brand" aria-hidden="true">
        <Icon className="size-4" />
      </span>
      <div>
        <p className="font-display text-xl font-semibold leading-none text-foreground">
          {value.toLocaleString()}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{label}</p>
      </div>
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

/** A date YouTube sent in a form that doesn't parse is shown as sent rather than dropped. */
function publishedLabel(value?: string): string {
  if (!value) return UNAVAILABLE;
  const formatted = shortDate(value);
  return formatted === UNAVAILABLE ? value : formatted;
}

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
        icon={Telescope}
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
  const patterns = asArray<RepeatedTitlePattern>(decision.repeated_title_patterns);
  const winners = asArray<SmallChannelWinner>(decision.small_channel_winners);
  const avoid = asArray<string>(decision.avoid);

  const generationSource =
    data.generation_source === "gemini"
      ? "AI suggestion / Gemini"
      : data.generation_source === "fallback"
        ? "Local fallback"
        : "Unavailable";
  // Gemini's text is generated like the fallback's; only an observation of YouTube is "info".
  const generationTone: EvidenceTone = generationSource === "Unavailable" ? "neutral" : "warn";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Summary icon={Youtube} label="Public results" value={results.length} />
        <Summary icon={Search} label="Queries run" value={queries.length} />
        <Summary icon={Hash} label="Keyword signals" value={keywords.length} />
        <Summary icon={AlertTriangle} label="Warnings" value={warnings.length} />
      </div>

      <Panel
        icon={Brain}
        title="Research synthesis"
        aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-brand-border bg-brand-soft/60 p-4">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-brand">
              Recommended angle
            </p>
            <p className="mt-1.5 font-display text-lg font-semibold leading-snug text-foreground">
              {displayValue(decision.recommended_angle)}
            </p>
          </div>
          <Item label="Reasoning">{displayValue(decision.reason)}</Item>
          <div className="grid gap-3 sm:grid-cols-2">
            <Item label="Synthesis confidence">{displayValue(decision.confidence)}</Item>
            <Item label="Dominant public title pattern">
              {displayValue(decision.dominant_competitor_pattern)}
            </Item>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Repeated title patterns</p>
              {patterns.length ? (
                patterns.map((row, index) => (
                  <Item key={index} label={displayValue(row.pattern)}>
                    Observed in {displayValue(row.count, "an unavailable number of")} returned
                    public result titles.
                  </Item>
                ))
              ) : (
                <UnavailableNote>No repeated title pattern was returned.</UnavailableNote>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Small-channel outliers</p>
              {winners.length ? (
                winners.map((row, index) => (
                  <Item key={index} label={displayValue(row.title)}>
                    {displayValue(row.channel)} · {formatNumber(row.views)} views reported by YouTube
                  </Item>
                ))
              ) : (
                <UnavailableNote>No small-channel outlier observation was returned.</UnavailableNote>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Avoid</p>
              {avoid.length ? (
                avoid.map((row, index) => (
                  <Item key={index} label="Avoid">
                    {displayValue(row)}
                  </Item>
                ))
              ) : (
                <UnavailableNote>No avoidance guidance was returned.</UnavailableNote>
              )}
            </div>
          </div>
        </div>
      </Panel>

      <Panel
        icon={Youtube}
        title="Public YouTube observations"
        aside={
          <>
            <EvidenceChip tone="info">Public observation</EvidenceChip>
            {/* The views are YouTube's; the outlier score is this tool's own arithmetic on them. */}
            <EvidenceChip tone="warn">Outlier score: local heuristic</EvidenceChip>
          </>
        }
      >
        {results.length ? (
          <>
            <ul className="divide-y divide-border">
              {results.slice(0, 8).map((row, index) => (
                <li key={row.video_id ?? index} className="flex items-center gap-3.5 py-3 first:pt-0">
                  <VideoThumb videoId={row.video_id} className="w-28 sm:w-32" />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-foreground">
                      {displayValue(row.title)}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {displayValue(row.channel_title)} · {publishedLabel(row.published_at)}
                    </p>
                  </div>
                  <div className="hidden shrink-0 gap-5 text-right sm:flex">
                    <div>
                      <p className="numeric text-[0.8125rem] font-semibold text-foreground">
                        {formatNumber(row.view_count)}
                      </p>
                      <p className="text-[0.6875rem] text-muted-foreground">
                        {row.captured_at ? `Views on ${shortDate(row.captured_at)}` : "Views"}
                      </p>
                    </div>
                    <div>
                      <p className="numeric text-[0.8125rem] font-semibold text-foreground">
                        {displayValue(row.outlier_score)}
                      </p>
                      <p className="text-[0.6875rem] text-muted-foreground">Outlier (heuristic)</p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              These are public observations returned by YouTube research; a result YouTube returned
              without enough statistics to score is listed last as Unavailable. They do not prove
              causation, ranking, or future performance.
            </p>
          </>
        ) : (
          <UnavailableNote>No public YouTube results were returned for this analysis.</UnavailableNote>
        )}
      </Panel>

      <Panel
        icon={Search}
        title="Executed research queries"
        aside={<EvidenceChip tone="info">Research context</EvidenceChip>}
      >
        {queries.length ? (
          <ul className="flex flex-wrap gap-2">
            {queries.map((row, index) => (
              <li
                key={index}
                className="inline-flex max-w-full items-center gap-2 rounded-xl border border-border bg-elevated px-3 py-2 text-[0.8125rem]"
              >
                <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[0.65625rem] font-medium uppercase tracking-wide text-muted-foreground">
                  {displayValue(row.type)}
                </span>
                <span className="min-w-0 break-words text-foreground">{displayValue(row.query)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <UnavailableNote>No research queries were returned.</UnavailableNote>
        )}
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          icon={Sigma}
          title="Local scoring candidates"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          <div className="space-y-2.5">
            {opportunities.length ? (
              opportunities.slice(0, 3).map((row, index) => (
                <Item key={index} label={displayValue(row.title)}>
                  Score {displayValue(row.outlier_score)} ·{" "}
                  {displayValue(
                    asArray<string>(row.opportunity_reasons).join("; "),
                    "No reason returned",
                  )}
                </Item>
              ))
            ) : (
              <UnavailableNote>No local scoring candidates were returned.</UnavailableNote>
            )}
          </div>
        </Panel>

        <Panel
          icon={Tags}
          title="Keyword signals"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          {keywords.length ? (
            <ul className="flex flex-wrap gap-2">
              {keywords.slice(0, 10).map((row, index) => (
                <li
                  key={index}
                  className="rounded-xl border border-border bg-elevated px-3 py-2"
                  title={`Mentions: ${displayValue(row.mentions)} · Strength: ${displayValue(row.strength)}`}
                >
                  <p className="text-[0.8125rem] font-medium text-foreground">{displayValue(row.keyword)}</p>
                  <p className="text-[0.6875rem] text-muted-foreground">
                    Mentions: {displayValue(row.mentions)} · Strength: {displayValue(row.strength)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>Unavailable: research found no keyword signals for this script.</UnavailableNote>
          )}
        </Panel>

        <Panel
          icon={Hash}
          title="Entity signals"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          {entities.length ? (
            <ul className="flex flex-wrap gap-2">
              {entities.slice(0, 10).map((row, index) => (
                <li key={index} className="rounded-xl border border-border bg-elevated px-3 py-2">
                  <p className="text-[0.8125rem] font-medium text-foreground">{displayValue(row.entity)}</p>
                  <p className="text-[0.6875rem] text-muted-foreground">
                    Type: {displayValue(row.type)} · Mentions: {displayValue(row.mentions)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>No entity signals were returned.</UnavailableNote>
          )}
        </Panel>

        <Panel
          icon={ImageIcon}
          title="Thumbnail research context"
          aside={<EvidenceChip tone="info">Public metadata</EvidenceChip>}
        >
          {Object.keys(thumbnails).length ? (
            <div className="space-y-2.5">
              <Item label="Available thumbnail metadata">
                Max: {displayValue(counts.maxres)} · High: {displayValue(counts.high)} · Medium:{" "}
                {displayValue(counts.medium)} · Default: {displayValue(counts.default)}
              </Item>
              <Item label="Low-resolution observations">
                {displayValue(thumbnails.low_resolution_count)}
              </Item>
              <Item label="Local setup suggestion">{displayValue(thumbnails.recommendation)}</Item>
            </div>
          ) : (
            <UnavailableNote>No thumbnail metadata was returned.</UnavailableNote>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          icon={Cpu}
          title="Generation context"
          aside={<EvidenceChip tone={generationTone}>{generationSource}</EvidenceChip>}
        >
          <div className="space-y-2.5">
            <Item label="Intent">{displayValue(data.intent)}</Item>
            <Item label="Content angle">{displayValue(data.content_angle)}</Item>
            <Item label="Cache policy">
              {displayValue(data.cache_policy)} — technical context, not evidence quality.
            </Item>
          </div>
        </Panel>

        <Panel
          icon={AlertTriangle}
          iconTone={warnings.length ? "warn" : "ok"}
          title="Research warnings and limits"
          aside={
            // "ok" means creator-supplied; an empty warning list is not a creator fact.
            <EvidenceChip tone={warnings.length ? "warn" : "neutral"}>
              {warnings.length ? "Review required" : "No warnings"}
            </EvidenceChip>
          }
        >
          {warnings.length ? (
            <ul className="space-y-2">
              {warnings.map((warning, index) => (
                <li
                  key={index}
                  className="rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-2.5 text-[0.8125rem] leading-relaxed text-foreground"
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
