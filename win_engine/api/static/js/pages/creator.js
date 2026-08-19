import { apiRequest } from "../api.js";
import { formatApiError } from "../errors.js";
import { creatorState } from "../state.js";
import { arr, esc, num } from "../utils.js";

const STAGES = [
  { key: "idea", label: "Stage 1 / Idea", hint: "Start with the script, topic, or raw video idea." },
  { key: "brief", label: "Stage 2 / Creator Brief", hint: "Confirm the audience, promise, angle, format, and thumbnail direction." },
  { key: "research", label: "Stage 3 / Research", hint: "Review returned public observations, local heuristics, and unavailable evidence." },
  { key: "angle", label: "Stage 4 / Recommended Angle", hint: "Review the suggested angle and the limited evidence behind it." },
  { key: "packaging", label: "Stage 5 / Packaging", hint: "Review and copy the generated metadata package." },
  { key: "compare", label: "Stage 6 / Compare", hint: "Compare title and thumbnail approaches, then choose one locally." },
  { key: "decision", label: "Stage 7 / Decision", hint: "Confirm what you selected, why it was suggested, and what remains unknown." },
  { key: "checklist", label: "Stage 8 / Checklist", hint: "Complete manual checks before publishing outside this tool." },
];

const FORM_FIELDS = [
  "script", "video_language", "language", "region", "target_audience",
  "viewer_promise", "unique_angle", "proof", "video_format", "title_style",
  "thumbnail_idea",
];

const PROVENANCE_FIELDS = [
  ["target_audience", "Target audience"],
  ["viewer_promise", "Viewer promise"],
  ["unique_angle", "Unique angle"],
  ["proof", "Proof / footage"],
  ["video_format", "Video format"],
  ["title_style", "Title style"],
  ["thumbnail_idea", "Thumbnail direction"],
];

const CHECKLIST_ITEMS = [
  { key: "title", source: "Generated suggestion", label: "The selected title accurately matches the finished video." },
  { key: "description", source: "Generated suggestion", label: "The description is factual, readable, and contains no unsupported promise." },
  { key: "tags", source: "Generated suggestion", label: "Every tag is relevant; required Shorts tags are included only for Shorts." },
  { key: "hashtags", source: "Generated suggestion", label: "The hashtags describe this exact video and are not presented as a growth guarantee." },
  { key: "thumbnail", source: "Manual check", label: "The final thumbnail or Short cover matches the selected direction and remains readable." },
  { key: "promise", source: "Creator-confirmed", label: "The opening seconds deliver the viewer promise shown in this package." },
  { key: "claims", source: "Manual check", label: "I reviewed names, facts, rights, spelling, and misleading or guaranteed-performance claims." },
  { key: "manualPublish", source: "Creator-confirmed", label: "I understand this tool does not upload, publish, or guarantee views, CTR, reach, or growth." },
];

const TEMPLATE_TEXT = {
  tech: "How to build a full YouTube SEO automation app in Python and Tamil using Gemini AI and FastAPI.",
  quote: "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
  growth: "How I grew my YouTube channel from 0 to 10,000 subscribers in 30 days using stronger title and topic choices.",
  review: "Top 5 AI productivity tools in 2026 that will improve coding and video creation workflows.",
};

let callbacks = {};

function freshChecklist() {
  return Object.fromEntries(CHECKLIST_ITEMS.map((item) => [item.key, false]));
}

