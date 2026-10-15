import {
  ArrowUpRight,
  BadgeCheck,
  BarChart3,
  FileText,
  Hash,
  HeartPulse,
  ListOrdered,
  Quote,
  ScrollText,
  Stethoscope,
  Tag,
  Type,
  Youtube,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { IconBadge } from "@/components/common/IconBadge";
import { Stat } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { LinkedVideoLearning } from "@/components/learning/LinkedVideoLearning";
import { asArray, asObject, displayValue } from "@/lib/utils";
import { formatCompact } from "@/lib/format";
import { historyDate } from "@/lib/historyFormat";
import { windowLabel } from "@/lib/auditFormat";
import { youtubeWatchUrl } from "@/lib/channelFormat";
import { cleanHashtags, cleanTags, hashtagsText, tagsText } from "@/lib/packages";
import type { HistoryRunDetail, LinkedVideoReport, PackageSelection } from "@/api/historyTypes";
import type { LinkedTrafficEvidence } from "@/api/learningTypes";

/** Older records predate full-package history, so absent fields say so plainly. */
export const NOT_STORED = "Not stored in this older record.";

function TagList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-[0.8125rem] text-muted-foreground">{NOT_STORED}</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item, index) => (
        <li
          key={`${item}-${index}`}
          className="max-w-full break-words rounded-lg border border-border bg-elevated px-2.5 py-1 text-xs text-foreground"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

export function Section({
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
    <section className="min-w-0 space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-[0.8125rem] font-semibold text-foreground">
          <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Callout({
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
      <div className="min-w-0 flex-1 basis-48 space-y-0.5">
        <p className="text-[0.8125rem] font-semibold text-foreground">{title}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{body}</p>
      </div>
      {chip ? <EvidenceChip tone={tone}>{chip}</EvidenceChip> : null}
      {action}
    </div>
  );
}

export function ScoreTile({
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
      <p className="text-[0.6875rem] text-muted-foreground">{note}</p>
    </div>
  );
}

/** The creator's recorded choice; a run without one says the tool won't guess it. */
export function SelectionCallout({ selection }: { selection: PackageSelection | null | undefined }) {
  const chosen = selection?.package ?? null;
  const recorded = Boolean(chosen && Object.keys(chosen).length);
  return (
    <Callout
      icon={BadgeCheck}
      title="Creator-selected package"
      body={
        recorded
          ? `${String(chosen?.title ?? "Selected package")} · selected ${historyDate(selection?.selected_at)}`
          : "No explicit selection was recorded. The tool will not infer one after publishing."
      }
      chip={recorded ? "Explicitly recorded" : "Unknown"}
      tone={recorded ? "ok" : "neutral"}
    />
  );
}

export function hasSelection(selection: PackageSelection | null | undefined): boolean {
  return Object.keys(selection?.package ?? {}).length > 0;
}

/** The retention assistant's verdict, or null when the package stored none. */
export function retentionGuidance(pkg: Record<string, unknown>) {
  const retention = asObject(pkg.retention_assistant);
  if (!Object.keys(retention).length) return null;
  const findings = asArray<unknown>(retention.risk_map).flatMap((stage) => asArray(asObject(stage).risks)).length;
  return { retention, findings };
}

export function RetentionCallout({ pkg }: { pkg: Record<string, unknown> }) {
  const guidance = retentionGuidance(pkg);
  if (!guidance) return null;
  const { retention, findings } = guidance;
  return (
    <Callout
      icon={HeartPulse}
      title={`Retention guidance: ${displayValue(retention.risk_level, "unknown")} risk`}
      body={`${displayValue(asObject(retention.trace).timing_basis, "relative stage")} · ${findings} deterministic finding(s). This is pre-publish guidance, not measured retention.`}
      chip={String(retention.rule_version ?? "Local rules")}
      tone="warn"
    />
  );
}

export function LinkCallout({ onLink, body }: { onLink: () => void; body?: string }) {
  return (
    <Callout
      icon={Youtube}
      title="Published-video learning"
      body={
        body ??
        "No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package."
      }
      tone="neutral"
      action={
        <Button size="sm" variant="outline" onClick={onLink}>
          Link video
        </Button>
      }
    />
  );
}

function percent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "Unavailable";
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1">
      {items.map((item) => (
        <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
          {item}
        </li>
      ))}
    </ul>
  );
}

/**
 * What went live and how it did: the linked video's report. Every number is
 * the stored measurement or "Unavailable", never a zero standing in for one.
 */
export function PublishedVideo({ report, fallbackTitle }: { report: LinkedVideoReport; fallbackTitle: string }) {
  const performance = report.performance ?? {};
  const usage = report.package_usage ?? {};
  const diagnosis = report.diagnosis ?? {};
  const url = youtubeWatchUrl(report.video_id);
  // oEmbed-only metadata can lack a title; fall back to what was published from, never to "undefined".
  const uploadedTitle = report.youtube?.title || usage.uploaded_title || fallbackTitle;
  const titleKnown = Boolean(report.youtube?.title || usage.uploaded_title);
  const generatedTags = asArray<string>(usage.generated_tags);
  const matchingTags = asArray<string>(usage.matching_tags);
  const worked = asArray<string>(diagnosis.what_worked);
  const improve = asArray<string>(diagnosis.needs_improvement);

  return (
    <Section
      icon={Youtube}
      title="Published video"
      action={
        <EvidenceChip tone={report.ownership_verified ? "ok" : "neutral"}>
          {report.ownership_verified ? "Verified owner" : "Unverified"}
        </EvidenceChip>
      }
    >
      <div className="space-y-4 rounded-xl border border-border bg-card p-4" data-testid="published-video">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="numeric inline-flex items-center gap-1 text-brand underline-offset-4 hover:underline"
              >
                {report.video_id}
                <ArrowUpRight className="size-3" aria-hidden="true" />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : (
              "Video ID unavailable"
            )}
            {report.published_at ? ` · published ${historyDate(report.published_at)}` : ""}
          </p>
          <p className="break-words text-sm font-medium text-foreground">{uploadedTitle}</p>
          {titleKnown && typeof usage.title_match === "boolean" ? (
            <EvidenceChip tone={usage.title_match ? "ok" : "warn"}>
              {usage.title_match
                ? usage.attribution_status === "creator_selected"
                  ? "Same title as your selection"
                  : "Same title as the package"
                : "Title changed before publishing"}
            </EvidenceChip>
          ) : null}
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
              <BarChart3 className="size-3.5 text-muted-foreground" aria-hidden="true" />
              Performance
            </p>
            <EvidenceChip tone="info">YouTube data</EvidenceChip>
          </div>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Views" value={formatCompact(performance.views)} />
            <Stat label="Likes" value={formatCompact(performance.likes)} />
            <Stat label="Comments" value={formatCompact(performance.comments)} />
            <Stat label="Avg viewed" value={percent(performance.average_view_percentage)} />
          </dl>
          <p className="text-xs text-muted-foreground">
            {performance.captured_at
              ? `${windowLabel(performance.snapshot_window)} · captured ${historyDate(performance.captured_at)}.`
              : "No performance snapshot has been captured yet."}
          </p>
        </div>

        <div className="space-y-1">
          <p className="text-xs font-medium text-foreground">What was used from the package</p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {generatedTags.length
              ? `${matchingTags.length.toLocaleString()} of ${generatedTags.length.toLocaleString()} generated tags are on the video.`
              : "The package had no tags to compare."}{" "}
            {displayValue(usage.attribution_note, "")}
          </p>
        </div>

        {diagnosis.verdict ? (
          <div className="space-y-2 border-t border-border pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                <Stethoscope className="size-3.5 text-muted-foreground" aria-hidden="true" />
                {diagnosis.verdict}
              </p>
              <EvidenceChip tone="warn">Local heuristic</EvidenceChip>
            </div>
            {worked.length ? <BulletList items={worked} /> : null}
            {improve.length ? <BulletList items={improve} /> : null}
            <p className="text-[0.6875rem] leading-relaxed text-muted-foreground">
              {diagnosis.confidence ? `${diagnosis.confidence}. ` : ""}
              Compares completed windows only. {displayValue(diagnosis.attribution_note, "")}
            </p>
          </div>
        ) : null}

        <LinkedVideoLearning
          evidence={report as LinkedVideoReport & LinkedTrafficEvidence}
          linkId={typeof report.link_id === "number" ? report.link_id : null}
          verified={Boolean(report.ownership_verified)}
        />
      </div>
    </Section>
  );
}

