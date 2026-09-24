import {
  BadgeCheck,
  FileText,
  Gauge,
  Hash,
  HeartPulse,
  ListOrdered,
  ScrollText,
  Tag,
  Target,
  Type,
  X,
  Youtube,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { IconBadge } from "@/components/common/IconBadge";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, displayValue, formatNumber } from "@/lib/utils";
import { historyDate } from "@/lib/historyFormat";
import { uploadBundleText } from "@/lib/packages";
import type { HistoryRunDetail } from "@/api/historyTypes";

/** Older records predate full-package history, so absent fields say so plainly. */
const NOT_STORED = "Not stored in this older record.";

function TagList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-[13px] text-muted-foreground">{NOT_STORED}</p>;
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

function Section({
  icon: Icon,
  title,
  action,
  children,
}: {
  icon: React.ElementType;
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
          <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function Callout({
  icon,
  title,
  body,
  chip,
  tone = "neutral",
  action,
}: {
  icon: React.ComponentProps<typeof IconBadge>["icon"];
  title: string;
  body: string;
  chip?: string;
  tone?: EvidenceTone;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3.5">
      <IconBadge icon={icon} tone={tone === "neutral" ? "neutral" : tone} size="sm" />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-[13px] font-semibold text-foreground">{title}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{body}</p>
      </div>
      {chip ? <EvidenceChip tone={tone}>{chip}</EvidenceChip> : null}
      {action}
    </div>
  );
}

function ScoreTile({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3.5">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </p>
      <p className="mt-1.5 font-display text-lg font-semibold text-foreground">{value}</p>
      <p className="text-[11px] text-muted-foreground">{note}</p>
    </div>
  );
}

function DetailBody({ run, onLink }: { run: HistoryRunDetail; onLink: () => void }) {
  const pkg = asObject(run.package);
  const hasPackage = Object.keys(pkg).length > 0;

  const tags = asArray<string>(pkg.tags);
  const hashtags = asArray<string>(pkg.hashtags);
  const variants = asArray<unknown>(pkg.title_variants)
    .map((item) => (typeof item === "string" ? item : String(asObject(item).title ?? "")))
    .filter(Boolean);
  const chapters = asArray<unknown>(pkg.chapters)
    .map((item) => {
      const chapter = asObject(item);
      return `${chapter.timestamp ?? ""} ${chapter.title ?? ""}`.trim() || String(item);
    })
    .filter(Boolean);

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
    <div className="space-y-6">
      {!hasPackage ? (
        <div className="rounded-xl border border-tone-warn-border bg-tone-warn-bg p-3.5 text-xs leading-relaxed text-foreground">
          This package was created before full-package history was added. Its saved title, script,
          and scores are shown below; future packages retain the complete generated output.
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <ScoreTile
          icon={Target}
          label="Opportunity"
          value={`${formatNumber(run.opportunity_score)} / 100`}
          note={displayValue(run.opportunity_label, "Unavailable")}
        />
        <ScoreTile
          icon={Type}
          label="Title quality"
          value={`${formatNumber(run.title_score)} / 10`}
          note="Local heuristic"
        />
        <ScoreTile
          icon={Gauge}
          label="Retention risk"
          value={displayValue(run.retention_risk, "Unavailable")}
          note="Pre-publish guidance"
        />
      </div>

      <div className="space-y-2.5">
        <Callout
          icon={BadgeCheck}
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
            icon={HeartPulse}
            title={`Retention guidance: ${displayValue(retention.risk_level, "unknown")} risk`}
            body={`${displayValue(asObject(retention.trace).timing_basis, "relative stage")} · ${retentionRisks.length} deterministic finding(s). This is pre-publish guidance, not measured retention.`}
            chip={String(retention.rule_version ?? "Local rules")}
            tone="warn"
          />
        ) : null}

        <Callout
          icon={Youtube}
          title="Published-video learning"
          body={
            isLinked
              ? `Linked to YouTube video ${displayValue(report.youtube_video_id ?? run.linked_youtube_video_id)}. Performance evidence is kept with this package.`
              : "No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package."
          }
          tone={isLinked ? "info" : "neutral"}
          action={
            !isLinked ? (
              <Button size="sm" variant="outline" onClick={onLink}>
                Link video
              </Button>
            ) : undefined
          }
        />
      </div>

      <Section
        icon={FileText}
        title="Description"
        action={description ? <CopyButton value={description} label="Copy" size="xs" /> : null}
      >
        {description ? (
          <p className="whitespace-pre-wrap rounded-xl border border-border bg-elevated p-4 text-[13px] leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : (
          <UnavailableNote>{NOT_STORED}</UnavailableNote>
        )}
      </Section>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section
          icon={Tag}
          title="Tags"
          action={tags.length ? <CopyButton value={tags.join(", ")} label="Copy" size="xs" /> : null}
        >
          <TagList items={tags} />
        </Section>
        <Section
          icon={Hash}
          title="Hashtags"
          action={
            hashtags.length ? <CopyButton value={hashtags.join(" ")} label="Copy" size="xs" /> : null
          }
        >
          <TagList items={hashtags} />
        </Section>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section icon={Type} title="Title variants">
          {variants.length ? (
            <ul className="space-y-1.5">
              {variants.map((variant, index) => (
                <li
                  key={index}
                  className="rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-[13px] text-muted-foreground"
                >
                  {variant}
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>{NOT_STORED}</UnavailableNote>
          )}
        </Section>
        <Section icon={ListOrdered} title="Chapters">
          {chapters.length ? (
            <ul className="space-y-1.5">
              {chapters.map((chapter, index) => (
                <li
                  key={index}
                  className="numeric rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-xs text-muted-foreground"
                >
                  {chapter}
                </li>
              ))}
            </ul>
          ) : (
            <UnavailableNote>{NOT_STORED}</UnavailableNote>
          )}
        </Section>
      </div>

      <Section
        icon={ScrollText}
        title="Source script"
        action={fullScript ? <CopyButton value={fullScript} label="Copy" size="xs" /> : null}
      >
        {fullScript ? (
          <p className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl border border-border bg-elevated p-4 text-[13px] leading-relaxed text-muted-foreground scrollbar-thin">
            {fullScript}
          </p>
        ) : (
          <UnavailableNote>{NOT_STORED}</UnavailableNote>
        )}
      </Section>
    </div>
  );
}

/**
 * One saved package, in a panel that slides over the list. Opening it is a
 * URL change (`?run=`), so a package can be linked to and survives a reload.
 */
export function HistoryDetail({
  open,
  run,
  fallbackTitle,
  isLoading,
  error,
  onClose,
  onLink,
}: {
  open: boolean;
  run: HistoryRunDetail | null;
  fallbackTitle?: string;
  isLoading: boolean;
  error: unknown;
  onClose: () => void;
  onLink: () => void;
}) {
  const pkg = asObject(run?.package);
  const hasPackage = Object.keys(pkg).length > 0;
  const isLinked = Boolean(asObject(run?.linked_video_report).linked);
  const title = run ? displayValue(run.title, "Untitled package") : fallbackTitle || "Saved package";

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent data-testid="history-detail">
        <div className="relative overflow-hidden border-b border-border px-5 py-5 sm:px-7">
          <div
            className="pointer-events-none absolute -right-16 -top-24 size-64 rounded-full bg-brand-gradient opacity-15 blur-3xl"
            aria-hidden="true"
          />
          <div className="relative flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1.5">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-brand">
                Saved package
              </p>
              <SheetTitle className="font-display text-xl font-semibold leading-snug tracking-tight text-foreground">
                {isLoading && !run ? "Loading saved package…" : title}
              </SheetTitle>
              <SheetDescription className="text-xs text-muted-foreground">
                {run
                  ? `Saved ${historyDate(run.created_at)} · ${displayValue(run.content_angle, "General")} · ${isLinked ? "Linked to YouTube" : "Not linked"}`
                  : "Package details from your local History."}
              </SheetDescription>
            </div>
            <SheetClose asChild>
              <Button variant="ghost" size="icon" aria-label="Close package detail" className="-mr-2 -mt-1">
                <X aria-hidden="true" />
              </Button>
            </SheetClose>
          </div>
          {run ? (
            <div className="relative mt-4">
              {/* The page promises the saved package can be reused; without this the
                  only route was selecting text inside a scroll box. */}
              <CopyButton
                value={uploadBundleText({
                  title: String(pkg.title ?? run.title ?? ""),
                  description: String(pkg.description ?? ""),
                  tags: asArray<string>(pkg.tags),
                  hashtags: asArray<string>(pkg.hashtags),
                })}
                label="Copy upload package"
                variant="gradient"
                size="sm"
                disabled={!hasPackage}
              />
            </div>
          ) : null}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-6 scrollbar-thin sm:px-7">
          {isLoading ? (
            <CardSkeleton rows={6} />
          ) : error ? (
            <ErrorState
              message={apiErrorMessage(error, "Could not load this saved package.")}
              requestId={apiRequestId(error)}
            />
          ) : run ? (
            <DetailBody run={run} onLink={onLink} />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