function objectOf(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function listOf(value) {
  return Array.isArray(value) ? value : [];
}

function valueFor(root, id) {
  const node = root.getElementById(id === "script" ? "scriptInput" : id);
  return node ? String(node.value || "").trim() : "";
}

function readCreatorForm(root) {
  const values = {};
  FORM_FIELDS.forEach((field) => { values[field] = valueFor(root, field); });
  return values;
}

function writeCreatorForm(root, values = {}) {
  FORM_FIELDS.forEach((field) => {
    const node = root.getElementById(field === "script" ? "scriptInput" : field);
    if (node && Object.prototype.hasOwnProperty.call(values, field)) node.value = values[field] || "";
  });
}

function syncFormState(root) {
  creatorState.formValues = readCreatorForm(root);
  return creatorState.formValues;
}

function displayValue(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") return fallback;
  return esc(value);
}

function sourceChip(label, tone = "") {
  return `<span class="chip ${tone ? `chip-${tone}` : ""}">${esc(label)}</span>`;
}

function emptyState(message) {
  return `<div class="creator-empty-state">${esc(message)}</div>`;
}

function renderStage(root, stageKey = creatorState.stage) {
  const stage = STAGES.find((item) => item.key === stageKey) || STAGES[0];
  creatorState.stage = stage.key;
  const shell = root.getElementById("creatorWorkflow");
  if (shell) shell.dataset.stage = stage.key;
  root.querySelectorAll("[data-creator-stage]").forEach((button) => {
    const active = button.dataset.creatorStage === stage.key;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  root.querySelectorAll("[data-creator-panel]").forEach((panel) => {
    const stages = String(panel.dataset.creatorPanel || "").split(/\s+/).filter(Boolean);
    const visible = stages.includes(stage.key);
    panel.classList.toggle("hidden", !visible);
    panel.setAttribute("aria-hidden", String(!visible));
  });
  const status = root.getElementById("creatorStageStatus");
  if (status) status.textContent = stage.label;
  const hint = root.getElementById("creatorWorkflowHint");
  if (hint) hint.textContent = stage.hint;
  const index = STAGES.findIndex((item) => item.key === stage.key);
  const back = root.getElementById("creatorBack");
  const next = root.getElementById("creatorNext");
  if (back) back.disabled = index <= 0;
  if (next) next.disabled = index >= STAGES.length - 1;
  renderResearchPanel(root);
}

function renderBriefProvenance(root, brief, submitted = {}) {
  const panel = root.getElementById("creatorBriefProvenance");
  if (!panel) return;
  if (!brief || typeof brief !== "object") {
    panel.innerHTML = "";
    panel.classList.add("hidden");
    return;
  }
  const rows = PROVENANCE_FIELDS.map(([field, label]) => {
    const value = String(brief[field] || submitted[field] || "").trim();
    if (!value) return "";
    const entered = Boolean(String(submitted[field] || "").trim());
    return `<div class="creator-provenance-row"><span><strong>${esc(label)}</strong><span class="creator-provenance-value">${esc(value)}</span></span>${sourceChip(entered ? "Creator-entered" : "Inferred", entered ? "ok" : "warn")}</div>`;
  }).filter(Boolean).join("");
  if (!rows) {
    panel.innerHTML = "";
    panel.classList.add("hidden");
    return;
  }
  panel.innerHTML = `<div class="card-title"><span>Creator brief provenance</span>${sourceChip("Explicit vs inferred", "accent")}</div><div class="creator-provenance-list">${rows}</div><p class="metric-sub">Inferred values are analysis suggestions. Review them before publishing; they never overwrite what you entered.</p>`;
  panel.classList.remove("hidden");
}

function researchHasEvidence(data) {
  if (!data || typeof data !== "object") return false;
  return Boolean(
    listOf(data.research_queries).length ||
    Object.keys(objectOf(data.research_decision)).length ||
    listOf(data.youtube_results).length ||
    listOf(data.top_opportunities).length ||
    listOf(data.keyword_signals).length ||
    listOf(data.entity_signals).length ||
    Object.keys(objectOf(data.thumbnail_intelligence)).length
  );
}

function researchStatusText(status) {
  return {
    loading: "Loading",
    available: "Available",
    "no-research": "No research available",
    unavailable: "Unavailable",
    error: "API error",
  }[status] || "Unavailable";
}

function researchEmpty(message = "Unavailable - this field was not returned by the analysis pipeline.") {
  return `<div class="creator-research-empty">${esc(message)}</div>`;
}

function renderResearchDecision(decision) {
  if (!Object.keys(decision).length) return researchEmpty();
  const repeated = listOf(decision.repeated_title_patterns).map((item) => {
    const row = objectOf(item);
    return `<div class="creator-research-item"><strong>${displayValue(row.pattern)}</strong><div class="creator-research-meta">Observed in ${displayValue(row.count, "an unavailable number of")} returned public result titles.</div></div>`;
  }).join("");
  const avoid = listOf(decision.avoid).map((item) => `<div class="creator-research-item">${displayValue(item)}</div>`).join("");
  const outliers = listOf(decision.small_channel_winners).map((item) => {
    const row = objectOf(item);
    return `<div class="creator-research-item"><strong>${displayValue(row.title)}</strong><div class="creator-research-meta">Public channel observation: ${displayValue(row.channel)} / Views reported by YouTube: ${displayValue(row.views)}</div></div>`;
  }).join("");
  return `
    <div class="creator-research-item"><strong>Recommended angle</strong><div class="creator-research-meta">${displayValue(decision.recommended_angle)}</div></div>
    <div class="creator-research-item"><strong>Reasoning</strong><div class="creator-research-meta">${displayValue(decision.reason)}</div></div>
    <div class="creator-research-item"><strong>Synthesis confidence</strong><div class="creator-research-meta">${displayValue(decision.confidence)} / ${sourceChip("Local heuristic", "warn")}</div></div>
    <div class="creator-research-item"><strong>Dominant public title pattern</strong><div class="creator-research-meta">${displayValue(decision.dominant_competitor_pattern)} / ${sourceChip("Public observation", "accent")}</div></div>
    <div class="creator-research-list">${repeated || researchEmpty("No repeated title pattern was returned.")}</div>
    <div class="creator-research-list">${outliers || researchEmpty("No small-channel outlier observation was returned.")}</div>
    <div class="creator-research-list">${avoid || researchEmpty("No avoidance guidance was returned.")}</div>`;
}

function renderPublicResults(results) {
  if (!results.length) return researchEmpty("No public YouTube results were returned for this analysis.");
  const rows = results.slice(0, 8).map((item) => {
    const row = objectOf(item);
    return `<tr><td><strong>${displayValue(row.title)}</strong><div class="creator-research-meta">${displayValue(row.channel_title)}</div></td><td>${displayValue(row.published_at)}</td><td>${displayValue(row.view_count)}</td><td>${displayValue(row.outlier_score)}<div class="creator-research-meta">Local heuristic</div></td></tr>`;
  }).join("");
  return `<div class="creator-table-scroll"><table class="creator-research-table"><thead><tr><th>Public result</th><th>Published</th><th>Views</th><th>Outlier score</th></tr></thead><tbody>${rows}</tbody></table></div><p class="metric-sub">These are public observations returned by YouTube research. They do not prove causation, ranking, or future performance.</p>`;
}

function renderTopOpportunities(items) {
  if (!items.length) return researchEmpty("No local scoring candidates were returned.");
  return items.slice(0, 3).map((item) => {
    const row = objectOf(item);
    const reasons = listOf(row.opportunity_reasons).join("; ");
    return `<div class="creator-research-item"><strong>${displayValue(row.title)}</strong><div class="creator-research-meta">Local heuristic score: ${displayValue(row.outlier_score)} / ${displayValue(reasons, "No reason returned")}</div></div>`;
  }).join("");
}

function renderSignals(items, type) {
  if (!items.length) return researchEmpty(`No ${type} signals were returned.`);
  return items.slice(0, 10).map((item) => {
    const row = objectOf(item);
    const label = type === "keyword" ? row.keyword : row.entity;
    const meta = type === "keyword"
      ? `Mentions in analyzed text/results: ${displayValue(row.mentions)} / Strength: ${displayValue(row.strength)}`
      : `Type: ${displayValue(row.type)} / Mentions: ${displayValue(row.mentions)}`;
    return `<div class="creator-research-item"><strong>${displayValue(label)}</strong><div class="creator-research-meta">${meta} / ${sourceChip("Local heuristic", "warn")}</div></div>`;
  }).join("");
}

function renderThumbnailContext(intelligence) {
  if (!Object.keys(intelligence).length) return researchEmpty("No thumbnail metadata was returned.");
  const counts = objectOf(intelligence.quality_counts);
  return `<div class="creator-research-item"><strong>Available thumbnail metadata</strong><div class="creator-research-meta">Max resolution: ${displayValue(counts.maxres)} / High: ${displayValue(counts.high)} / Medium: ${displayValue(counts.medium)} / Default: ${displayValue(counts.default)}</div></div><div class="creator-research-item"><strong>Low-resolution observations</strong><div class="creator-research-meta">${displayValue(intelligence.low_resolution_count)} / ${sourceChip("Public observation", "accent")}</div></div><div class="creator-research-item"><strong>Local setup suggestion</strong><div class="creator-research-meta">${displayValue(intelligence.recommendation)} / ${sourceChip("Local heuristic", "warn")}</div></div>`;
}

function renderResearchPanel(root) {
  const panel = root.getElementById("creatorResearchPanel");
  if (!panel) return;
  const status = creatorState.researchStatus || "no-research";
  const statusClass = status === "available" ? "available" : status === "loading" ? "loading" : status === "error" ? "error" : "";
  const statusMessage = {
    loading: "The existing Analyze request is loading. Opening this stage never starts a separate research request.",
    available: "Research returned by the existing analysis pipeline is shown with source and limitation labels.",
    "no-research": "Run Analyze first. Stage navigation never calls YouTube, Gemini, OAuth, or another research endpoint.",
    unavailable: "The analysis completed, but no research evidence was returned. No substitute score or competitor claim is shown.",
    error: creatorState.researchError || "The Analyze API returned an error; research is unavailable for this run.",
  }[status] || "Research status unavailable.";
  const data = creatorState.analysis || {};
  const decision = objectOf(data.research_decision);
  const warnings = listOf(data.research_warnings);
  const generationSource = data.generation_source === "gemini" ? "AI suggestion / Google Gemini" : data.generation_source === "fallback" ? "Generated suggestion / local fallback" : "Unavailable";
  let content = `<div class="creator-research-status ${statusClass}"><strong>${esc(researchStatusText(status))}</strong><div class="metric-sub">${esc(statusMessage)}</div></div>`;
  if (status === "available") {
    content += `<div class="creator-research-grid">
      <div class="creator-research-card wide"><div class="card-title"><span>Research synthesis</span>${sourceChip("Local heuristic", "warn")}</div>${renderResearchDecision(decision)}</div>
      <div class="creator-research-card wide"><div class="card-title"><span>Executed research queries</span>${sourceChip("Public research context", "accent")}</div>${listOf(data.research_queries).length ? `<div class="creator-research-list">${listOf(data.research_queries).map((item) => `<div class="creator-research-item"><strong>${displayValue(objectOf(item).type)}</strong><div class="creator-research-meta">${displayValue(objectOf(item).query)}</div></div>`).join("")}</div>` : researchEmpty("No research queries were returned.")}</div>
      <div class="creator-research-card wide"><div class="card-title"><span>Public YouTube observations</span>${sourceChip("Public observation", "accent")}</div>${renderPublicResults(listOf(data.youtube_results))}</div>
      <div class="creator-research-card"><div class="card-title"><span>Local scoring candidates</span>${sourceChip("Local heuristic", "warn")}</div>${renderTopOpportunities(listOf(data.top_opportunities))}</div>
      <div class="creator-research-card"><div class="card-title"><span>Keyword signals</span>${sourceChip("Local heuristic", "warn")}</div>${renderSignals(listOf(data.keyword_signals), "keyword")}</div>
      <div class="creator-research-card"><div class="card-title"><span>Entity signals</span>${sourceChip("Local heuristic", "warn")}</div>${renderSignals(listOf(data.entity_signals), "entity")}</div>
      <div class="creator-research-card"><div class="card-title"><span>Thumbnail research context</span>${sourceChip("Public metadata", "accent")}</div>${renderThumbnailContext(objectOf(data.thumbnail_intelligence))}</div>
      <div class="creator-research-card"><div class="card-title"><span>Generation context</span>${sourceChip(generationSource, data.generation_source === "gemini" ? "accent" : "warn")}</div><div class="creator-research-list"><div class="creator-research-item"><strong>Intent</strong><div class="creator-research-meta">${displayValue(data.intent)} / Local heuristic</div></div><div class="creator-research-item"><strong>Content angle</strong><div class="creator-research-meta">${displayValue(data.content_angle)} / Generated suggestion</div></div><div class="creator-research-item"><strong>Cache policy</strong><div class="creator-research-meta">${displayValue(data.cache_policy)} / Technical context, not evidence quality</div></div></div></div>
      <div class="creator-research-card wide"><div class="card-title"><span>Research warnings and limits</span>${sourceChip(warnings.length ? "Review required" : "No warnings returned", warnings.length ? "warn" : "ok")}</div>${warnings.length ? `<div class="creator-research-list">${warnings.map((warning) => `<div class="creator-research-item">${displayValue(warning)}</div>`).join("")}</div>` : researchEmpty("No research warning was returned; absence of a warning is not proof of quality or causation.")}</div>
    </div>`;
  } else {
    content += researchEmpty(status === "error" ? "No fallback research is fabricated after an API error." : "Only fields returned by the analysis pipeline will appear here.");
  }
  panel.innerHTML = `<div class="card-title"><span>Research and provenance</span>${sourceChip(researchStatusText(status), status === "available" ? "ok" : status === "error" ? "bad" : "warn")}</div>${content}`;
}

function selectedLanguagePackage(data) {
  const multilang = objectOf(data.multilang);
  const requested = String((creatorState.submittedFormValues || {}).language || "").toLowerCase();
  const resolved = requested === "auto"
    ? String((creatorState.submittedFormValues || {}).video_language || "english").toLowerCase()
    : requested;
  const key = multilang[resolved] ? resolved : Object.keys(multilang).find((name) => objectOf(multilang[name]).title);
  const pkg = key ? objectOf(multilang[key]) : {};
  return {
    language: key || resolved || "english",
    title: pkg.title || data.title || "",
    description: pkg.description || data.description || "",
    tags: arr(pkg.tags).length ? arr(pkg.tags) : arr(data.tags),
    hashtags: arr(pkg.hashtags).length ? arr(pkg.hashtags) : arr(data.hashtags),
    variants: arr(pkg.variants).length ? arr(pkg.variants) : arr(data.title_variants),
  };
}

function normalizedTitle(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

function titleScore(data, title) {
  const scored = listOf(objectOf(data.title_optimization).scored_variants);
  const match = scored.find((item) => normalizedTitle(objectOf(item).title) === normalizedTitle(title));
  if (match && Number.isFinite(Number(match.score))) return Number(match.score);
  if (normalizedTitle(data.title) === normalizedTitle(title)) {
    const value = objectOf(data.ctr_prediction).title_quality_score;
    if (Number.isFinite(Number(value))) return Number(value);
  }
  return null;
}

function buildPackageOptions(data) {
  const base = selectedLanguagePackage(data);
  const brief = objectOf(data.creator_brief);
  const richPackages = listOf(data.title_thumbnail_packages).map(objectOf);
  const richByTitle = new Map(richPackages.map((item) => [normalizedTitle(item.title), item]));
  const candidates = [
    { title: base.title, primary: true, ...richByTitle.get(normalizedTitle(base.title)) },
    ...richPackages,
    ...base.variants.map((title) => ({ title })),
  ];
  const seen = new Set();
  const generationLabel = data.generation_source === "gemini" ? "AI suggestion" : "Generated suggestion";
  const options = [];
  candidates.forEach((candidate) => {
    const title = String(candidate.title || "").trim();
    const key = normalizedTitle(title);
    if (!title || seen.has(key) || options.length >= 5) return;
    seen.add(key);
    const index = options.length;
    options.push({
      id: `package-${String.fromCharCode(97 + index)}`,
      label: `Package ${String.fromCharCode(65 + index)}`,
      primary: Boolean(candidate.primary) || key === normalizedTitle(base.title),
      title,
      description: base.description,
      tags: [...base.tags],
      hashtags: [...base.hashtags],
      language: base.language,
      thumbnailText: String(candidate.thumbnail_text || "").trim(),
      thumbnailVisual: String(candidate.thumbnail_visual || brief.thumbnail_idea || "").trim(),
      viewerPromise: String(candidate.viewer_promise || brief.viewer_promise || "").trim(),
      whySuggested: String(candidate.why_click || (candidate.primary ? "This is the primary generated recommendation." : "This is a generated title alternative for comparison.")).trim(),
      approach: String(candidate.approach || "alternative").trim(),
      packageIntent: String(candidate.package_intent || "Alternative").trim(),
      bestFor: String(candidate.best_for || "Unavailable").trim(),
      misleadingRisk: String(candidate.misleading_risk || "not evaluated").trim(),
      qualityStatus: String(candidate.quality_status || "not evaluated").trim(),
      titleQualityScore: titleScore(data, title),
      source: generationLabel,
    });
  });
  return options;
}

function selectedPackage() {
  return creatorState.packageOptions.find((option) => option.id === creatorState.selectedPackageId) || creatorState.packageOptions[0] || null;
}

function tagsHtml(items, emptyMessage) {
  if (!items.length) return `<span class="metric-sub">${esc(emptyMessage)}</span>`;
  return items.map((item) => `<span class="tag-item">${esc(item)}</span>`).join("");
}

function copyButton(field, packageId, label) {
  return `<button type="button" class="btn creator-copy-btn" data-copy-field="${esc(field)}" data-copy-package-id="${esc(packageId)}">${esc(label)}</button>`;
}

function renderAnglePanel(root) {
  const panel = root.getElementById("creatorAnglePanel");
  if (!panel) return;
  const data = creatorState.analysis;
  if (!data) {
    panel.innerHTML = `<div class="card-title"><span>Recommended angle</span>${sourceChip("Unavailable", "warn")}</div>${emptyState("Run Analyze to review the recommended angle and its provenance.")}`;
    return;
  }
  const decision = objectOf(data.research_decision);
  const brief = objectOf(data.creator_brief);
  const submitted = creatorState.submittedFormValues || {};
  const enteredAngle = Boolean(String(submitted.unique_angle || "").trim());
  const publicCount = listOf(data.youtube_results).length;
  panel.innerHTML = `<div class="card-title"><span>Recommended angle and context</span>${sourceChip("Review before use", "warn")}</div>
    <div class="creator-analysis-grid">
      <div class="creator-analysis-card"><div class="creator-card-heading">Engine content angle ${sourceChip("Local heuristic", "warn")}</div><p>${displayValue(data.content_angle)}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Research synthesis ${sourceChip("Local heuristic", "warn")}</div><p>${displayValue(decision.recommended_angle)}</p><p class="metric-sub">${displayValue(decision.reason, "No research reasoning was returned.")}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Creator brief angle ${sourceChip(enteredAngle ? "Creator-entered" : "Inferred", enteredAngle ? "ok" : "warn")}</div><p>${displayValue(brief.unique_angle)}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Public context ${sourceChip(publicCount ? "Public observation" : "Unavailable", publicCount ? "accent" : "warn")}</div><p>${publicCount ? `${num(publicCount)} public result${publicCount === 1 ? " was" : "s were"} returned for context. This does not prove why a video performed.` : "No public result was returned for this run."}</p></div>
    </div>`;
}

function renderPackagingPanel(root) {
  const panel = root.getElementById("outputContent");
  const results = root.getElementById("resultsPanel");
  if (!panel || !results) return;
  const data = creatorState.analysis;
  if (!data) {
    panel.innerHTML = `<div class="card-title"><span>Generated package</span>${sourceChip("Unavailable", "warn")}</div>${emptyState("Run Analyze to generate title, description, tags, hashtags, and comparison options.")}`;
    return;
  }
  const choice = selectedPackage();
  if (!choice) {
    panel.innerHTML = emptyState("The analysis returned no usable package option.");
    return;
  }
  const opportunity = objectOf(objectOf(data.opportunity_gap_analysis).opportunity_score);
  const score = choice.titleQualityScore;
  const variants = creatorState.packageOptions.map((option) => `
    <div class="creator-variant-row ${option.id === choice.id ? "selected" : ""}">
      <div><strong>${esc(option.label)}${option.primary ? " / Primary recommendation" : ""}</strong><div>${esc(option.title)}</div></div>
      <div class="creator-inline-actions">${copyButton("title", option.id, "Copy title")}<button type="button" class="btn creator-select-btn" data-select-package="${esc(option.id)}">${option.id === choice.id ? "Selected" : "Select"}</button></div>
    </div>`).join("");
  panel.innerHTML = `<div class="card-title"><span>Generated SEO package</span>${sourceChip(choice.source, data.generation_source === "gemini" ? "accent" : "warn")}</div>
    <div class="creator-score-grid">
      <div class="creator-score-card"><span>Opportunity score</span><strong>${displayValue(opportunity.score)} / 100</strong><small>Local heuristic, not a performance guarantee.</small></div>
      <div class="creator-score-card"><span>Selected title quality</span><strong>${score === null ? "Unavailable" : `${num(score)} / 10`}</strong><small>Local title-quality heuristic, not measured CTR.</small></div>
      <div class="creator-score-card"><span>Selection</span><strong>${esc(choice.label)}</strong><small>Local choice only; not persisted or published.</small></div>
    </div>
    <div class="creator-analysis-grid creator-package-fields">
      <div class="creator-analysis-card wide"><div class="creator-card-heading"><span>Selected title</span>${copyButton("title", choice.id, "Copy title")}</div><p class="creator-output-title">${esc(choice.title)}</p></div>
      <div class="creator-analysis-card wide"><div class="creator-card-heading"><span>Description</span>${copyButton("description", choice.id, "Copy description")}</div><div class="creator-output-text">${esc(choice.description)}</div></div>
      <div class="creator-analysis-card"><div class="creator-card-heading"><span>Video tags</span>${copyButton("tags", choice.id, "Copy tags")}</div><div class="tag-list">${tagsHtml(choice.tags, "No tags returned.")}</div></div>
      <div class="creator-analysis-card"><div class="creator-card-heading"><span>Hashtags</span>${copyButton("hashtags", choice.id, "Copy hashtags")}</div><div class="tag-list">${tagsHtml(choice.hashtags, "No hashtags returned.")}</div></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Thumbnail direction ${sourceChip("Generated suggestion", "warn")}</div><p>${displayValue(choice.thumbnailVisual)}</p><p class="metric-sub">Suggested text: ${displayValue(choice.thumbnailText)}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Viewer promise ${sourceChip("Generated suggestion", "warn")}</div><p>${displayValue(choice.viewerPromise)}</p></div>
    </div>
    <div class="creator-section-heading">Title alternatives</div><div class="creator-variant-list">${variants}</div>
    <p class="metric-sub">All choices reuse the generated description, tags, and hashtags because the current API returns title/thumbnail alternatives, not separately generated metadata bundles.</p>`;
}

function renderComparePanel(root) {
  const panel = root.getElementById("creatorComparePanel");
  if (!panel) return;
  if (!creatorState.analysis || !creatorState.packageOptions.length) {
    panel.innerHTML = `<div class="card-title"><span>Compare packages</span>${sourceChip("Unavailable", "warn")}</div>${emptyState("Run Analyze to create comparable package options.")}`;
    return;
  }
  const cards = creatorState.packageOptions.map((option) => {
    const selected = option.id === creatorState.selectedPackageId;
    return `<article class="creator-package-card ${selected ? "selected" : ""}" data-testid="package-option-card" data-package-id="${esc(option.id)}">
      <div class="creator-package-card-head"><div><span class="creator-package-label">${esc(option.label)}</span>${option.primary ? sourceChip("Primary generated recommendation", "accent") : ""}</div>${sourceChip(option.source, option.source === "AI suggestion" ? "accent" : "warn")}</div>
      <h3>${esc(option.title)}</h3>
      <div class="creator-package-facts">
        <div><span>Title quality</span><strong>${option.titleQualityScore === null ? "Unavailable" : `${num(option.titleQualityScore)} / 10`}</strong><small>Local heuristic</small></div>
        <div><span>Approach</span><strong>${esc(option.approach)}</strong><small>Generated suggestion</small></div>
        <div><span>Package intent</span><strong>${esc(option.packageIntent)}</strong><small>Generated suggestion</small></div>
        <div><span>Best for</span><strong>${esc(option.bestFor)}</strong><small>Generated suggestion</small></div>
      </div>
      <div class="creator-package-note"><strong>Why suggested</strong><p>${esc(option.whySuggested)}</p></div>
      <div class="creator-package-note"><strong>Thumbnail direction</strong><p>${displayValue(option.thumbnailVisual)}${option.thumbnailText ? ` / Text: ${esc(option.thumbnailText)}` : ""}</p></div>
      <div class="creator-package-limit">Misleading-risk check: ${esc(option.misleadingRisk)}. This is a generated/local assessment and must be manually reviewed.</div>
      <div class="creator-inline-actions"><button type="button" class="btn creator-copy-btn" data-copy-field="title" data-copy-package-id="${esc(option.id)}">Copy title</button><button type="button" class="btn ${selected ? "btn-primary" : ""} creator-select-btn" data-select-package="${esc(option.id)}" data-testid="select-${esc(option.id)}" aria-pressed="${selected}">${selected ? "Selected locally" : `Select ${esc(option.label)}`}</button></div>
    </article>`;
  }).join("");
  panel.innerHTML = `<div class="card-title"><span>Compare title and thumbnail approaches</span>${sourceChip("Selection is local", "ok")}</div><p class="metric-sub creator-panel-intro">Scores and best-for labels are local heuristics or generated suggestions. They are not measured CTR, reach, or performance predictions.</p><div class="creator-package-grid">${cards}</div>`;
}

function renderDecisionPanel(root) {
  const panel = root.getElementById("creatorDecisionPanel");
  if (!panel) return;
  const data = creatorState.analysis;
  const choice = selectedPackage();
  if (!data || !choice) {
    panel.innerHTML = `<div class="card-title"><span>Final decision</span>${sourceChip("Unavailable", "warn")}</div>${emptyState("Run Analyze and select a package before reviewing the final decision.")}`;
    return;
  }
  const publicCount = listOf(data.youtube_results).length;
  const opportunity = objectOf(objectOf(data.opportunity_gap_analysis).opportunity_score);
  panel.innerHTML = `<div class="card-title"><span>Final local decision</span>${sourceChip("Not published", "warn")}</div>
    <div class="creator-decision-hero"><span>${esc(choice.label)} selected locally</span><h3>${esc(choice.title)}</h3><p>This choice remains in this browser session. It does not change the saved History record or any YouTube video.</p></div>
    <div class="creator-analysis-grid">
      <div class="creator-analysis-card"><div class="creator-card-heading">Why it was suggested ${sourceChip(choice.source, choice.source === "AI suggestion" ? "accent" : "warn")}</div><p>${esc(choice.whySuggested)}</p><p class="metric-sub">Approach: ${esc(choice.approach)} / Intended use: ${esc(choice.bestFor)}</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Public context ${sourceChip(publicCount ? "Public observation" : "Unavailable", publicCount ? "accent" : "warn")}</div><p>${publicCount ? `${num(publicCount)} public YouTube result${publicCount === 1 ? " was" : "s were"} returned as context.` : "No public YouTube result was returned."}</p><p class="metric-sub">Public counts and patterns do not prove why another video performed.</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Pre-publication scoring ${sourceChip("Local heuristic", "warn")}</div><p>Opportunity: ${displayValue(opportunity.score)} / 100. Title quality: ${choice.titleQualityScore === null ? "Unavailable" : `${num(choice.titleQualityScore)} / 10`}.</p><p class="metric-sub">These scores help compare packaging. They do not predict actual CTR, views, reach, or growth.</p></div>
      <div class="creator-analysis-card"><div class="creator-card-heading">Unavailable before publishing ${sourceChip("Unavailable", "warn")}</div><p>Actual impressions, CTR, retention, views, and causal performance evidence are unavailable for this package.</p><p class="metric-sub">Link the published video in History and collect mature comparable snapshots before learning from results.</p></div>
    </div>
    <div class="creator-source-legend"><strong>Source guide</strong>${sourceChip("Creator-entered", "ok")}${sourceChip("Inferred", "warn")}${sourceChip("Public observation", "accent")}${sourceChip("Local heuristic", "warn")}${sourceChip(choice.source, choice.source === "AI suggestion" ? "accent" : "warn")}${sourceChip("Unavailable", "warn")}</div>
    <div class="creator-inline-actions creator-decision-actions">${copyButton("upload-package", choice.id, "Copy selected upload package")}<button type="button" class="btn" id="decisionExportBtn">Export full analysis and local decision</button></div>`;
}

function renderChecklistPanel(root) {
  const panel = root.getElementById("creatorChecklistPanel");
  if (!panel) return;
  const choice = selectedPackage();
  if (!creatorState.analysis || !choice) {
    panel.innerHTML = `<div class="card-title"><span>Pre-publish checklist</span>${sourceChip("Unavailable", "warn")}</div>${emptyState("Run Analyze and select a package before completing manual upload checks.")}`;
    return;
  }
  const checklist = creatorState.checklist || freshChecklist();
  const completed = CHECKLIST_ITEMS.filter((item) => Boolean(checklist[item.key])).length;
  const rows = CHECKLIST_ITEMS.map((item) => `<label class="creator-checklist-item"><input type="checkbox" data-checklist-key="${esc(item.key)}" ${checklist[item.key] ? "checked" : ""}/><span><strong>${esc(item.label)}</strong><small>${esc(item.source)}. Checking this is your acknowledgment, not an automated YouTube validation.</small></span></label>`).join("");
  panel.innerHTML = `<div class="card-title"><span>Manual pre-publish checklist</span>${sourceChip(`${completed} / ${CHECKLIST_ITEMS.length} confirmed`, completed === CHECKLIST_ITEMS.length ? "ok" : "warn")}</div>
    <div class="creator-checklist-summary"><strong>Selected: ${esc(choice.label)}</strong><span>${esc(choice.title)}</span><p>Changing the selected package resets these acknowledgments so the new choice is reviewed.</p></div>
    <div class="creator-checklist-list">${rows}</div>
    <div class="creator-checklist-footer ${completed === CHECKLIST_ITEMS.length ? "complete" : ""}"><strong>${completed === CHECKLIST_ITEMS.length ? "Manual review completed" : "Manual review still required"}</strong><span>${completed === CHECKLIST_ITEMS.length ? "You can copy the package and publish manually in YouTube Studio. Performance is still not guaranteed." : "Confirm every item before using this package in YouTube Studio."}</span></div>
    <div class="creator-inline-actions creator-decision-actions">${copyButton("upload-package", choice.id, "Copy selected upload package")}<button type="button" class="btn" id="checklistExportBtn">Export full analysis and local decision</button></div>`;
}

function renderAnalysisPanels(root) {
  renderAnglePanel(root);
  renderPackagingPanel(root);
  renderComparePanel(root);
  renderDecisionPanel(root);
  renderChecklistPanel(root);
}

function renderAlert(root, kind = "", messages = []) {
  const shell = root.getElementById("creatorStatusPanel");
  const alertBox = root.getElementById("alertBox");
  if (!shell || !alertBox) return;
  const clean = listOf(messages).map((item) => String(item || "").trim()).filter(Boolean);
  shell.classList.toggle("hidden", clean.length === 0);
  if (!clean.length) {
    alertBox.innerHTML = "";
    return;
  }
  const className = kind === "error" ? "alert-err" : kind === "success" ? "alert-ok" : "alert-warn";
  alertBox.innerHTML = `<div class="alert-banner ${className}"><div>${clean.map(esc).join("<br>")}</div></div>`;
}

function setAnalyzeBusy(root, busy) {
  const button = root.getElementById("analyzeBtn");
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.innerHTML;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.innerHTML = `<span class="spin"></span> Analyzing and packaging...`;
  } else {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.innerHTML = button.dataset.originalLabel || "Generate SEO Package";
  }
}

function resetGeneratedState(root) {
  creatorState.analysis = null;
  creatorState.generatedPackage = null;
  creatorState.inferredBrief = null;
  creatorState.packageOptions = [];
  creatorState.selectedPackageId = null;
  creatorState.checklist = freshChecklist();
  creatorState.error = null;
  creatorState.researchError = null;
  const exportButton = root.getElementById("exportBtn");
  if (exportButton) exportButton.disabled = true;
  renderBriefProvenance(root, null);
  renderAnalysisPanels(root);
}

async function submitAnalyze(root) {
  const values = syncFormState(root);
  resetGeneratedState(root);
  creatorState.researchStatus = values.script ? "loading" : "no-research";
  renderResearchPanel(root);
  if (!values.script) {
    creatorState.generationStatus = "error";
    renderAlert(root, "error", ["Please enter a script or video idea first."]);
    return;
  }
  const submitted = { ...values };
  creatorState.submittedFormValues = submitted;
  const sequence = creatorState.requestSequence + 1;
  creatorState.requestSequence = sequence;
  creatorState.activeRequestSequence = sequence;
  creatorState.generationStatus = "loading";
  renderAlert(root, "loading", ["Analysis is in progress. This is the only Analyze request for this submission."]);
  setAnalyzeBusy(root, true);
  const payload = {
    script: values.script,
    video_language: values.video_language || "english",
    language: values.language || "english",
    region: values.region || "global",
  };
  ["target_audience", "viewer_promise", "unique_angle", "proof", "video_format", "title_style", "thumbnail_idea"].forEach((field) => {
    if (values[field]) payload[field] = values[field];
  });
  try {
    const data = await apiRequest("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Cache-Control": "no-cache" },
      body: JSON.stringify(payload),
    });
    if (sequence !== creatorState.requestSequence) return;
    creatorState.analysis = data;
    creatorState.generatedPackage = { title: data.title, description: data.description, tags: data.tags, hashtags: data.hashtags };
    creatorState.inferredBrief = data.creator_brief || null;
    creatorState.packageOptions = buildPackageOptions(data);
    creatorState.selectedPackageId = creatorState.packageOptions[0]?.id || null;
    creatorState.checklist = freshChecklist();
    creatorState.generationStatus = "success";
    creatorState.researchStatus = researchHasEvidence(data) ? "available" : "unavailable";
    creatorState.researchError = null;
    const exportButton = root.getElementById("exportBtn");
    if (exportButton) exportButton.disabled = false;
    renderBriefProvenance(root, creatorState.inferredBrief, submitted);
    renderResearchPanel(root);
    renderAnalysisPanels(root);
    const warnings = listOf(data.research_warnings);
    const fallback = data.generation_source === "fallback"
      ? ["Gemini was unavailable for this run. Review the local fallback carefully before publishing."]
      : [];
    renderAlert(root, warnings.length || fallback.length ? "warning" : "success", warnings.length || fallback.length ? [...fallback, ...warnings] : ["Package generated. Review each stage before manual publishing."]);
    renderStage(root, "packaging");
    if (typeof callbacks.onAnalysisSaved === "function") callbacks.onAnalysisSaved(data);
  } catch (error) {
    if (sequence !== creatorState.requestSequence) return;
    creatorState.generationStatus = "error";
    creatorState.error = { message: error.message || "Analysis failed.", requestId: error.requestId || "", status: error.status || 0 };
    creatorState.researchStatus = "error";
    creatorState.researchError = formatApiError(error, "Analysis failed.");
    renderAlert(root, "error", [creatorState.researchError]);
    renderResearchPanel(root);
  } finally {
    if (sequence === creatorState.requestSequence) {
      creatorState.activeRequestSequence = 0;
      setAnalyzeBusy(root, false);
    }
  }
}

function uploadPackageText(option) {
  return ["TITLE", option.title, "", "DESCRIPTION", option.description, "", "TAGS", option.tags.join(", "), "", "HASHTAGS", option.hashtags.join(" ")].join("\n");
}

function copyValue(option, field) {
  if (!option) return "";
  if (field === "tags") return option.tags.join(", ");
  if (field === "hashtags") return option.hashtags.join(" ");
  if (field === "upload-package") return uploadPackageText(option);
  return String(option[field] || "");
}

function legacyClipboardCopy(root, text) {
  const area = root.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  root.body.appendChild(area);
  area.select();
  const copied = typeof root.execCommand === "function" && root.execCommand("copy");
  area.remove();
  return copied;
}

async function copyPackageField(root, button) {
  const option = creatorState.packageOptions.find((item) => item.id === button.dataset.copyPackageId) || selectedPackage();
  const text = copyValue(option, button.dataset.copyField);
  if (!text) {
    if (typeof callbacks.notify === "function") callbacks.notify("Nothing is available to copy.");
    return;
  }
  let copied = false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      copied = true;
    }
  } catch (_) {
    copied = false;
  }
  if (!copied) copied = legacyClipboardCopy(root, text);
  const original = button.textContent;
  button.textContent = copied ? "Copied" : "Copy failed";
  button.classList.toggle("copy-failed", !copied);
  if (typeof callbacks.notify === "function") callbacks.notify(copied ? "Copied to clipboard." : "Clipboard access failed. Select and copy the text manually.");
  window.setTimeout(() => {
    button.textContent = original;
    button.classList.remove("copy-failed");
  }, 1500);
}

