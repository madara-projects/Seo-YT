import { useState } from "react";
import { FlaskConical, Link2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { CardSkeleton, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, formatApiError } from "@/api/client";
import { useCreateStudioTest, useStudioTests, useUpdateStudioTest } from "@/hooks/useLearning";
import { chosenSimilarPairs, studioResultText, studioStatusLabel } from "@/lib/learningFormat";
import { historyDate } from "@/lib/historyFormat";
import { asArray, cn } from "@/lib/utils";
import type { SimilarPair, StudioCandidate, StudioOutcome, StudioTest, StudioTestOverview } from "@/api/learningTypes";

const LABELS = ["A", "B", "C"];

function SimilarWarning({ pairs, names }: { pairs: SimilarPair[]; names: (id: string) => string }) {
  if (!pairs.length) return null;
  return (
    <div
      role="status"
      className="flex gap-2 rounded-xl border border-tone-warn-border bg-tone-warn-bg p-3 text-xs leading-relaxed text-foreground"
    >
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-tone-warn" aria-hidden="true" />
      <div className="space-y-0.5">
        {pairs.map((pair) => (
          <p key={`${pair.first}-${pair.second}`}>
            {names(pair.first)} and {names(pair.second)} have titles too similar to tell apart in a test (
            {Math.round(pair.similarity * 100)}% alike). Consider a clearly different angle.
          </p>
        ))}
      </div>
    </div>
  );
}

/** A variant's title and thumbnail text, each with its own copy button for pasting into Studio. */
function VariantCopy({ label, title, thumbnailText }: { label: string; title: string; thumbnailText: string }) {
  const suffix = label ? ` ${label}` : "";
  return (
    <div className="min-w-0 flex-1 space-y-1.5">
      <p className="text-[0.8125rem] font-medium leading-snug text-foreground">{title}</p>
      <p className="text-xs text-muted-foreground">
        Thumbnail text: {thumbnailText || "none saved"}
      </p>
      <div className="flex flex-wrap gap-1.5">
        <CopyButton value={title} label={`Copy title${suffix}`} size="xs" />
        {thumbnailText ? <CopyButton value={thumbnailText} label={`Copy thumbnail text${suffix}`} size="xs" /> : null}
      </div>
    </div>
  );
}

function ResultForm({ test, onDone, runId }: { test: StudioTest; onDone: () => void; runId: number }) {
  const update = useUpdateStudioTest(runId);
  const labels = test.variants.map((variant) => variant.label);
  const [outcome, setOutcome] = useState<StudioOutcome | "">(test.result?.outcome ?? "");
  const [winner, setWinner] = useState(test.winner_variant ?? "");
  const [shares, setShares] = useState<Record<string, string>>(() =>
    Object.fromEntries(labels.map((label) => [label, String(test.result?.watch_time_share?.[label] ?? "")])),
  );
  const [notes, setNotes] = useState(test.notes);

  const submit = async () => {
    const watchTimeShare = Object.fromEntries(
      Object.entries(shares)
        .filter(([, value]) => value.trim() !== "")
        .map(([label, value]) => [label, Number(value)]),
    );
    try {
      await update.mutateAsync({
        testId: test.id,
        changes: {
          outcome: outcome || undefined,
          ...(outcome === "winner" ? { winner_variant: winner } : {}),
          watch_time_share: watchTimeShare,
          notes,
        },
      });
      toast.success("Studio result recorded.");
      onDone();
    } catch (error) {
      toast.error(formatApiError(error, "The result could not be recorded."));
    }
  };

  return (
    <form
      className="space-y-3 rounded-xl border border-border bg-elevated p-3.5"
      aria-label={`Record the Studio result of test ${test.id}`}
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <fieldset className="space-y-1.5">
        <legend className="text-xs font-medium text-foreground">What Studio shows</legend>
        <div className="flex flex-wrap gap-3 text-[0.8125rem]">
          {(
            [
              ["winner", "A winner"],
              ["no_clear_winner", "No clear winner"],
            ] as const
          ).map(([value, text]) => (
            <label key={value} className="inline-flex items-center gap-1.5">
              <input
                type="radio"
                name={`outcome-${test.id}`}
                value={value}
                checked={outcome === value}
                onChange={() => setOutcome(value)}
              />
              {text}
            </label>
          ))}
        </div>
      </fieldset>
      {outcome === "winner" ? (
        <fieldset className="space-y-1.5">
          <legend className="text-xs font-medium text-foreground">Winning variant</legend>
          <div className="flex flex-wrap gap-3 text-[0.8125rem]">
            {labels.map((label) => (
              <label key={label} className="inline-flex items-center gap-1.5">
                <input
                  type="radio"
                  name={`winner-${test.id}`}
                  value={label}
                  checked={winner === label}
                  onChange={() => setWinner(label)}
                />
                Variant {label}
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}
      <fieldset className="space-y-1.5">
        <legend className="text-xs font-medium text-foreground">Watch-time share, as Studio shows it (optional)</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {labels.map((label) => (
            <div key={label} className="space-y-1">
              <Label htmlFor={`share-${test.id}-${label}`} className="text-xs">
                Variant {label} (%)
              </Label>
              <Input
                id={`share-${test.id}-${label}`}
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step={0.1}
                value={shares[label] ?? ""}
                onChange={(event) => setShares((prior) => ({ ...prior, [label]: event.target.value }))}
                className="h-9"
              />
            </div>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor={`notes-${test.id}`} className="text-xs">
          Notes
        </Label>
        <Textarea
          id={`notes-${test.id}`}
          value={notes}
          maxLength={2000}
          onChange={(event) => setNotes(event.target.value)}
          className="min-h-16"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={!outcome || (outcome === "winner" && !winner) || update.isPending}>
          {update.isPending ? "Saving…" : "Save result"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function TestCard({ test, overview, runId }: { test: StudioTest; overview: StudioTestOverview; runId: number }) {
  const update = useUpdateStudioTest(runId);
  const [recording, setRecording] = useState(false);
  const result = studioResultText(test);
  const linked = Boolean(test.linked_video);
  // A result read in Studio belongs to the video it was read for, never to one linked later.
  const orphaned = Boolean(test.result) && !linked;
  const canLink = Boolean(overview.linked_video) && !linked && !orphaned;

  const link = async () => {
    try {
      await update.mutateAsync({ testId: test.id, changes: { link_video: true } });
      toast.success("Test linked to the published video.");
    } catch (error) {
      toast.error(formatApiError(error, "The test could not be linked."));
    }
  };

  return (
    <li className="space-y-3 rounded-xl border border-border bg-card p-3.5" data-testid="studio-test">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Test #{test.id}
          {test.created_at ? ` · prepared ${historyDate(test.created_at)}` : ""}
          {test.linked_video ? ` · video ${test.linked_video.youtube_video_id}` : ""}
        </p>
        <EvidenceChip tone={test.status === "completed" ? "ok" : "neutral"}>{studioStatusLabel(test)}</EvidenceChip>
      </div>
      <ul className="space-y-2">
        {test.variants.map((variant) => (
          <li key={variant.label} className="flex gap-3">
            <span
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-md text-xs font-semibold",
                test.winner_variant === variant.label ? "bg-tone-ok-bg text-tone-ok" : "bg-muted text-foreground",
              )}
              aria-label={`Variant ${variant.label}`}
            >
              {variant.label}
            </span>
            <VariantCopy label={variant.label} title={variant.title} thumbnailText={variant.thumbnail_text} />
          </li>
        ))}
      </ul>
      <SimilarWarning pairs={asArray<SimilarPair>(test.similar_pairs)} names={(label) => `Variant ${label}`} />
      {result ? <p className="text-[0.8125rem] font-medium text-foreground">{result}</p> : null}
      {test.notes && !recording ? <p className="text-xs text-muted-foreground">Notes: {test.notes}</p> : null}
      {recording ? (
        <ResultForm test={test} runId={runId} onDone={() => setRecording(false)} />
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {!linked && !orphaned ? (
            <Button size="sm" variant="outline" onClick={() => void link()} disabled={!canLink || update.isPending}>
              <Link2 aria-hidden="true" />
              Link to published video
            </Button>
          ) : null}
          {linked ? (
            <Button size="sm" variant="outline" onClick={() => setRecording(true)}>
              {test.result ? "Correct the Studio result" : "Record Studio result"}
            </Button>
          ) : null}
          {orphaned ? (
            <span className="text-xs text-muted-foreground">
              This result was read for a video that is no longer linked to this package. Prepare a new test for the new video.
            </span>
          ) : null}
          {!linked && !orphaned && !overview.linked_video ? (
            <span className="text-xs text-muted-foreground">
              After publishing, link the video to this package in History, then link this test to it.
            </span>
          ) : null}
        </div>
      )}
    </li>
  );
}

function Prepare({ overview, runId }: { overview: StudioTestOverview; runId: number }) {
  const create = useCreateStudioTest(runId);
  const [chosen, setChosen] = useState<string[]>([]);
  const candidates = asArray<StudioCandidate>(overview.candidates);
  const max = overview.max_variants || 3;
  const min = overview.min_variants || 2;
  const warnings = chosenSimilarPairs(asArray<SimilarPair>(overview.similar_pairs), chosen);
  const labelOf = (packageId: string) => {
    const index = chosen.indexOf(packageId);
    return index >= 0 ? LABELS[index] : null;
  };

  const toggle = (packageId: string, checked: boolean) =>
    setChosen((prior) => (checked ? [...prior, packageId].slice(0, max) : prior.filter((id) => id !== packageId)));

  const save = async () => {
    try {
      await create.mutateAsync({ packageIds: chosen });
      setChosen([]);
      toast.success("Test prepared. Set it up in YouTube Studio after publishing.");
    } catch (error) {
      toast.error(formatApiError(error, "The test could not be saved."));
    }
  };

  if (!candidates.length) {
    return <UnavailableNote>This saved package has no title/thumbnail packages to test.</UnavailableNote>;
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Choose {min === max ? max : `${min} to ${max}`} packages. {chosen.length} of {max} chosen.
      </p>
      <ul className="space-y-2">
        {candidates.map((candidate) => {
          const label = labelOf(candidate.package_id);
          const id = `studio-${runId}-${candidate.package_id}`;
          return (
            <li
              key={candidate.package_id}
              className={cn(
                "flex gap-3 rounded-xl border bg-card p-3",
                label ? "border-brand-border" : "border-border",
              )}
            >
              <Checkbox
                id={id}
                checked={Boolean(label)}
                disabled={!label && chosen.length >= max}
                onCheckedChange={(value) => toggle(candidate.package_id, value === true)}
                aria-label={`Use "${candidate.title}" as a variant`}
                className="mt-0.5"
              />
              <div className="min-w-0 flex-1 space-y-1">
                <label htmlFor={id} className="block text-xs font-medium text-muted-foreground">
                  {label ? `Variant ${label}` : "Not chosen"}
                </label>
                <VariantCopy label={label ?? ""} title={candidate.title} thumbnailText={candidate.thumbnail_text} />
              </div>
            </li>
          );
        })}
      </ul>
      <SimilarWarning
        pairs={warnings}
        names={(packageId) => `Variant ${labelOf(packageId) ?? "?"}`}
      />
      <Button onClick={() => void save()} disabled={chosen.length < min || chosen.length > max || create.isPending}>
        <FlaskConical aria-hidden="true" />
        {create.isPending ? "Saving…" : "Save as a prepared test"}
      </Button>
    </div>
  );
}

/**
 * Preparing YouTube Studio's own title/thumbnail test (Test & Compare) for a
 * long video, and recording what Studio reported. Record-only: YouTube runs
 * the test, and nothing here changes a video.
 */
export function StudioTestPanel({ runId, className }: { runId: number | null; className?: string }) {
  const query = useStudioTests(runId);
  const overview = query.data;
  const tests = asArray<StudioTest>(overview?.tests);

  return (
    <Panel
      className={className}
      icon={FlaskConical}
      headingLevel={3}
      title="YouTube Studio test (Test & Compare)"
      description="Prepare up to three title and thumbnail variants for YouTube's own A/B test on this long video."
      aside={<EvidenceChip tone="neutral">Record only</EvidenceChip>}
      data-testid="studio-test-panel"
    >
      {!runId ? (
        <UnavailableNote>This package was not saved to History, so no test can be prepared for it.</UnavailableNote>
      ) : query.isPending ? (
        <CardSkeleton rows={2} />
      ) : query.isError || !overview ? (
        <UnavailableNote>{apiErrorMessage(query.error, "Studio tests could not be loaded.")}</UnavailableNote>
      ) : overview.eligible === false ? (
        <p className="text-[0.8125rem] text-muted-foreground" data-testid="studio-shorts-note">
          {overview.reason || "YouTube's Test & Compare is not available for Shorts."}
        </p>
      ) : (
        <div className="space-y-4">
          <Prepare overview={overview} runId={runId} />
          {tests.length ? (
            <ul className="space-y-3" aria-label="Prepared tests">
              {tests.map((test) => (
                <TestCard key={test.id} test={test} overview={overview} runId={runId} />
              ))}
            </ul>
          ) : null}
          <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
            {overview.note ||
              "YouTube Studio runs this test and picks by watch-time share. This app never runs it; its own before/after comparisons are not equivalent to YouTube's test."}
          </p>
        </div>
      )}
    </Panel>
  );
}
