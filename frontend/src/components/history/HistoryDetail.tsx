import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, displayValue, formatNumber } from "@/lib/utils";
import { historyDate } from "@/lib/historyFormat";
import { uploadBundleText } from "@/lib/packages";
import type { HistoryRunDetail } from "@/api/historyTypes";

/** Older records predate full-package history, so absent fields say so plainly. */
const NOT_STORED = "Not stored in this older record.";

function TagList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-xs text-muted-foreground">{NOT_STORED}</p>;
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

function Callout({
  title,
  body,
  chip,
  tone,
  action,
}: {
  title: string;
  body: string;
  chip?: string;
  tone?: "ok" | "warn" | "info" | "neutral" | "bad";
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="min-w-0 space-y-0.5">
        <p className="text-xs font-bold text-foreground">{title}</p>
        <p className="text-[11px] leading-relaxed text-muted-foreground">{body}</p>
      </div>
      {chip ? <EvidenceChip tone={tone}>{chip}</EvidenceChip> : null}
      {action}
    </div>
  );
}

export function HistoryDetail({
  run,
  isLoading,
  error,
  onClose,
  onLink,
}: {
  run: HistoryRunDetail | null;
  isLoading: boolean;
  error: unknown;
  onClose: () => void;
  onLink: () => void;
}) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-5">
          <p className="mb-3 text-xs text-muted-foreground">Loading saved package…</p>
          <CardSkeleton rows={5} />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <ErrorState
        message={apiErrorMessage(error, "Could not load this saved package.")}
        requestId={apiRequestId(error)}
      />
    );
  }

  if (!run) return null;

  const pkg = asObject(run.package);
  const hasPackage = Object.keys(pkg).length > 0;

  const tags = asArray<string>(pkg.tags);
  const hashtags = asArray<string>(pkg.hashtags);
  const variants = asArray<unknown>(pkg.title_variants).map((item) =>
    typeof item === "string" ? item : String(asObject(item).title ?? ""),
  );
  const chapters = asArray<unknown>(pkg.chapters).map((item) => {
    const chapter = asObject(item);
    return `${chapter.timestamp ?? ""} ${chapter.title ?? ""}`.trim() || String(item);
  });

  const brief = asObject(pkg.creator_brief);
  const fullScript = String(brief.content ?? run.query ?? "");

  const selection = asObject(run.selected_package);
  const selectedData = asObject(selection.package);
  const hasSelection = Object.keys(selectedData).length > 0;

  const retention = asObject(pkg.retention_assistant);
  const retentionRisks = asArray<{ risks?: unknown[] }>(retention.risk_map).flatMap((stage) =>
    asArray(asObject(stage).risks),
  );

  const report = asObject(run.linked_video_report);
  const isLinked = Boolean(report.linked);

  const description = String(pkg.description ?? "");

  return (
    <Card data-testid="history-detail">
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="min-w-0 space-y-1">
          <CardTitle className="text-base">{displayValue(run.title, "Untitled package")}</CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Saved {historyDate(run.created_at)} · {displayValue(run.content_angle, "General")} ·{" "}
            {isLinked ? "Linked to YouTube" : "Not linked"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {/* The page promises the saved package can be reused; without this the
              only route was selecting text inside a scroll box. */}
          <CopyButton
            value={uploadBundleText({
              title: String(pkg.title ?? run.title ?? ""),
              description,
              tags,
              hashtags,
            })}
            label="Copy upload package"
            disabled={!hasPackage}
          />
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close package detail">
            <X aria-hidden="true" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {!hasPackage ? (
          <div className="rounded-lg border border-tone-warn-border bg-tone-warn-bg p-3 text-[11px] leading-relaxed text-foreground">
            This package was created before full-package history was added. Its saved title, script,
            and scores are shown below; future packages retain the complete generated output.
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Opportunity
            </p>
            <p className="numeric text-sm font-bold text-foreground">
              {formatNumber(run.opportunity_score)} / 100
            </p>
            <p className="text-[10px] text-muted-foreground">
              {displayValue(run.opportunity_label, "Unavailable")}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Title quality
            </p>
            <p className="numeric text-sm font-bold text-foreground">
              {formatNumber(run.title_score)} / 10
            </p>
            <p className="text-[10px] text-muted-foreground">Local heuristic</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Retention risk
            </p>
            <p className="text-sm font-bold text-foreground">
              {displayValue(run.retention_risk, "Unavailable")}
            </p>
            <p className="text-[10px] text-muted-foreground">Pre-publish guidance</p>
          </div>
        </div>

        <Callout
          title="Creator-selected package"
          body={
            hasSelection
              ? `${String(selectedData.title ?? "Selected package")} · selected ${historyDate(String(selection.selected_at ?? ""))}`
              : "No explicit selection was recorded. The tool will not infer one after publishing."
          }
          chip={hasSelection ? "Explicitly recorded" : "Unknown"}
          tone={hasSelection ? "ok" : "neutral"}
        />

        {Object.keys(retention).length ? (
          <Callout
            title={`Retention guidance: ${displayValue(retention.risk_level, "unknown")} risk`}
            body={`${displayValue(asObject(retention.trace).timing_basis, "relative stage")} · ${retentionRisks.length} deterministic finding(s). This is pre-publish guidance, not measured retention.`}
            chip={String(retention.rule_version ?? "Local rules")}
            tone="warn"
          />
        ) : null}

        <Callout
          title="Published-video learning"
          body={
            isLinked
              ? `Linked to YouTube video ${displayValue(report.youtube_video_id ?? run.linked_youtube_video_id)}. Performance evidence is kept with this package.`
              : "No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package."
          }
          action={
            !isLinked ? (
              <Button size="sm" variant="outline" onClick={onLink}>
                Link video
              </Button>
            ) : undefined
          }
        />

        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-foreground">Description</p>
            {description ? <CopyButton value={description} label="Copy" /> : null}
          </div>
          {description ? (
            <p className="whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
              {description}
            </p>
          ) : (
            <UnavailableNote>{NOT_STORED}</UnavailableNote>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">Tags</p>
              {tags.length ? <CopyButton value={tags.join(", ")} label="Copy" /> : null}
            </div>
            <TagList items={tags} />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">Hashtags</p>
              {hashtags.length ? <CopyButton value={hashtags.join(" ")} label="Copy" /> : null}
            </div>
            <TagList items={hashtags} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs font-semibold text-foreground">Title variants</p>
            {variants.filter(Boolean).length ? (
              <ul className="space-y-1.5">
                {variants.filter(Boolean).map((variant, index) => (
                  <li
                    key={index}
                    className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
                  >
                    {variant}
                  </li>
                ))}
              </ul>
            ) : (
              <UnavailableNote>{NOT_STORED}</UnavailableNote>
            )}
          </div>
          <div className="space-y-2">
            <p className="text-xs font-semibold text-foreground">Chapters</p>
            {chapters.filter(Boolean).length ? (
              <ul className="space-y-1.5">
                {chapters.filter(Boolean).map((chapter, index) => (
                  <li
                    key={index}
                    className="numeric rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
                  >
                    {chapter}
                  </li>
                ))}
              </ul>
            ) : (
              <UnavailableNote>{NOT_STORED}</UnavailableNote>
            )}
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-foreground">Source script</p>
            {fullScript ? <CopyButton value={fullScript} label="Copy" /> : null}
          </div>
          {fullScript ? (
            <p className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground scrollbar-thin">
              {fullScript}
            </p>
          ) : (
            <UnavailableNote>{NOT_STORED}</UnavailableNote>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