function exportAnalysis(root) {
  const choice = selectedPackage();
  if (!creatorState.analysis || !choice) {
    renderAlert(root, "error", ["Run Analyze and select a package before exporting."]);
    return;
  }
  const exportPayload = {
    ...creatorState.analysis,
    creator_workflow_local: {
      selected_package_id: choice.id,
      selected_package: { ...choice },
      checklist: { ...creatorState.checklist },
      persistence: "Local browser state only; not saved to SQLite or YouTube.",
      publishing: "Manual publishing outside Win-Engine OS.",
    },
  };
  const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = root.createElement("a");
  anchor.href = url;
  anchor.download = `seo-analysis-${Date.now()}.json`;
  root.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  if (typeof callbacks.notify === "function") callbacks.notify("Full analysis and local decision exported.");
}

function selectPackage(root, packageId) {
  if (!creatorState.packageOptions.some((item) => item.id === packageId)) return;
  if (creatorState.selectedPackageId !== packageId) creatorState.checklist = freshChecklist();
  creatorState.selectedPackageId = packageId;
  renderPackagingPanel(root);
  renderComparePanel(root);
  renderDecisionPanel(root);
  renderChecklistPanel(root);
}

function moveStage(root, offset) {
  const index = STAGES.findIndex((item) => item.key === creatorState.stage);
  const nextIndex = Math.max(0, Math.min(STAGES.length - 1, index + offset));
  renderStage(root, STAGES[nextIndex].key);
}

