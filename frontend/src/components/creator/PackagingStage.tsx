import {
  CalendarClock,
  Clapperboard,
  FileText,
  Hash,
  HeartHandshake,
  Image as ImageIcon,
  ListOrdered,
  Tag,
  Target,
  Type,
  Bookmark,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Inset, Panel } from "@/components/common/Panel";
import { EmptyState, UnavailableNote } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { asObject, cn, displayValue, formatNumber } from "@/lib/utils";
import { formatSeconds } from "@/lib/format";
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

/** How the selected package might look in a search list. A mock, labelled as one. */
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

export function PackagingStage({
  data,
  options,
  selected,
  selectionStatus,
  onSelect,
  durationSeconds,
}: {
  data: AnalyzeResponse | null;
  options: PackageOption[];
  selected: PackageOption | null;
  selectionStatus: SelectionStatus;
  onSelect: (packageId: string) => void;
  durationSeconds?: string;
}) {
  if (!data) {
    return (
      <EmptyState
        icon={Clapperboard}
        title="No package yet"
        description="Run Analyze to generate a title, description, tags, hashtags, and comparison options."
      />
    );
  }
  if (!selected) {
    return <EmptyState title="The analysis returned no usable package option." />;
  }

  const opportunity = asObject(asObject(data.opportunity_gap_analysis).opportunity_score);
  const timing = asObject(data.upload_timing);
  const timingZone = String(timing.timezone ?? timing.today_timezone ?? "").trim();
  const duration = durationSeconds ? formatSeconds(durationSeconds, "") : "";

  const recurringWindow =
    timing.recommended_time && timingZone
      ? `${timing.recommended_time} ${timingZone}`
      : "Unavailable until a timezone-explicit recommendation is calculated";
  const todayWindow =
    timing.today_time && (timing.today_timezone || timingZone)
      ? `${timing.today_time} ${timing.today_timezone || timingZone}`
      : "Unavailable";

  const selectionCaption =
    selectionStatus === "saved"
      ? "Saved to History; not published."
      : selectionStatus === "saving"
        ? "Saving to History…"
        : selectionStatus === "error"
          ? "Could not save; retry selection."
          : "Preview only until you select it.";

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Opportunity score"
          icon={Target}
          value={`${displayValue(opportunity.score)} / 100`}
          caption="Local heuristic, not a performance guarantee."
          tone="warn"
          toneLabel="Heuristic"
        />
        <StatCard
          label="Selected title quality"
          icon={Type}
          value={
            selected.titleQualityScore === null
              ? "Unavailable"
              : `${formatNumber(selected.titleQualityScore)} / 10`
          }
          caption="Local title-quality heuristic, not measured CTR."
          tone="warn"
          toneLabel="Heuristic"
        />
        <StatCard
          label="Selection"
          icon={Bookmark}
          iconTone={selectionStatus === "saved" ? "ok" : "brand"}
          value={selected.label}
          caption={selectionCaption}
          tone={selectionStatus === "saved" ? "ok" : selectionStatus === "error" ? "bad" : "warn"}
          toneLabel={selectionStatus === "saved" ? "Saved" : "Local"}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22.5rem]">
        <div className="min-w-0 space-y-5">
          <Panel
            icon={Clapperboard}
            title="Generated SEO package"
            description="Copy each field into YouTube Studio, or copy the whole bundle at once."
            aside={
              <>
                <EvidenceChip tone={data.generation_source === "gemini" ? "info" : "warn"}>
                  {selected.source}
                </EvidenceChip>
                <CopyButton
                  value={copyValue(selected, "upload-package")}
                  label="Copy all"
                  variant="soft"
                />
              </>
            }
          >
            <div className="space-y-6">
              <div className="space-y-2.5">
                <FieldHeader
                  icon={Type}
                  label="Selected title"
                  count={`${selected.title.length} chars`}
                  action={<CopyButton value={copyValue(selected, "title")} label="Copy title" />}
                />
                <p className="font-display text-xl font-semibold leading-snug tracking-tight text-foreground">
                  {selected.title}
                </p>
              </div>

              <div className="space-y-2.5">
                <FieldHeader
                  icon={FileText}
                  label="Description"
                  count={`${selected.description.length} chars`}
                  action={
                    <CopyButton value={copyValue(selected, "description")} label="Copy description" />
                  }
                />
                <p className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground scrollbar-thin">
                  {selected.description || "No description returned."}
                </p>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div className="space-y-2.5">
                  <FieldHeader
                    icon={Tag}
                    label="Video tags"
                    count={String(selected.tags.length)}
                    action={<CopyButton value={copyValue(selected, "tags")} label="Copy tags" />}
                  />
                  <TagList items={selected.tags} emptyLabel="No tags returned." />
                </div>
                <div className="space-y-2.5">
                  <FieldHeader
                    icon={Hash}
                    label="Hashtags"
                    count={String(selected.hashtags.length)}
                    action={<CopyButton value={copyValue(selected, "hashtags")} label="Copy hashtags" />}
                  />
                  <TagList items={selected.hashtags} emptyLabel="No hashtags returned." />
                </div>
              </div>
            </div>
          </Panel>
          <div className="grid gap-4 md:grid-cols-2">
            <Panel
              icon={ImageIcon}
              title="Thumbnail direction"
              aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}
            >
              <div className="space-y-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
                <p>{displayValue(selected.thumbnailVisual)}</p>
                <p>
                  Suggested text:{" "}
                  <span className="font-semibold text-foreground">{displayValue(selected.thumbnailText)}</span>
                </p>
              </div>
            </Panel>
            <Panel
              icon={HeartHandshake}
              title="Viewer promise"
              aside={<EvidenceChip tone="warn">Generated</EvidenceChip>}
            >
              <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                {displayValue(selected.viewerPromise)}
              </p>
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
            <SearchPreview option={selected} duration={duration || undefined} />
          </Panel>

          <Panel
            icon={CalendarClock}
            title="Upload timing guidance"
            data-testid="upload-timing-guidance"
            aside={
              <EvidenceChip tone={timing.confidence === "HIGH" ? "ok" : "warn"}>
                {String(timing.confidence ?? "unavailable").toUpperCase()}
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
                {displayValue(
                  timing.explanation,
                  "Personalized upload timing is not yet established.",
                )}
              </p>
            </div>
          </Panel>
        </div>
      </div>

      <Panel icon={ListOrdered} title="Title alternatives">
        <div className="space-y-2">
          {options.length ? (
            options.map((option) => {
              const isSelected = option.id === selected.id;
              return (
                <div
                  key={option.id}
                  className={cn(
                    "flex flex-col gap-3 rounded-xl border p-3.5 transition-colors sm:flex-row sm:items-center sm:justify-between",
                    isSelected ? "border-brand-border bg-brand-soft/50" : "border-border bg-elevated",
                  )}
                >
                  <div className="min-w-0 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[0.8125rem] font-semibold text-foreground">{option.label}</span>
                      {option.primary ? <Badge variant="brand">Primary</Badge> : null}
                      <Badge variant="neutral" className="numeric">
                        {option.title.length} chars
                      </Badge>
                    </div>
                    <p className="break-words text-[0.8125rem] text-muted-foreground">{option.title}</p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <CopyButton value={copyValue(option, "title")} label="Copy" />
                    <Button
                      size="sm"
                      variant={isSelected ? "default" : "outline"}
                      onClick={() => onSelect(option.id)}
                      aria-pressed={isSelected}
                    >
                      {isSelected ? "Selected" : "Select"}
                    </Button>
                  </div>
                </div>
              );
            })
          ) : (
            <UnavailableNote>No title alternatives were returned.</UnavailableNote>
          )}
          <p className="pt-1 text-xs leading-relaxed text-muted-foreground">
            All choices reuse the generated description, tags, and hashtags, because the API returns
            title and thumbnail alternatives rather than separately generated metadata bundles.
          </p>
        </div>
      </Panel>
    </div>
  );
}
