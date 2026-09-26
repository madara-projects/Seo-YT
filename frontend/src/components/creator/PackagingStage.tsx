import { useState } from "react";
import {
  CalendarClock,
  Check,
  Clapperboard,
  FileText,
  Hash,
  HeartHandshake,
  Image as ImageIcon,
  Loader2,
  Tag,
  Target,
  Type,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { EmptyState } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { asObject, cn, displayValue } from "@/lib/utils";
import { formatSeconds } from "@/lib/format";
import { opportunityText, titleScoreText } from "@/lib/dashboardFormat";
import { copyValue } from "@/lib/packages";
import { ThumbnailMock } from "./ThumbnailMock";
import type { AnalyzeResponse, PackageOption, SelectionStatus } from "@/api/types";

/** A common guideline, not a YouTube rule: long titles are cut off on phones. */
const TITLE_TRUNCATION_GUIDE = 70;

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (!items.length) return <p className="text-[0.8125rem] text-muted-foreground">{emptyLabel}</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item, index) => (
        <li
          key={`${item}-${index}`}
          className="rounded-lg border border-border bg-elevated px-2.5 py-1 text-xs text-foreground"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function FieldHeader({
  icon: Icon,
  label,
  count,
  action,
}: {
  icon: React.ElementType;
  label: string;
  count?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="text-[0.8125rem] font-medium text-foreground">{label}</span>
        {count ? <Badge variant="neutral" className="numeric">{count}</Badge> : null}
      </div>
      {action}
    </div>
  );
}

/** How the package might look in a search list. A mock, labelled as one. */
function SearchPreview({ option, duration }: { option: PackageOption; duration?: string }) {
  const long = option.title.length > TITLE_TRUNCATION_GUIDE;
  return (
    <div className="space-y-3.5">
      <ThumbnailMock text={option.thumbnailText} duration={duration} />
      <div className="flex gap-3">
        <span className="mt-0.5 size-9 shrink-0 rounded-full bg-brand-gradient opacity-80" aria-hidden="true" />
        <div className="min-w-0">
          <p className="line-clamp-2 text-[0.9375rem] font-semibold leading-snug text-foreground">
            {option.title}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Your channel · no views until you publish
          </p>
        </div>
      </div>
      <p
        className={cn(
          "rounded-xl border px-3 py-2 text-xs leading-relaxed",
          long
            ? "border-tone-warn-border bg-tone-warn-bg text-foreground"
            : "border-border bg-elevated text-muted-foreground",
        )}
      >
        {long
          ? `At ${option.title.length} characters this title may be cut off on phones and in suggested feeds (a common guideline is about ${TITLE_TRUNCATION_GUIDE}).`
          : `${option.title.length} characters — within the common ~${TITLE_TRUNCATION_GUIDE}-character guideline for titles shown in full.`}
      </p>
    </div>
  );
}

const SELECTION_STATE: Record<SelectionStatus, { tone: EvidenceTone; chip: string }> = {
  saved: { tone: "ok", chip: "Saved to History" },
  saving: { tone: "neutral", chip: "Saving…" },
  error: { tone: "bad", chip: "Not saved" },
  unrecorded: { tone: "neutral", chip: "Not chosen yet" },
};

/**
 * Picks which option is on show, and records one as the creator's choice.
 * Previewing never records anything; only "Use this package" does.
 */
function PackageSwitcher({
  options,
  preview,
  chosen,
  selectionStatus,
  onPreview,
  onSelect,
}: {
  options: PackageOption[];
  preview: PackageOption;
  chosen: PackageOption | null;
  selectionStatus: SelectionStatus;
  onPreview: (optionId: string) => void;
  onSelect: (optionId: string) => void;
}) {
  const inUse = chosen?.id === preview.id;
  const recordable = preview.packageId !== null;
  const status = inUse ? SELECTION_STATE[selectionStatus] : SELECTION_STATE.unrecorded;
  const retry = inUse && selectionStatus === "error";

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-3.5 shadow-card sm:flex-row sm:items-center sm:justify-between sm:p-4">
      <fieldset className="min-w-0">
        <legend className="sr-only">Package to preview</legend>
        <div className="flex flex-wrap gap-1.5" data-testid="package-switcher">
          {options.map((option) => {
            const active = option.id === preview.id;
            return (
              <label
                key={option.id}
                className={cn(
                  "cursor-pointer rounded-xl border px-3 py-1.5 text-[0.8125rem] font-medium transition-[border-color,background-color,color] duration-150",
                  "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring",
                  active
                    ? "border-brand-border bg-brand-soft text-foreground"
                    : "border-border bg-elevated text-muted-foreground hover:text-foreground",
                )}
                title={option.title}
              >
                <input
                  type="radio"
                  name="package-preview"
                  value={option.id}
                  checked={active}
                  onChange={() => onPreview(option.id)}
                  className="sr-only"
                  // The pill shows only the letter; the name carries the title as well.
                  aria-label={`${option.label}: ${option.title}${option.packageId === null ? " (title only)" : ""}${option.id === chosen?.id ? " (in use)" : ""}`}
                />
                {option.label.replace("Package ", "")}
                {option.id === chosen?.id ? <Check className="ml-1 inline size-3.5 text-tone-ok" aria-hidden="true" /> : null}
              </label>
            );
          })}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        <EvidenceChip tone={status.tone}>{status.chip}</EvidenceChip>
        <Button
          type="button"
          size="sm"
          variant={inUse && !retry ? "outline" : "default"}
          onClick={() => onSelect(preview.id)}
          disabled={!recordable || (inUse && !retry) || selectionStatus === "saving"}
          aria-describedby={recordable ? undefined : "package-title-only"}
          data-testid="use-package"
        >
          {inUse && selectionStatus === "saving" ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          {inUse && !retry ? <Check aria-hidden="true" /> : null}
          {retry ? "Try saving again" : inUse ? "In use" : `Use package ${preview.label.replace("Package ", "")}`}
        </Button>
      </div>
      {recordable ? null : (
        <p id="package-title-only" className="text-xs text-muted-foreground sm:basis-full">
          A title-only option has no saved package behind it, so it can&apos;t be recorded; copy its title if you use it.
        </p>
      )}
    </div>
  );
}

/**
 * The generated package, ready to copy. The switcher previews each option;
 * only an explicit "Use" records one, so nothing reads as chosen before that.
 */
export function PackagingStage({
  data,
  options,
  chosen,
  selectionStatus,
  onSelect,
  durationSeconds,
}: {
  data: AnalyzeResponse | null;
  options: PackageOption[];
  chosen: PackageOption | null;
  selectionStatus: SelectionStatus;
  onSelect: (optionId: string) => void;
  durationSeconds?: string;
}) {
  const [previewId, setPreviewId] = useState<string | null>(null);

  if (!data) {
    return (
      <EmptyState
        icon={Clapperboard}
        title="No package yet"
        description="Generate a package to see its title, description, tags, hashtags and options."
      />
    );
  }
  const preview = options.find((option) => option.id === previewId) ?? chosen ?? options[0] ?? null;
  if (!preview) {
    return <EmptyState title="The analysis returned no usable package option." />;
  }

  const opportunity = asObject(asObject(data.opportunity_gap_analysis).opportunity_score);
  const opportunityMeasured = typeof opportunity.score === "number";
  const timing = asObject(data.upload_timing);
  const timingZone = String(timing.timezone ?? timing.today_timezone ?? "").trim();
  const timingConfidence = String(timing.confidence ?? "").trim().toLowerCase();
  const duration = durationSeconds ? formatSeconds(durationSeconds, "") : "";

  const recurringWindow =
    timing.recommended_time && timingZone
      ? `${timing.recommended_time} ${timingZone}`
      : "Unavailable until a timezone-explicit recommendation is calculated";
  const todayWindow =
    timing.today_time && (timing.today_timezone || timingZone)
      ? `${timing.today_time} ${timing.today_timezone || timingZone}`
      : "Unavailable";

  return (
    <div className="space-y-5">
      <PackageSwitcher
        options={options}
        preview={preview}
        chosen={chosen}
        selectionStatus={selectionStatus}
        onPreview={setPreviewId}
        onSelect={onSelect}
      />

      {/*
        Left: the package and, under it, its scores and generated notes (two up,
        four up from 2xl). Right: the feed preview and upload timing. The two
        columns come out about the same height, so neither leaves a hole.
      */}
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_22.5rem] 2xl:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="min-w-0 space-y-5">
          <Panel
            icon={Clapperboard}
            title={`${preview.label}${preview.id === chosen?.id ? " · in use" : ""}`}
            description="Copy each field into YouTube Studio, or copy the whole bundle at once."
            aside={
              <>
                {/* Written by Gemini or the local fallback: generated text either way. */}
                <EvidenceChip tone="warn">{preview.source}</EvidenceChip>
                <CopyButton value={copyValue(preview, "upload-package")} label="Copy all" variant="soft" />
              </>
            }
            data-testid="package-card"
          >
            <div className="space-y-6">
              <div className="space-y-2.5">
                <FieldHeader
                  icon={Type}
                  label="Title"
                  count={`${preview.title.length} chars`}
                  action={<CopyButton value={copyValue(preview, "title")} label="Copy title" />}
                />
                <p className="font-display text-xl font-semibold leading-snug tracking-tight text-foreground">
                  {preview.title}
                </p>
              </div>

              <div className="space-y-2.5">
                <FieldHeader
                  icon={FileText}
                  label="Description"
                  count={`${preview.description.length} chars`}
                  action={<CopyButton value={copyValue(preview, "description")} label="Copy description" />}
                />
                <p className="max-h-72 max-w-none overflow-y-auto whitespace-pre-wrap rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground scrollbar-thin">
                  <span className="block max-w-[80ch]">{preview.description || "No description returned."}</span>
                </p>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div className="space-y-2.5">
                  <FieldHeader
                    icon={Tag}
                    label="Video tags"
                    count={String(preview.tags.length)}
                    action={<CopyButton value={copyValue(preview, "tags")} label="Copy tags" />}
                  />
                  <TagList items={preview.tags} emptyLabel="No tags returned." />
                </div>
                <div className="space-y-2.5">
                  <FieldHeader
                    icon={Hash}
                    label="Hashtags"
                    count={String(preview.hashtags.length)}
                    action={<CopyButton value={copyValue(preview, "hashtags")} label="Copy hashtags" />}
                  />
                  <TagList items={preview.hashtags} emptyLabel="No hashtags returned." />
                </div>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Every option shares this description, tags and hashtags: the options differ in title and thumbnail.
              </p>
            </div>
          </Panel>

          <div className="grid gap-5 sm:grid-cols-2 2xl:grid-cols-4">
            <StatCard
              label="Opportunity score"
              icon={Target}
              value={opportunityText(opportunity.score)}
              caption={
                opportunityMeasured
                  ? "Local heuristic, not a performance guarantee."
                  : "Not measured: no competitor results were returned to score against."
              }
              tone={opportunityMeasured ? "warn" : "neutral"}
              toneLabel={opportunityMeasured ? "Heuristic" : "Unavailable"}
            />
            <StatCard
              label={`${preview.label} title quality`}
              icon={Type}
              value={titleScoreText(preview.titleQualityScore)}
              caption="Local title-quality heuristic, not measured CTR."
              tone="warn"
              toneLabel="Heuristic"
            />
            <Panel icon={ImageIcon} title="Thumbnail direction" aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}>
              <div className="space-y-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
                <p>{displayValue(preview.thumbnailVisual)}</p>
                <p>
                  Suggested text:{" "}
                  <span className="font-semibold text-foreground">{displayValue(preview.thumbnailText)}</span>
                </p>
              </div>
            </Panel>
            <Panel icon={HeartHandshake} title="Viewer promise" aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}>
              <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{displayValue(preview.viewerPromise)}</p>
            </Panel>

          </div>
        </div>

        <div className="space-y-5">
          <Panel
            icon={ImageIcon}
            title="Preview"
            description="A mock of the title and thumbnail text at feed size."
            aside={<EvidenceChip tone="warn">Mock-up</EvidenceChip>}
          >
            <SearchPreview option={preview} duration={duration || undefined} />
          </Panel>

          <Panel
            icon={CalendarClock}
            title="Upload timing guidance"
            data-testid="upload-timing-guidance"
            aside={
              // A heuristic whatever its confidence; the ok tone is for what the creator supplied.
              <EvidenceChip tone={timingConfidence ? "warn" : "neutral"}>
                {timingConfidence ? `Heuristic · ${timingConfidence} confidence` : "Unavailable"}
              </EvidenceChip>
            }
          >
            <div className="space-y-2.5">
              <Inset>
                <p className="text-xs text-muted-foreground">Best recurring window</p>
                <p className="mt-1 text-[0.8125rem] font-medium text-foreground">
                  {displayValue(timing.recommended_day)} · {recurringWindow}
                </p>
              </Inset>
              <Inset>
                <p className="text-xs text-muted-foreground">If uploading today</p>
                <p className="mt-1 text-[0.8125rem] font-medium text-foreground">
                  {displayValue(timing.today_recommendation)}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">Window: {todayWindow}</p>
              </Inset>
              <p className="text-xs leading-relaxed text-muted-foreground">
                <strong className="font-semibold text-foreground">Basis:</strong>{" "}
                {String(timing.basis ?? "unavailable").replaceAll("_", " ")}.{" "}
                {displayValue(timing.explanation, "Personalized upload timing is not yet established.")}
              </p>
            </div>
          </Panel>
        </div>
      </div>

    </div>
  );
}