/**
 * The saved upload package: description, tags, hashtags, title variants and
 * the text it was written from. A Short has no chapters, and its source is
 * the quote.
 */
export function SavedPackageFields({ run, shorts = false }: { run: HistoryRunDetail; shorts?: boolean }) {
  const pkg = asObject(run.package);
  // Cleaned once, so the tags on screen are exactly the tags that get pasted.
  const tags = cleanTags(pkg.tags);
  const hashtags = cleanHashtags(pkg.hashtags);
  const description = String(pkg.description ?? "");
  const variants = asArray<unknown>(pkg.title_variants)
    .map((item) => (typeof item === "string" ? item : String(asObject(item).title ?? "")))
    .filter(Boolean);
  // Chapters are only kept when the creator wrote a valid list; none are invented.
  const chaptersStored = Array.isArray(pkg.chapters);
  const chapters = asArray<unknown>(pkg.chapters)
    .map((item) => {
      const chapter = asObject(item);
      return `${chapter.timestamp ?? ""} ${chapter.title ?? ""}`.trim() || String(item);
    })
    .filter(Boolean);
  const source = String(asObject(pkg.creator_brief).content ?? run.query ?? "");

  const titleVariants = (
    <Section icon={Type} title="Title variants">
      {variants.length ? (
        <ul className="space-y-1.5">
          {variants.map((variant, index) => (
            <li
              key={index}
              className="break-words rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-[0.8125rem] text-muted-foreground"
            >
              {variant}
            </li>
          ))}
        </ul>
      ) : (
        <UnavailableNote>{NOT_STORED}</UnavailableNote>
      )}
    </Section>
  );

  return (
    <div className="space-y-6">
      <Section
        icon={FileText}
        title="Description"
        action={description ? <CopyButton value={description} label="Copy" size="xs" /> : null}
      >
        {description ? (
          <p className="whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground">
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
          action={tags.length ? <CopyButton value={tagsText(tags)} label="Copy" size="xs" /> : null}
        >
          <TagList items={tags} />
        </Section>
        <Section
          icon={Hash}
          title="Hashtags"
          action={
            hashtags.length ? <CopyButton value={hashtagsText(hashtags)} label="Copy" size="xs" /> : null
          }
        >
          <TagList items={hashtags} />
        </Section>
      </div>

      {shorts ? (
        titleVariants
      ) : (
        <div className="grid gap-6 sm:grid-cols-2">
          {titleVariants}
          <Section icon={ListOrdered} title="Chapters">
            {chapters.length ? (
              <ul className="space-y-1.5">
                {chapters.map((chapter, index) => (
                  <li
                    key={index}
                    className="numeric break-words rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-xs text-muted-foreground"
                  >
                    {chapter}
                  </li>
                ))}
              </ul>
            ) : (
              <UnavailableNote>
                {chaptersStored ? "No chapters: add your own timestamps to the description." : NOT_STORED}
              </UnavailableNote>
            )}
          </Section>
        </div>
      )}

      <Section
        icon={shorts ? Quote : ScrollText}
        title={shorts ? "Quote" : "Source script"}
        action={source ? <CopyButton value={source} label="Copy" size="xs" /> : null}
      >
        {source ? (
          <p className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground scrollbar-thin">
            {source}
          </p>
        ) : (
          <UnavailableNote>{NOT_STORED}</UnavailableNote>
        )}
      </Section>
    </div>
  );
}
