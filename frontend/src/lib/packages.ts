import type {
  AnalyzeResponse,
  LanguagePackage,
  PackageOption,
  TitleThumbnailPackage,
} from "@/api/types";
import { asArray, asObject, normalizeTitle } from "./utils";

/**
 * Derivation of the comparable package options shown on the Compare stage.
 *
 * Ported from the legacy `pages/creator.js`. The rules are deliberate and are
 * kept verbatim:
 *  - at most five options, de-duplicated by case-folded title;
 *  - the language-resolved package wins over the top-level fields;
 *  - every option reuses the same description/tags/hashtags, because the API
 *    returns title and thumbnail alternatives, not separate metadata bundles.
 *    Presenting them as independently generated bundles would overstate what
 *    the backend actually produced.
 */

const MAX_OPTIONS = 5;

export function selectedLanguagePackage(
  data: AnalyzeResponse,
  submitted: { language?: string; video_language?: string } = {},
): Required<LanguagePackage> & { language: string } {
  const multilang = (data.multilang ?? {}) as Record<string, LanguagePackage>;
  const requested = String(submitted.language ?? "").toLowerCase();
  const resolved =
    requested === "auto" ? String(submitted.video_language ?? "english").toLowerCase() : requested;

  const key = multilang[resolved]
    ? resolved
    : Object.keys(multilang).find((name) => multilang[name]?.title);
  const pkg: LanguagePackage = key ? (multilang[key] ?? {}) : {};

  return {
    language: key || resolved || "english",
    title: pkg.title || data.title || "",
    description: pkg.description || data.description || "",
    tags: asArray<string>(pkg.tags).length ? asArray<string>(pkg.tags) : asArray<string>(data.tags),
    hashtags: asArray<string>(pkg.hashtags).length
      ? asArray<string>(pkg.hashtags)
      : asArray<string>(data.hashtags),
    variants: asArray<string>(pkg.variants).length
      ? asArray<string>(pkg.variants)
      : asArray<string>(data.title_variants),
  };
}

/** Title-quality score, or null when the backend did not score this title. */
export function titleScore(data: AnalyzeResponse, title: string): number | null {
  const scored = asArray<{ title?: string; score?: number }>(data.title_optimization?.scored_variants);
  const match = scored.find((item) => normalizeTitle(item?.title) === normalizeTitle(title));
  if (match && Number.isFinite(Number(match.score))) return Number(match.score);

  if (normalizeTitle(data.title) === normalizeTitle(title)) {
    const value = data.ctr_prediction?.title_quality_score;
    if (Number.isFinite(Number(value))) return Number(value);
  }
  return null;
}

export function buildPackageOptions(
  data: AnalyzeResponse,
  submitted: { language?: string; video_language?: string } = {},
): PackageOption[] {
  const base = selectedLanguagePackage(data, submitted);
  const brief = asObject(data.creator_brief);
  const rich = asArray<TitleThumbnailPackage>(data.title_thumbnail_packages).map(
    (item) => asObject(item) as TitleThumbnailPackage,
  );
  const richByTitle = new Map(rich.map((item) => [normalizeTitle(item.title), item]));

  const candidates: (TitleThumbnailPackage & { primary?: boolean })[] = [
    { title: base.title, primary: true, ...richByTitle.get(normalizeTitle(base.title)) },
    ...rich,
    ...base.variants.map((title) => ({ title })),
  ];

  const generationLabel = data.generation_source === "gemini" ? "AI suggestion" : "Generated suggestion";
  const seen = new Set<string>();
  const options: PackageOption[] = [];

  for (const candidate of candidates) {
    const title = String(candidate.title ?? "").trim();
    const key = normalizeTitle(title);
    if (!title || seen.has(key) || options.length >= MAX_OPTIONS) continue;
    seen.add(key);

    const index = options.length;
    options.push({
      id: String(candidate.package_id || `package-${String.fromCharCode(97 + index)}`),
      label: `Package ${String.fromCharCode(65 + index)}`,
      primary: Boolean(candidate.primary) || key === normalizeTitle(base.title),
      title,
      description: base.description,
      tags: [...base.tags],
      hashtags: [...base.hashtags],
      language: base.language,
      thumbnailText: String(candidate.thumbnail_text ?? "").trim(),
      thumbnailVisual: String(candidate.thumbnail_visual ?? brief.thumbnail_idea ?? "").trim(),
      viewerPromise: String(candidate.viewer_promise ?? brief.viewer_promise ?? "").trim(),
      whySuggested: String(
        candidate.why_click ??
          (candidate.primary
            ? "This is the primary generated recommendation."
            : "This is a generated title alternative for comparison."),
      ).trim(),
      approach: String(candidate.approach ?? "alternative").trim(),
      packageIntent: String(candidate.package_intent ?? "Alternative").trim(),
      bestFor: String(candidate.best_for ?? "Unavailable").trim(),
      misleadingRisk: String(candidate.misleading_risk ?? "not evaluated").trim(),
      qualityStatus: String(candidate.quality_status ?? "not evaluated").trim(),
      titleQualityScore: titleScore(data, title),
      source: generationLabel,
      mechanism: String(candidate.mechanism ?? candidate.approach ?? "direct topic framing"),
      reason: String(
        candidate.reason ?? candidate.why_click ?? "A source-supported generated alternative.",
      ),
    });
  }

  return options;
}

/** Plain-text bundle for pasting into YouTube Studio. */
export function uploadPackageText(option: PackageOption): string {
  return uploadBundleText({
    title: option.title,
    description: option.description,
    tags: option.tags,
    hashtags: option.hashtags,
  });
}

/**
 * The same bundle built from loose fields, for a saved History record where
 * there is no `PackageOption` — only the stored package dict.
 */
export function uploadBundleText(fields: {
  title?: string;
  description?: string;
  tags?: string[];
  hashtags?: string[];
}): string {
  return [
    "TITLE",
    fields.title ?? "",
    "",
    "DESCRIPTION",
    fields.description ?? "",
    "",
    "TAGS",
    (fields.tags ?? []).join(", "),
    "",
    "HASHTAGS",
    (fields.hashtags ?? []).join(" "),
  ].join("\n");
}

export type CopyField = "title" | "description" | "tags" | "hashtags" | "upload-package";

export function copyValue(option: PackageOption | null, field: CopyField): string {
  if (!option) return "";
  if (field === "tags") return option.tags.join(", ");
  if (field === "hashtags") return option.hashtags.join(" ");
  if (field === "upload-package") return uploadPackageText(option);
  return String(option[field] ?? "");
}

/** Does the payload carry any research evidence at all? */
export function researchHasEvidence(data: AnalyzeResponse | null | undefined): boolean {
  if (!data || typeof data !== "object") return false;
  return Boolean(
    asArray(data.research_queries).length ||
      Object.keys(asObject(data.research_decision)).length ||
      asArray(data.youtube_results).length ||
      asArray(data.top_opportunities).length ||
      asArray(data.keyword_signals).length ||
      asArray(data.entity_signals).length ||
      Object.keys(asObject(data.thumbnail_intelligence)).length,
  );
}
