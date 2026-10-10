import { AlertTriangle, FileText, Hash, Package, Tag, Type, XCircle } from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { qualityNotes, titleOptions, verdictChip } from "@/lib/aiShortsFormat";
import { cleanHashtags, cleanTags, hashtagsText, tagsText, uploadBundleText } from "@/lib/packages";
import { cn } from "@/lib/utils";
import type { AiShortsPlan } from "@/api/aiShortsTypes";

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (!items.length) return <p className="text-[0.8125rem] text-muted-foreground">{emptyLabel}</p>;
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

/**
 * The Short's title, description, hashtags and tags, ready to copy. The
 * bundle is the same text the Creator and History copy, so YouTube Studio
 * gets one format wherever it came from.
 */
export function ShortsPackage({ plan }: { plan: AiShortsPlan }) {
  const pkg = plan.package;
  const titles = titleOptions(plan);
  const primary = titles[0] ?? "";
  const description = String(pkg?.description ?? "");
  // Cleaned once, so the tags on screen are exactly the tags that get pasted.
  const tags = cleanTags(pkg?.tags);
  const hashtags = cleanHashtags(pkg?.hashtags);
  const verdict = verdictChip(pkg?.generation_quality?.verdict);
  const issues = qualityNotes(pkg?.generation_quality?.issues);
  const warnings = qualityNotes(pkg?.generation_quality?.warnings);
  const bundle = uploadBundleText({ title: primary, description, tags, hashtags });

  return (
    <Panel
      icon={Package}
      title="SEO package"
      description="Copy each field into YouTube Studio, or the whole bundle at once."
      aside={
        <>
          <EvidenceChip tone={verdict.tone}>{verdict.label}</EvidenceChip>
          <CopyButton value={bundle} label="Copy upload package" variant="gradient" disabled={!primary} />
        </>
      }
      data-testid="shorts-package"
    >
      {!pkg ? (
        <UnavailableNote>No package was returned for this plan.</UnavailableNote>
      ) : (
        <div className="space-y-6">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Checks assess source fidelity, not predicted views. This package makes no YouTube Data API research
            (no competitor videos or view counts), so the Opportunity Score is unmeasured. Subject tags come from the
            quote&apos;s meaning and are checked against YouTube&apos;s free search suggestions, which show what viewers
            type, not search volume; yt and shorts are format tags.
          </p>
          {issues.length || warnings.length ? (
            <ul className="space-y-1.5" aria-label="Package quality notes">
              {issues.map((issue, index) => (
                <li
                  key={`issue-${index}`}
                  className="flex gap-2.5 rounded-xl border border-tone-bad-border bg-tone-bad-bg px-3.5 py-2.5 text-xs leading-relaxed text-foreground"
                >
                  <XCircle className="mt-0.5 size-3.5 shrink-0 text-tone-bad" aria-hidden="true" />
                  <span>{issue}</span>
                </li>
              ))}
              {warnings.map((warning, index) => (
                <li
                  key={`warning-${index}`}
                  className="flex gap-2.5 rounded-xl border border-tone-warn-border bg-tone-warn-bg px-3.5 py-2.5 text-xs leading-relaxed text-foreground"
                >
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-tone-warn" aria-hidden="true" />
                  <span>{warning}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="space-y-2.5">
            <FieldHeader icon={Type} label="Title options" count={titles.length ? String(titles.length) : undefined} />
            {titles.length ? (
              <ul className="space-y-2">
                {titles.map((title, index) => (
                  <li
                    key={title}
                    className="flex flex-wrap items-start justify-between gap-2 rounded-xl border border-border bg-elevated px-3.5 py-2.5"
                    data-testid="title-option"
                  >
                    <span className="min-w-0 flex-1 space-y-1">
                      <Badge variant={index === 0 ? "brand" : "neutral"}>{index === 0 ? "Primary" : `Option ${index + 1}`}</Badge>
                      <span
                        className={cn(
                          "block break-words leading-snug text-foreground",
                          index === 0 ? "font-display text-base font-semibold" : "text-[0.8125rem] font-medium",
                        )}
                      >
                        {title}
                      </span>
                      <span className="numeric block text-[0.6875rem] text-muted-foreground">{title.length} chars</span>
                    </span>
                    <CopyButton value={title} label="Copy title" size="xs" aria-label={`Copy title: ${title}`} />
                  </li>
                ))}
              </ul>
            ) : (
              <UnavailableNote>No title was returned.</UnavailableNote>
            )}
          </div>

          <div className="space-y-2.5">
            <FieldHeader
              icon={FileText}
              label="Description"
              count={description ? `${description.length} chars` : undefined}
              action={description ? <CopyButton value={description} label="Copy description" /> : null}
            />
            {description ? (
              <p className="whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-4 text-[0.8125rem] leading-relaxed text-muted-foreground">
                <span className="block max-w-[80ch]">{description}</span>
              </p>
            ) : (
              <UnavailableNote>No description was returned.</UnavailableNote>
            )}
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2.5">
              <FieldHeader
                icon={Hash}
                label="Hashtags"
                count={String(hashtags.length)}
                action={hashtags.length ? <CopyButton value={hashtagsText(hashtags)} label="Copy hashtags" /> : null}
              />
              <TagList items={hashtags} emptyLabel="No hashtags returned." />
            </div>
            <div className="space-y-2.5">
              <FieldHeader
                icon={Tag}
                label="Video tags"
                count={String(tags.length)}
                action={tags.length ? <CopyButton value={tagsText(tags)} label="Copy tags" /> : null}
              />
              <TagList items={tags} emptyLabel="No tags returned." />
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
