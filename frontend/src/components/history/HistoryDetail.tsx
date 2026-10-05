import {
  ArrowUpRight,
  BadgeCheck,
  BarChart3,
  Clapperboard,
  FileText,
  Gauge,
  Hash,
  HeartPulse,
  ListOrdered,
  ScrollText,
  Stethoscope,
  Tag,
  Target,
  Type,
  X,
  Youtube,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip, type EvidenceTone } from "@/components/common/EvidenceChip";
import { IconBadge } from "@/components/common/IconBadge";
import { Stat } from "@/components/common/Panel";
import { CardSkeleton, ErrorState, UnavailableNote } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { asArray, asObject, displayValue } from "@/lib/utils";
import { formatCompact, toFiniteNumber } from "@/lib/format";
import { opportunityText, titleScoreText } from "@/lib/dashboardFormat";
import { historyDate } from "@/lib/historyFormat";
import { partsLabel } from "@/lib/aiShortsFormat";
import { windowLabel } from "@/lib/auditFormat";
import { youtubeWatchUrl } from "@/lib/channelFormat";
import { cleanHashtags, cleanTags, hashtagsText, tagsText, uploadBundleText } from "@/lib/packages";
import type { HistoryRunDetail, LinkedVideoReport } from "@/api/historyTypes";
import { HistoryOpportunityBreakdown } from "./HistoryOpportunityBreakdown";
import { LinkedVideoLearning } from "@/components/learning/LinkedVideoLearning";
import { StudioTestPanel } from "@/components/learning/StudioTestPanel";
import type { LinkedTrafficEvidence } from "@/api/learningTypes";

