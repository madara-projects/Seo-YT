import { useId } from "react";
import { AlertTriangle, FileText, Hash, Package, ShieldCheck, Tag, Type, XCircle } from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { CopyButton } from "@/components/common/CopyButton";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { Panel } from "@/components/common/Panel";
import { UnavailableNote } from "@/components/common/States";
import { qualityNotes, titleOptions, verdictChip, verdictSummary } from "@/lib/aiShortsFormat";
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
  labelId,
  count,
  action,
}: {
  icon: React.ElementType;
  label: string;
  labelId?: string;
  count?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
        <span id={labelId} className="text-[0.8125rem] font-medium text-foreground">{label}</span>
        {count ? <Badge variant="neutral" className="numeric">{count}</Badge> : null}
      </div>
      {action}
    </div>
  );
}

/** The quality gate's verdict in plain words, and what it does not measure. */
function QualityCheck({ plan }: { plan: AiShortsPlan }) {
  const quality = plan.package?.generation_quality;
  const verdict = verdictChip(quality?.verdict);
  const issues = qualityNotes(quality?.issues);
  const warnings = qualityNotes(quality?.warnings);

  return (
    <section aria-label="Quality check" className="space-y-2.5 rounded-xl border border-border bg-elevated p-3.5 sm:p-4">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <ShieldCheck className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="text-[0.8125rem] font-medium text-foreground">Quality check</span>
        <EvidenceChip tone={verdict.tone}>{verdict.label}</EvidenceChip>
      </div>
      <p className="text-[0.8125rem] leading-relaxed text-foreground">{verdictSummary(quality?.verdict)}</p>
      {issues.length || warnings.length ? (
        <ul className="space-y-1.5" aria-label="Package quality notes">
          {issues.map((issue, index) => (
            <li key={`issue-${index}`} className="flex gap-2 text-xs leading-relaxed text-foreground">
              <XCircle className="mt-0.5 size-3.5 shrink-0 text-tone-bad" aria-hidden="true" />
              <span className="min-w-0 break-words">{issue}</span>
            </li>
          ))}
          {warnings.map((warning, index) => (
            <li key={`warning-${index}`} className="flex gap-2 text-xs leading-relaxed text-foreground">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-tone-warn" aria-hidden="true" />
              <span className="min-w-0 break-words">{warning}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs leading-relaxed text-muted-foreground">
        Checks assess source fidelity, not predicted views. This package makes no YouTube Data API research (no
        competitor videos or view counts), so the Opportunity Score is unmeasured. Subject tags come from the
        quote&apos;s meaning and are checked against YouTube&apos;s free search suggestions, which show what viewers
        type, not search volume; yt and shorts are format tags.
      </p>
    </section>
  );
}

/**
 * The Short's title, description, hashtags and tags, ready to copy. The
 * chosen title goes into the bundle, which is the same text the Creator and
 * History copy, so YouTube Studio gets one format wherever it came from.
 */
export function ShortsPackage({
  plan,
  chosenTitle,
  onChooseTitle,
}: {
  plan: AiShortsPlan;
  /** Index into the title options; the primary title when out of range. */
  chosenTitle: number;
  onChooseTitle: (index: number) => void;
}) {
  const titlesId = useId();
  const pkg = plan.package;
  const titles = titleOptions(plan);
  const chosen = chosenTitle >= 0 && chosenTitle < titles.length ? chosenTitle : 0;
  const title = titles[chosen] ?? "";
  const description = String(pkg?.description ?? "");
  // Cleaned once, so the tags on screen are exactly the tags that get pasted.
  const tags = cleanTags(pkg?.tags);
  const hashtags = cleanHashtags(pkg?.hashtags);
  const bundle = uploadBundleText({ title, description, tags, hashtags });

  return (
    <Panel
      icon={Package}
      title="Upload package"
      description="Pick a title, then copy the package into YouTube Studio: all at once, or field by field."
      aside={pkg ? <CopyButton value={bundle} label="Copy upload package" variant="gradient" disabled={!title} /> : null}
      className="@container"
      data-testid="shorts-package"
    >
      {!pkg ? (
        <UnavailableNote>No package was returned for this plan.</UnavailableNote>
      ) : (
        <div className="space-y-6">
          <QualityCheck plan={plan} />

          <div className="space-y-2.5">
            <FieldHeader
              icon={Type}
              label="Title options"
              labelId={titlesId}
              count={titles.length ? String(titles.length) : undefined}
            />
            {titles.length ? (
              <div role="radiogroup" aria-labelledby={titlesId}>
                <ul className="space-y-2">
                  {titles.map((option, index) => {
                    const checked = index === chosen;
                    return (
                      <li
                        key={option}
                        className={cn(
                          "flex items-start gap-3 rounded-xl border px-3.5 py-2.5 transition-colors",
                          checked
                            ? "border-brand-border bg-brand-soft/50"
                            : "border-border bg-elevated hover:border-foreground/20",
                        )}
                        data-testid="title-option"
                      >
                        <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                          <input
                            type="radio"
                            name={`ai-shorts-title-${plan.id}`}
                            checked={checked}
                            onChange={() => onChooseTitle(index)}
                            aria-label={index === 0 ? `${option} (primary)` : option}
                            className="mt-1 size-4 shrink-0 cursor-pointer accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                          />
                          <span className="min-w-0 space-y-1">
                            <span className="flex flex-wrap items-center gap-1.5">
                              <Badge variant={index === 0 ? "brand" : "neutral"}>
                                {index === 0 ? "Primary" : `Option ${index + 1}`}
                              </Badge>
                              {checked ? <span className="text-[0.6875rem] font-medium text-brand">In the package</span> : null}
                            </span>
                            <span
                              className={cn(
                                "block break-words leading-snug text-foreground",
                                checked ? "font-display text-base font-semibold" : "text-[0.875rem] font-medium",
                              )}
                            >
                              {option}
                            </span>
                            <span className="numeric block text-[0.6875rem] text-muted-foreground">{option.length} chars</span>
                          </span>
                        </label>
                        <CopyButton
                          value={option}
                          label="Copy"
                          size="xs"
                          className="shrink-0"
                          aria-label={`Copy title: ${option}`}
                        />
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <UnavailableNote>No title was returned.</UnavailableNote>
            )}
          </div>

          <div className="space-y-2.5">
            <FieldHeader
              icon={FileText}
              label="Description"
              count={description ? `${description.length} chars` : undefined}
              action={description ? <CopyButton value={description} label="Copy description" size="xs" /> : null}
            />
            {description ? (
              <p className="select-text whitespace-pre-wrap break-words rounded-xl border border-border bg-elevated p-3.5 text-[0.8125rem] leading-relaxed text-foreground sm:p-4">
                <span className="block max-w-[80ch]">{description}</span>
              </p>
            ) : (
              <UnavailableNote>No description was returned.</UnavailableNote>
            )}
          </div>

          <div className="grid gap-5 @xl:grid-cols-2">
            <div className="min-w-0 space-y-2.5">
              <FieldHeader
                icon={Hash}
                label="Hashtags"
                count={String(hashtags.length)}
                action={hashtags.length ? <CopyButton value={hashtagsText(hashtags)} label="Copy hashtags" size="xs" /> : null}
              />
              <TagList items={hashtags} emptyLabel="No hashtags returned." />
            </div>
            <div className="min-w-0 space-y-2.5">
              <FieldHeader
                icon={Tag}
                label="Video tags"
                count={String(tags.length)}
                action={tags.length ? <CopyButton value={tagsText(tags)} label="Copy tags" size="xs" /> : null}
              />
              <TagList items={tags} emptyLabel="No tags returned." />
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
