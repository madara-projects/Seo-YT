import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceChip, SourceLegend, type EvidenceTone } from "@/components/common/EvidenceChip";
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

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Engine content angle</CardTitle>
            <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
          </CardHeader>
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            {displayValue(data.content_angle)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Research synthesis</CardTitle>
            <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p className="text-foreground">{displayValue(decision.recommended_angle)}</p>
            <p>{displayValue(decision.reason, "No research reasoning was returned.")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Creator brief angle</CardTitle>
            <EvidenceChip tone={enteredAngle ? "ok" : "warn"}>
              {enteredAngle ? "Creator-entered" : "Inferred"}
            </EvidenceChip>
          </CardHeader>
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            {displayValue(brief.unique_angle)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Public context</CardTitle>
            <EvidenceChip tone={publicCount ? "info" : "warn"}>
              {publicCount ? "Public observation" : "Unavailable"}
            </EvidenceChip>
          </CardHeader>
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            {publicCount
              ? `${formatNumber(publicCount)} public result${publicCount === 1 ? " was" : "s were"} returned for context. This does not prove why a video performed.`
              : "No public result was returned for this run."}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
          <div className="space-y-1">
            <CardTitle>Hook, pacing and retention assistant</CardTitle>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {displayValue(assistant.disclaimer, "Heuristic analysis of the supplied text.")}{" "}
              {assistant.rule_version ? `Rules: ${assistant.rule_version}.` : ""}
            </p>
          </div>
          <EvidenceChip tone={severityTone(String(assistant.risk_level))}>
            Risk: {String(assistant.risk_level ?? "unknown").toUpperCase()}
          </EvidenceChip>
        </CardHeader>

        <CardContent className="space-y-4">
          {!hasAssistant ? (
            <UnavailableNote>
              No retention analysis was returned for this run.
            </UnavailableNote>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <StatCard
                  label="Opening"
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
                  value={displayValue(frame.readability)}
                  caption={`${displayValue(frame.text_word_count)} words · one-read estimate ${displayValue(frame.estimated_single_read_seconds)}s`}
                  tone={frame.status === "unavailable" ? "warn" : "ok"}
                  toneLabel={frame.status === "unavailable" ? "Unavailable" : "Supplied"}
                />
                <StatCard
                  label="Pacing"
                  value={displayValue(pacing.format_assessment)}
                  caption={`${displayValue(pacing.word_count)} words · est. speech ${displayValue(pacing.estimated_spoken_seconds)}s · timing ${displayValue(pacing.timing_confidence)}`}
                  tone="warn"
                  toneLabel="Heuristic"
                />
                <StatCard
                  label="Quote presentation"
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
                  value={selected ? selected.label : "No selection"}
                  caption={`Status: ${displayValue(alignment?.status)} · similarity ${displayValue(alignment?.opening_similarity)}. Text alignment, not viewer behaviour.`}
                  tone="warn"
                  toneLabel="Heuristic"
                />
                <StatCard
                  label="Post-publish learning"
                  value={displayValue(learning.status)}
                  caption={`${displayValue(learning.message, "")} Sample ${formatNumber(learning.sample_size ?? 0)} of ${formatNumber(learning.minimum_samples ?? 0)}.`}
                  tone={learning.learning_allowed ? "info" : "warn"}
                  toneLabel={learning.learning_allowed ? "Post-publish" : "Unavailable"}
                />
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Retention-risk map
                </h3>
                {risks.length ? (
                  <div className="space-y-2">
                    {risks.map((risk, index) => (
                      <div key={index} className="rounded-md border border-border bg-muted/30 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-foreground">
                            {displayValue(risk.stage)} · {displayValue(risk.risk_code)}
                          </p>
                          <EvidenceChip tone={severityTone(risk.severity)}>
                            {String(risk.severity ?? "review").toUpperCase()}
                          </EvidenceChip>
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                          {displayValue(risk.explanation)}
                        </p>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                          <strong className="text-foreground">Evidence:</strong>{" "}
                          {displayValue(risk.evidence)}
                          <br />
                          <strong className="text-foreground">Change:</strong>{" "}
                          {displayValue(risk.recommendation)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <UnavailableNote>
                    No specific deterministic risk was identified. This is not measured retention
                    evidence.
                  </UnavailableNote>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    What to change
                  </h3>
                  {asArray<{ recommendation?: string; priority?: string }>(assistant.recommendations)
                    .length ? (
                    asArray<{ recommendation?: string; priority?: string }>(
                      assistant.recommendations,
                    ).map((row, index) => (
                      <div key={index} className="rounded-md border border-border bg-muted/30 p-3">
                        <p className="text-xs font-semibold text-foreground">
                          {displayValue(row.recommendation)}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          Priority: {displayValue(row.priority)} · Heuristic · no performance
                          guarantee
                        </p>
                      </div>
                    ))
                  ) : (
                    <UnavailableNote>No additional recommendation returned.</UnavailableNote>
                  )}
                </div>

                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Practical alternatives
                  </h3>
                  {asArray<{ alternative_code?: string; structure?: string; preserves_source?: string }>(
                    assistant.alternatives,
                  ).length ? (
                    asArray<{
                      alternative_code?: string;
                      structure?: string;
                      preserves_source?: string;
                    }>(assistant.alternatives).map((row, index) => (
                      <div key={index} className="rounded-md border border-border bg-muted/30 p-3">
                        <p className="text-xs font-semibold text-foreground">
                          {displayValue(row.alternative_code)}
                        </p>
                        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                          {displayValue(row.structure)}
                          <br />
                          Preserves: {displayValue(row.preserves_source)}
                        </p>
                      </div>
                    ))
                  ) : (
                    <UnavailableNote>
                      No alternative is forced when the source supports only one structure.
                    </UnavailableNote>
                  )}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <SourceLegend />
    </div>
  );
}
