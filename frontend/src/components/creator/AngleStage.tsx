import {
  AudioWaveform,
  Compass,
  Eye,
  Globe,
  HeartPulse,
  Lightbulb,
  ListTodo,
  MessageSquareQuote,
  Route,
  ScanText,
  TrendingUp,
  UserPen,
  Wand2,
} from "lucide-react";
import { EvidenceChip, provenanceLabel, SourceLegend, type EvidenceTone } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { EmptyState, UnavailableNote } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { humanize } from "@/lib/labels";
import { toFiniteNumber } from "@/lib/format";
import { asArray, asObject, displayValue, formatNumber, UNAVAILABLE } from "@/lib/utils";
import { PacingPanel } from "./PacingPanel";
import type { AnalyzeResponse, PackageOption, RetentionAssistant, RetentionRisk } from "@/api/types";

function severityTone(severity?: string): EvidenceTone {
  if (severity === "high") return "bad";
  if (severity === "medium") return "warn";
  return "info";
}

/** The backend's stored words ("high_burden", "relative_stage_only") as a person would say them. */
function words(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const text = String(value ?? "").trim();
  return text ? humanize(text) : UNAVAILABLE;
}

/** "12 words"; null when nothing was counted, so no unit is ever put on "Unavailable". */
function wordCount(value: unknown): string | null {
  const count = toFiniteNumber(value);
  return count === null ? null : `${formatNumber(count)} ${count === 1 ? "word" : "words"}`;
}

/** "4.5s"; null when there is no estimate. */
function secondsText(value: unknown): string | null {
  const seconds = toFiniteNumber(value);
  return seconds === null ? null : `${seconds.toLocaleString(undefined, { maximumFractionDigits: 1 })}s`;
}

/** The parts that were measured, joined; the fallback when none were. */
function caption(parts: (string | null)[], fallback: string): string {
  const known = parts.filter((part): part is string => Boolean(part));
  return known.length ? known.join(" · ") : fallback;
}

/** "Supplied" only when the brief says the creator supplied it; otherwise its real source. */
function suppliedChip(status: unknown, provenance: unknown): { tone: EvidenceTone; label: string } {
  if (status !== "available") return { tone: "neutral", label: "Unavailable" };
  const source = provenanceLabel(provenance);
  return source.tone === "ok" ? { tone: "ok", label: "Supplied" } : source;
}