function handleCreatorClick(root, event) {
  const target = event.target.closest("button, [data-template-key]");
  if (!target || !root.getElementById("view-creator")?.contains(target)) return;
  if (target.dataset.creatorStage) return renderStage(root, target.dataset.creatorStage);
  if (target.id === "creatorBack") return moveStage(root, -1);
  if (target.id === "creatorNext") return moveStage(root, 1);
  if (target.id === "analyzeBtn") return submitAnalyze(root);
  if (["exportBtn", "decisionExportBtn", "checklistExportBtn"].includes(target.id)) return exportAnalysis(root);
  if (target.dataset.selectPackage) return selectPackage(root, target.dataset.selectPackage);
  if (target.dataset.copyField) return copyPackageField(root, target);
  if (target.dataset.templateKey) {
    const script = root.getElementById("scriptInput");
    if (script) {
      script.value = TEMPLATE_TEXT[target.dataset.templateKey] || "";
      syncFormState(root);
      script.focus();
      if (typeof callbacks.notify === "function") callbacks.notify("Sample idea loaded into the Creator input.");
    }
  }
}

function handleCreatorChange(root, event) {
  const checklistKey = event.target.dataset?.checklistKey;
  if (checklistKey && Object.prototype.hasOwnProperty.call(creatorState.checklist, checklistKey)) {
    creatorState.checklist[checklistKey] = Boolean(event.target.checked);
    renderChecklistPanel(root);
    return;
  }
  if (FORM_FIELDS.includes(event.target.id === "scriptInput" ? "script" : event.target.id)) syncFormState(root);
}