/** Older records predate full-package history, so absent fields say so plainly. */
const NOT_STORED = "Not stored in this older record.";

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
        <p className="text-[0.8125rem] font-semibold text-foreground">{title}</p>
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
      <p className="text-[0.6875rem] text-muted-foreground">{note}</p>
    </div>
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
function PublishedVideo({ report, fallbackTitle }: { report: LinkedVideoReport; fallbackTitle: string }) {
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
          <p className="text-sm font-medium text-foreground">{uploadedTitle}</p>
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

function DetailBody({ run, onLink }: { run: HistoryRunDetail; onLink: () => void }) {
  const pkg = asObject(run.package);
  const hasPackage = Object.keys(pkg).length > 0;

  // Cleaned once, so the tags on screen are exactly the tags that get pasted.
  const tags = cleanTags(pkg.tags);
  const hashtags = cleanHashtags(pkg.hashtags);
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

  const brief = asObject(pkg.creator_brief);
  const fullScript = String(brief.content ?? run.query ?? "");

  const selection = run.selected_package ?? null;
  const selectedData = selection?.package ?? null;
  const hasSelection = Boolean(selectedData && Object.keys(selectedData).length);

  const retention = asObject(pkg.retention_assistant);
  const retentionRisks = asArray<{ risks?: unknown[] }>(retention.risk_map).flatMap((stage) =>
    asArray(asObject(stage).risks),
  );

  const report = run.linked_video_report ?? null;
  const isLinked = Boolean(report?.linked);
  const description = String(pkg.description ?? "");
  const unmeasured = run.opportunity_label === "UNMEASURED";

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
          // An unmeasured score was once stored as 0; the label says it was never measured.
          value={unmeasured ? "Unavailable" : opportunityText(run.opportunity_score)}
          note={unmeasured ? "Not measured: no competitor results" : displayValue(run.opportunity_label, "Unavailable")}
        />
        <ScoreTile
          icon={Type}
          label="Title quality"
          value={titleScoreText(run.title_score)}
          note="Local heuristic"
        />
        <ScoreTile
          icon={Gauge}
          label="Retention risk"
          value={displayValue(run.retention_risk, "Unavailable")}
          note="Pre-publish guidance"
        />
      </div>
      <HistoryOpportunityBreakdown run={run} />

      <div className="space-y-2.5">
        <Callout
          icon={BadgeCheck}
          title="Creator-selected package"
          body={
            hasSelection
              ? `${String(selectedData?.title ?? "Selected package")} · selected ${historyDate(selection?.selected_at)}`
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

        {!isLinked ? (
          <Callout
            icon={Youtube}
            title="Published-video learning"
            body="No YouTube video is linked yet. Link it after publishing to keep performance evidence with this package."
            tone="neutral"
            action={
              <Button size="sm" variant="outline" onClick={onLink}>
                Link video
              </Button>
            }
          />
        ) : null}
      </div>

      {isLinked && report ? (
        <PublishedVideo
          report={report}
          fallbackTitle={String(selectedData?.title || pkg.title || run.title || "Saved package")}
        />
      ) : null}

      {hasPackage ? <StudioTestPanel runId={run.id} /> : null}

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

      <div className="grid gap-6 sm:grid-cols-2">
        <Section icon={Type} title="Title variants">
          {variants.length ? (
            <ul className="space-y-1.5">
              {variants.map((variant, index) => (
                <li
                  key={index}
                  className="rounded-xl border border-border bg-elevated px-3.5 py-2.5 text-[0.8125rem] text-muted-foreground"
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
            <UnavailableNote>
              {chaptersStored ? "No chapters: add your own timestamps to the description." : NOT_STORED}
            </UnavailableNote>
          )}
        </Section>
      </div>

      <Section
        icon={ScrollText}
        title="Source script"
        action={fullScript ? <CopyButton value={fullScript} label="Copy" size="xs" /> : null}
      >
        {fullScript ? (
          <p className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground scrollbar-thin">
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
 * The AI Shorts plan a package was written from. Its saved payload carries
 * `source_page: "ai_shorts"` and an `ai_shorts` block naming the plan; a row
 * carries the same once the server copies them out of the payload.
 */
function aiShortsMarker(run: HistoryRunDetail | null): { planId: number | null; label: string } | null {
  if (!run) return null;
  const pkg = asObject(run.package);
  const marker = asObject(run.ai_shorts ?? pkg.ai_shorts);
  const written =
    run.source_page === "ai_shorts" || pkg.source_page === "ai_shorts" || Object.keys(marker).length > 0;
  if (!written) return null;
  const planId = toFiniteNumber(marker.plan_id);
  const parts = toFiniteNumber(marker.parts);
  const total = toFiniteNumber(marker.total_seconds);
  return {
    planId: planId !== null && planId > 0 ? planId : null,
    label: parts !== null && parts > 0 ? `AI Shorts · ${partsLabel(parts, total ?? undefined)}` : "AI Shorts",
  };
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
  const isLinked = Boolean(run?.linked_video_report?.linked);
  const title = run ? displayValue(run.title, "Untitled package") : fallbackTitle || "Saved package";
  // The creator's recorded choice is what they meant to publish, so it is what gets copied.
  const chosen = run?.selected_package?.package ?? null;
  const aiShorts = aiShortsMarker(run);

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      {/* Wider on wide screens, where the package's two-column sections have room. */}
      <SheetContent data-testid="history-detail" className="xl:max-w-3xl 2xl:max-w-4xl">
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
            <div className="relative mt-4 flex flex-wrap items-center gap-2">
              {/* The page promises the saved package can be reused; without this the
                  only route was selecting text inside a scroll box. */}
              <CopyButton
                value={uploadBundleText({
                  title: String(chosen?.title || pkg.title || run.title || ""),
                  description: String(chosen?.description ?? pkg.description ?? ""),
                  tags: asArray<string>(chosen?.tags ?? pkg.tags),
                  hashtags: asArray<string>(chosen?.hashtags ?? pkg.hashtags),
                })}
                label={chosen ? "Copy selected upload package" : "Copy upload package"}
                variant="gradient"
                size="sm"
                disabled={!hasPackage}
              />
              {aiShorts ? (
                <>
                  <Badge variant="brand" title="Written on the AI Shorts page">
                    {aiShorts.label}
                  </Badge>
                  {aiShorts.planId !== null ? (
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/ai-shorts?plan=${aiShorts.planId}`}>
                        <Clapperboard aria-hidden="true" />
                        Open AI Short
                      </Link>
                    </Button>
                  ) : null}
                </>
              ) : null}
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
