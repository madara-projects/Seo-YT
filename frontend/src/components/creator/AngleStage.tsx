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
import { EvidenceChip, SourceLegend, type EvidenceTone } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { EmptyState, UnavailableNote } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { asArray, asObject, displayValue, formatNumber } from "@/lib/utils";
import type { AnalyzeResponse, PackageOption, RetentionAssistant, RetentionRisk } from "@/api/types";
import type { CreatorFormValues } from "@/schemas/creator";

function severityTone(severity?: string): EvidenceTone {
  if (severity === "high") return "bad";
  if (severity === "medium") return "warn";
  return "info";
}

export function AngleStage({
  data,
  submitted,
  selected,
}: {
  data: AnalyzeResponse | null;
  submitted: CreatorFormValues | null;
  selected: PackageOption | null;
}) {
  if (!data) {
    return (
      <EmptyState
        icon={Compass}
        title="No angle yet"
        description="Run Analyze to review the recommended angle and the evidence behind it."
      />
    );
  }

  const decision = asObject(data.research_decision);
  const brief = asObject(data.creator_brief);
  const enteredAngle = Boolean(String(submitted?.unique_angle ?? "").trim());
  const publicCount = asArray(data.youtube_results).length;

  const assistant = asObject(data.retention_assistant) as RetentionAssistant;
  const hasAssistant = Object.keys(assistant).length > 0;
  const opening = asObject(assistant.opening);
  const frame = asObject(assistant.first_frame);
  const pacing = asObject(assistant.pacing);
  const quote = asObject(assistant.quote_presentation);
  const learning = asObject(assistant.retention_learning);
  const alignment = asArray<{ package_id?: string; status?: string; opening_similarity?: string }>(
    assistant.package_alignment,
  ).find((item) => item.package_id === selected?.id);

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
          <div className="space-y-1.5 text-[13px] leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">{displayValue(decision.recommended_angle)}</p>
            <p>{displayValue(decision.reason, "No research reasoning was returned.")}</p>
          </div>
        </Panel>

        <Panel
          icon={UserPen}
          iconTone={enteredAngle ? "ok" : "neutral"}
          title="Creator brief angle"
          aside={
            <EvidenceChip tone={enteredAngle ? "ok" : "warn"}>
              {enteredAngle ? "Creator-entered" : "Inferred"}
            </EvidenceChip>
          }
        >
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {displayValue(brief.unique_angle)}
          </p>
        </Panel>

        <Panel
          icon={Globe}
          iconTone={publicCount ? "info" : "neutral"}
          title="Public context"
          aside={
            <EvidenceChip tone={publicCount ? "info" : "warn"}>
              {publicCount ? "Public observation" : "Unavailable"}
            </EvidenceChip>
          }
        >
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {publicCount
              ? `${formatNumber(publicCount)} public result${publicCount === 1 ? " was" : "s were"} returned for context. This does not prove why a video performed.`
              : "No public result was returned for this run."}
          </p>
        </Panel>
      </div>

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
                    ? "Unavailable"
                    : `${formatNumber(opening.score)} / 100`
                }
                caption={`Clarity: ${displayValue(opening.clarity)} · Specificity: ${displayValue(opening.specificity)}. Not measured retention.`}
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="First frame"
                icon={Eye}
                value={displayValue(frame.readability)}
                caption={`${displayValue(frame.text_word_count)} words · one-read estimate ${displayValue(frame.estimated_single_read_seconds)}s`}
                tone={frame.status === "unavailable" ? "warn" : "ok"}
                toneLabel={frame.status === "unavailable" ? "Unavailable" : "Supplied"}
              />
              <StatCard
                label="Pacing"
                icon={AudioWaveform}
                value={displayValue(pacing.format_assessment)}
                caption={`${displayValue(pacing.word_count)} words · est. speech ${displayValue(pacing.estimated_spoken_seconds)}s · timing ${displayValue(pacing.timing_confidence)}`}
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="Quote presentation"
                icon={MessageSquareQuote}
                value={
                  quote.status === "available"
                    ? `${displayValue(quote.word_count)} words`
                    : "Unavailable"
                }
                caption={
                  quote.status === "available"
                    ? `Exact text preserved: ${displayValue(quote.exact_text_preserved_on_screen)} · attribution ${displayValue(quote.attribution)}`
                    : displayValue(quote.reason)
                }
                tone={quote.status === "available" ? "ok" : "warn"}
                toneLabel={quote.status === "available" ? "Supplied" : "Unavailable"}
              />
              <StatCard
                label="Selected package alignment"
                icon={ScanText}
                value={selected ? selected.label : "No selection"}
                caption={`Status: ${displayValue(alignment?.status)} · similarity ${displayValue(alignment?.opening_similarity)}. Text alignment, not viewer behaviour.`}
                tone="warn"
                toneLabel="Heuristic"
              />
              <StatCard
                label="Post-publish learning"
                icon={TrendingUp}
                value={displayValue(learning.status)}
                caption={`${displayValue(learning.message, "")} Sample ${formatNumber(learning.sample_size ?? 0)} of ${formatNumber(learning.minimum_samples ?? 0)}.`}
                tone={learning.learning_allowed ? "info" : "warn"}
                toneLabel={learning.learning_allowed ? "Post-publish" : "Unavailable"}
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
                        className="absolute -left-[26px] top-4 size-2.5 rounded-full border-2 border-card bg-brand-gradient"
                        aria-hidden="true"
                      />
                      <Inset>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[13px] font-medium text-foreground">
                            {displayValue(risk.stage)} · {displayValue(risk.risk_code)}
                          </p>
                          <EvidenceChip tone={severityTone(risk.severity)}>
                            {String(risk.severity ?? "review").toUpperCase()}
                          </EvidenceChip>
                        </div>
                        <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
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
                      <p className="text-[13px] font-medium text-foreground">
                        {displayValue(row.recommendation)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Priority: {displayValue(row.priority)} · Heuristic · no performance guarantee
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
                      <p className="text-[13px] font-medium text-foreground">
                        {displayValue(row.alternative_code)}
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