export function mountCreatorPage(root = document, options = {}) {
  const view = root.getElementById("view-creator");
  if (!view) return;
  callbacks = { ...callbacks, ...options };
  view.dataset.pageModule = "creator";
  if (view.dataset.creatorInitialized === "true") {
    renderStage(root, creatorState.stage);
    return;
  }
  view.dataset.creatorInitialized = "true";
  creatorState.initialized = true;
  if (!creatorState.checklist || !Object.keys(creatorState.checklist).length) creatorState.checklist = freshChecklist();
  if (creatorState.formValues && Object.keys(creatorState.formValues).length) writeCreatorForm(root, creatorState.formValues);
  syncFormState(root);
  view.addEventListener("click", (event) => handleCreatorClick(root, event));
  view.addEventListener("input", (event) => handleCreatorChange(root, event));
  view.addEventListener("change", (event) => handleCreatorChange(root, event));
  renderBriefProvenance(root, creatorState.inferredBrief, creatorState.submittedFormValues || {});
  renderAnalysisPanels(root);
  renderStage(root, creatorState.stage);
  if (window.__SEO_YT_TEST__ === true) {
    window.__seoYtCreatorTestHooks = {
      submitAnalyze: () => submitAnalyze(root),
      getState: () => ({
        stage: creatorState.stage,
        researchStatus: creatorState.researchStatus,
        requestSequence: creatorState.requestSequence,
        selectedPackageId: creatorState.selectedPackageId,
        checklist: { ...creatorState.checklist },
        analysis: creatorState.analysis,
      }),
    };
  }
}