export function AngleStage({
  data,
  selected,
}: {
  data: AnalyzeResponse | null;
  /** The creator's explicit choice, or null before one is made. */
  selected: PackageOption | null;
}) {
  if (!data) {
    return (
      <EmptyState
        icon={Compass}
        title="No angle yet"
        description="Generate a package to review the recommended angle and the evidence behind it."
      />
    );
  }

  const decision = asObject(data.research_decision);
  const brief = asObject(data.creator_brief);
  // The backend records where every brief field came from; it never infers the unique angle.
  const angleSource = provenanceLabel(asObject(asObject(brief.field_provenance).unique_angle).source);
  const publicCount = asArray(data.youtube_results).length;

  const assistant = asObject(data.retention_assistant) as RetentionAssistant;
  const hasAssistant = Object.keys(assistant).length > 0;
  const opening = asObject(assistant.opening);
  const frame = asObject(assistant.first_frame);
  const pacing = asObject(assistant.pacing);
  const quote = asObject(assistant.quote_presentation);
  const learning = asObject(assistant.retention_learning);
  const frameChip = suppliedChip(frame.status, frame.provenance);
  const quoteChip = suppliedChip(quote.status, quote.provenance);
  const alignment = asArray<{ package_id?: string; status?: string; opening_similarity?: string }>(
    assistant.package_alignment,
  ).find((item) => selected?.packageId && item.package_id === selected.packageId);

  const risks = asArray<{ risks?: RetentionRisk[] }>(assistant.risk_map).flatMap((stage) =>
    asArray<RetentionRisk>(stage.risks),
  );
  const recommendations = asArray<{ recommendation?: string; priority?: string }>(
    assistant.recommendations,
  );
  const alternatives = asArray<{
    alternative_code?: string;
    structure?: string;
    preserves_source?: string;
  }>(assistant.alternatives);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <Panel
          icon={Compass}
          title="Engine content angle"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          <p className="font-display text-lg font-semibold leading-snug text-foreground">
            {displayValue(data.content_angle)}
          </p>
        </Panel>

        <Panel
          icon={Lightbulb}
          title="Research synthesis"
          aside={<EvidenceChip tone="warn">Local heuristic</EvidenceChip>}
        >
          <div className="space-y-1.5 text-[0.8125rem] leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">{displayValue(decision.recommended_angle)}</p>
            <p>{displayValue(decision.reason, "No research reasoning was returned.")}</p>
          </div>
        </Panel>

        <Panel
          icon={UserPen}
          iconTone={angleSource.tone === "ok" ? "ok" : "neutral"}
          title="Creator brief angle"
          aside={<EvidenceChip tone={angleSource.tone}>{angleSource.label}</EvidenceChip>}
        >
          <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
            {displayValue(brief.unique_angle)}
          </p>
        </Panel>

        <Panel
          icon={Globe}
          iconTone={publicCount ? "info" : "neutral"}
          title="Public context"
          aside={
            <EvidenceChip tone={publicCount ? "info" : "neutral"}>
              {publicCount ? "Public observation" : "Unavailable"}
            </EvidenceChip>
          }
        >
          <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
            {publicCount
              ? `${formatNumber(publicCount)} public result${publicCount === 1 ? " was" : "s were"} returned for context. This does not prove why a video performed.`
              : "No public result was returned for this run."}
          </p>
        </Panel>
      </div>

      <PacingPanel pacing={data.pacing_analysis} />

      <Panel
        icon={HeartPulse}
        title="Hook, pacing and retention assistant"
        description={
          <>
            {displayValue(assistant.disclaimer, "Heuristic analysis of the supplied text.")}{" "}
            {assistant.rule_version ? `Rules: ${assistant.rule_version}.` : ""}
          </>
        }
        aside={
          <EvidenceChip tone={severityTone(String(assistant.risk_level))}>
            Risk: {String(assistant.risk_level ?? "unknown").toUpperCase()}
          </EvidenceChip>
        }
      >
        {!hasAssistant ? (
          <UnavailableNote>No retention analysis was returned for this run.</UnavailableNote>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <StatCard
                label="Opening"
                icon={Wand2}
                value={
                  opening.score === null || opening.score === undefined
                    ? UNAVAILABLE
                    : `${formatNumber(opening.score)} / 100`
                }
                caption={`Clarity: ${words(opening.clarity)} · Specificity: ${words(opening.specificity)}. Not measured retention.`}
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="First frame"
                icon={Eye}
                value={frame.status === "available" ? words(frame.readability) : UNAVAILABLE}
                caption={
                  frame.status === "available"
                    ? caption(
                        [
                          wordCount(frame.text_word_count),
                          secondsText(frame.estimated_single_read_seconds)
                            ? `one-read estimate ${secondsText(frame.estimated_single_read_seconds)}`
                            : null,
                        ],
                        "No on-screen text was counted.",
                      )
                    : // Why it wasn't analysed, in the backend's words (a plain script has no first frame).
                      displayValue(frame.reason, "No first-frame analysis was returned for this run.")
                }
                tone={frameChip.tone}
                toneLabel={frameChip.label}
              />
              <StatCard
                label="Pacing"
                icon={AudioWaveform}
                value={words(pacing.format_assessment)}
                caption={caption(
                  [
                    wordCount(pacing.word_count),
                    secondsText(pacing.estimated_spoken_seconds)
                      ? `est. speech ${secondsText(pacing.estimated_spoken_seconds)}`
                      : null,
                    pacing.timing_confidence ? `timing ${words(pacing.timing_confidence).toLowerCase()}` : null,
                  ],
                  "No pacing figures were returned for this run.",
                )}
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="Quote presentation"
                icon={MessageSquareQuote}
                value={
                  quote.status === "available"
                    ? `${displayValue(quote.word_count)} words`
                    : UNAVAILABLE
                }
                caption={
                  quote.status === "available"
                    ? `Exact text preserved on screen: ${words(quote.exact_text_preserved_on_screen)} · attribution ${words(quote.attribution).toLowerCase()}`
                    : displayValue(quote.reason)
                }
                tone={quoteChip.tone}
                toneLabel={quoteChip.label}
              />
              <StatCard
                label="Selected package alignment"
                icon={ScanText}
                value={selected ? selected.label : "No selection"}
                caption={
                  selected
                    ? `Status: ${words(alignment?.status)} · similarity ${words(alignment?.opening_similarity).toLowerCase()}. Text alignment, not viewer behaviour.`
                    : "Choose a package to see how its opening lines up with the script."
                }
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="Post-publish learning"
                icon={TrendingUp}
                value={words(learning.status)}
                caption={`${displayValue(learning.message, "")} Sample ${formatNumber(learning.sample_size)} of ${formatNumber(learning.minimum_samples)}.`}
                tone={learning.learning_allowed ? "info" : "neutral"}
                toneLabel={learning.learning_allowed ? "Post-publish" : "Not enough evidence"}
              />
            </div>

            <section className="space-y-2.5">
              <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                <Route className="size-3.5" aria-hidden="true" />
                Retention-risk map
              </h3>
              {risks.length ? (
                <ol className="relative space-y-2.5 border-l border-dashed border-border pl-5">
                  {risks.map((risk, index) => (
                    <li key={index} className="relative">
                      <span
                        className="absolute -left-6.5 top-4 size-2.5 rounded-full border-2 border-card bg-brand-gradient"
                        aria-hidden="true"
                      />
                      <Inset>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[0.8125rem] font-medium text-foreground">
                            {words(risk.stage)} · {words(risk.risk_code)}
                          </p>
                          <EvidenceChip tone={severityTone(risk.severity)}>
                            {String(risk.severity ?? "review").toUpperCase()}
                          </EvidenceChip>
                        </div>
                        <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted-foreground">
                          {displayValue(risk.explanation)}
                        </p>
                        <dl className="mt-2 grid gap-1 text-xs leading-relaxed text-muted-foreground">
                          <div>
                            <dt className="inline font-semibold text-foreground">Evidence: </dt>
                            <dd className="inline">{displayValue(risk.evidence)}</dd>
                          </div>
                          <div>
                            <dt className="inline font-semibold text-foreground">Change: </dt>
                            <dd className="inline">{displayValue(risk.recommendation)}</dd>
                          </div>
                        </dl>
                      </Inset>
                    </li>
                  ))}
                </ol>
              ) : (
                <UnavailableNote>
                  No specific deterministic risk was identified. This is not measured retention
                  evidence.
                </UnavailableNote>
              )}
            </section>

            <div className="grid gap-5 md:grid-cols-2">
              <section className="space-y-2.5">
                <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  <ListTodo className="size-3.5" aria-hidden="true" />
                  What to change
                </h3>
                {recommendations.length ? (
                  recommendations.map((row, index) => (
                    <Inset key={index}>
                      <p className="text-[0.8125rem] font-medium text-foreground">
                        {displayValue(row.recommendation)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Priority: {words(row.priority)} · Heuristic · no performance guarantee
                      </p>
                    </Inset>
                  ))
                ) : (
                  <UnavailableNote>No additional recommendation returned.</UnavailableNote>
                )}
              </section>

              <section className="space-y-2.5">
                <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  <Wand2 className="size-3.5" aria-hidden="true" />
                  Practical alternatives
                </h3>
                {alternatives.length ? (
                  alternatives.map((row, index) => (
                    <Inset key={index}>
                      <p className="text-[0.8125rem] font-medium text-foreground">
                        {words(row.alternative_code)}
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {displayValue(row.structure)}
                        <br />
                        Preserves: {displayValue(row.preserves_source)}
                      </p>
                    </Inset>
                  ))
                ) : (
                  <UnavailableNote>
                    No alternative is forced when the source supports only one structure.
                  </UnavailableNote>
                )}
              </section>
            </div>
          </div>
        )}
      </Panel>

      <SourceLegend />
    </div>
  );
}
