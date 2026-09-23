import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { EmptyState, UnavailableNote } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { asObject, cn, displayValue, formatNumber } from "@/lib/utils";
import { copyValue } from "@/lib/packages";
import type { AnalyzeResponse, PackageOption, SelectionStatus } from "@/api/types";

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (!items.length) return <p className="text-xs text-muted-foreground">{emptyLabel}</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item, index) => (
        <li
          key={`${item}-${index}`}
          className="rounded-md border border-border bg-muted/50 px-2 py-1 text-[11px] text-foreground"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

export function PackagingStage({
  data,
  options,
  selected,
  selectionStatus,
  onSelect,
}: {
  data: AnalyzeResponse | null;
  options: PackageOption[];
  selected: PackageOption | null;
  selectionStatus: SelectionStatus;
  onSelect: (packageId: string) => void;
}) {
  if (!data) {
    return (
      <EmptyState
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
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Opportunity score"
          value={`${displayValue(opportunity.score)} / 100`}
          caption="Local heuristic, not a performance guarantee."
          tone="warn"
          toneLabel="Heuristic"
        />
        <StatCard
          label="Selected title quality"
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
          value={selected.label}
          caption={selectionCaption}
          tone={selectionStatus === "saved" ? "ok" : selectionStatus === "error" ? "bad" : "warn"}
          toneLabel={selectionStatus === "saved" ? "Saved" : "Local"}
        />
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
          <CardTitle>Generated SEO package</CardTitle>
          <EvidenceChip tone={data.generation_source === "gemini" ? "info" : "warn"}>
            {selected.source}
          </EvidenceChip>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">Selected title</span>
                <span className="numeric rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {selected.title.length} chars
                </span>
              </div>
              <CopyButton value={copyValue(selected, "title")} label="Copy title" />
            </div>
            <p className="text-base font-bold leading-snug text-foreground">{selected.title}</p>
          </div>

          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">Description</span>
                <span className="numeric rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {selected.description.length} chars
                </span>
              </div>
              <CopyButton value={copyValue(selected, "description")} label="Copy description" />
            </div>
            <p className="whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
              {selected.description || "No description returned."}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">Video tags</span>
                <CopyButton value={copyValue(selected, "tags")} label="Copy tags" />
              </div>
              <TagList items={selected.tags} emptyLabel="No tags returned." />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">Hashtags</span>
                <CopyButton value={copyValue(selected, "hashtags")} label="Copy hashtags" />
              </div>
              <TagList items={selected.hashtags} emptyLabel="No hashtags returned." />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="upload-timing-guidance">
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
          <CardTitle>Upload timing guidance</CardTitle>
          <EvidenceChip tone={timing.confidence === "HIGH" ? "ok" : "warn"}>
            {String(timing.confidence ?? "unavailable").toUpperCase()}
          </EvidenceChip>
        </CardHeader>
        <CardContent className="space-y-2.5">
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <p className="text-xs font-semibold text-foreground">Best recurring window</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {displayValue(timing.recommended_day)} · {recurringWindow}
            </p>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <p className="text-xs font-semibold text-foreground">If uploading today</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {displayValue(timing.today_recommendation)}
              <br />
              Window: {todayWindow}
            </p>
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            <strong className="text-foreground">Basis:</strong>{" "}
            {String(timing.basis ?? "unavailable").replaceAll("_", " ")}.{" "}
            {displayValue(timing.explanation, "Personalized upload timing is not yet established.")}
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Thumbnail direction</CardTitle>
            <EvidenceChip tone="warn">Generated</EvidenceChip>
          </CardHeader>
          <CardContent className="space-y-1 text-xs leading-relaxed text-muted-foreground">
            <p>{displayValue(selected.thumbnailVisual)}</p>
            <p>Suggested text: {displayValue(selected.thumbnailText)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle>Viewer promise</CardTitle>
            <EvidenceChip tone="warn">Generated</EvidenceChip>
          </CardHeader>
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            {displayValue(selected.viewerPromise)}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Title alternatives</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {options.length ? (
            options.map((option) => (
              <div
                key={option.id}
                className={cn(
                  "flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between",
                  option.id === selected.id
                    ? "border-primary/50 bg-primary/5"
                    : "border-border bg-muted/20",
                )}
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-foreground">{option.label}</span>
                    {option.primary ? (
                      <EvidenceChip tone="info">Primary</EvidenceChip>
                    ) : null}
                    <span className="numeric rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {option.title.length} chars
                    </span>
                  </div>
                  <p className="break-words text-xs text-muted-foreground">{option.title}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <CopyButton value={copyValue(option, "title")} label="Copy" />
                  <Button
                    size="sm"
                    variant={option.id === selected.id ? "default" : "outline"}
                    onClick={() => onSelect(option.id)}
                    aria-pressed={option.id === selected.id}
                  >
                    {option.id === selected.id ? "Selected" : "Select"}
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <UnavailableNote>No title alternatives were returned.</UnavailableNote>
          )}
          <p className="pt-1 text-[11px] leading-relaxed text-muted-foreground">
            All choices reuse the generated description, tags, and hashtags, because the API returns
            title and thumbnail alternatives rather than separately generated metadata bundles.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
