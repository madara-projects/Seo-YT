# SEO YT Personal Growth Engine Roadmap

## Product contract

SEO YT is a private, single-user YouTube planning and learning tool. It runs in Docker on the creator's laptop today and may later have an Android client. It is not a public SaaS product.

The tool must improve decisions before publishing and learn from the creator's own videos after publishing. It must never promise a fixed growth percentage. Titles, thumbnails, topic demand, viewer satisfaction, retention, and distribution all influence performance.

### Non-negotiable constraints

- Keep the app local. Docker must bind the application to 127.0.0.1:8000 and must not publish Redis.
- Keep Gemini, YouTube API, OAuth, and encryption keys only in ignored local environment files. Never write secrets to source, logs, responses, screenshots, database history JSON, or commits.
- Gemini is the sole AI provider. Do not reintroduce Ollama.
- Do not add paid keyword tools, paid hosting, automatic uploads, or automatic edits to live YouTube metadata without explicit creator approval.
- Preserve the existing YouTube connection, package history, and channel data during every change and database migration.
- The tool is advisory. The creator always chooses what is published or changed.

### Definition of success

The tool can eventually say:

> For your Tamil work-life Shorts, specific personal-outcome titles with short emotional thumbnail text have produced stronger early performance than generic vlog titles. Use package B and make the first 15 seconds faster.

It must say Collecting evidence when there is not enough data to support the conclusion.

## Current implementation snapshot

The core implementation for Stages A through F, Stage G1, Stage H, and Stage I is present and verified locally. Personal recommendations remain in the Collecting evidence state until real linked videos reach the documented sample thresholds.

- **Stage A (Package-to-Video Linking)**: `published_video_links` table, fail-closed owned-video verification with stored channel provenance, `POST /api/history/runs/{id}/link-video`, `GET /api/published-videos`, `PATCH /api/published-videos/{id}`, and 1-click link actions in the dashboard.
- **Stage B (Age-Based Snapshots)**: `video_performance_snapshots` keeps current display data separate from bounded, observable, retryable 24h/7d/28d evidence windows. Only valid Analytics evidence completes a scheduled window.
- **Stage C (Personal Learning Engine)**: `evidence_policy.py` is the single 5/10/20 threshold source for cohort analytics, History diagnosis, channel learning, and Gemini prompt eligibility. One verified video contributes at most one completed observation to a selected format/language/window cohort.
- **Stage D (Package Experiments)**: `package_experiments` table and experiment logging endpoints (`POST /api/experiments`) with a real saved performance baseline; all live YouTube changes remain manual.
- **Stage E (Search/Browse/Audience Packages)**: Gemini multilingual generation producing dedicated Search, Browse, and Returning Audience title/thumbnail packages.
- **Stage F (Reliability & Test Suite)**: Schema version 6, verified online backup-before-migration, runtime foreign-key enforcement, safe cascades, transactional deletion rollback, SQLite WAL persistence, 179 backend tests, and 38 deterministic Chromium workflow tests. Browser tooling remains development-only.
- **Phase 3D (Creator Decision Workflow)**: Complete eight-stage flow from Idea through Checklist, truthful Research/provenance, deterministic local package comparison and selection, decision evidence/unknowns, safe copy/export, manual acknowledgments, and Creator renderer ownership in `pages/creator.js`.
- **Stage H / Phase 4 (Generation Quality & Anti-Repetition Engine)**: Completed 23 August 2026. Structured brief provenance, deterministic Unicode-aware quality/diversity checks, one-repair maximum, evidence-gated personalization trace, package reasons/trade-offs, additive selected-package persistence, and explicit History attribution are implemented. See `docs/phases/PHASE_04.md`.
- **Stage I / Phase 5 (Hook, Pacing & Retention Assistant)**: Completed 23 August 2026. Deterministic pre-publish hook, first-frame, pacing, quote-presentation, risk-map, practical-alternative, and package-alignment guidance is integrated into the existing Creator flow. Comparable mature post-publish average-view-percentage evidence is correlation-labelled and unavailable retention details remain unavailable. See `docs/phases/PHASE_05.md`.
- **Stage G1 / Phase 6 (Idea Backlog & Topic Opportunity Workspace)**: Completed 23 August 2026. The Ideas page, schema-v4 lifecycle persistence, immutable dated research snapshots, approved research reuse, existing-generator linkage, verified publication linkage, honest opportunity explanation, pagination, filtering, and stale-evidence protection are implemented. See `docs/phases/PHASE_06.md`.
- **Stages G2 and G5 / Phase 7 (Watchlist & Honest Demand Explorer)**: Completed 23 August 2026. Verified channel/video watchlists, immutable public snapshots, same-channel comparable-format possible-outlier analysis, dated demand classifications, shared personal-evidence gating, Idea integration, and generation through the existing Creator/History engine are implemented. See `docs/phases/PHASE_07.md`.
- **Stages G3 and G4 / Phase 8 (Published Audits & Experiment Center)**: Completed 23 August 2026. Immutable generated/selected/published audit snapshots, historical pre-publish traceability, actual observation windows, deterministic findings, controlled-versus-observational experiments, explicit video assignment, comparable-window metrics, and evidence-gated result snapshots are implemented. See `docs/phases/PHASE_08.md`.

Stages J through L remain the next product program. Stages G1 through G5, H, and I are complete for their documented scopes. An agent may mark another item complete only after its required database work, backend, dashboard flow, tests, Docker rebuild, and live verification all pass.

### Current gaps that must be addressed first

- The quota-aware due-snapshot collector is implemented but deliberately opt-in and disabled by default. Until the creator enables it, linked-video refresh remains manual/page-triggered and evidence accumulates more slowly.
- Existing links migrated from schema version 0 are deliberately unverified and legacy/current snapshots are deliberately excluded from mature evidence until official verification and new scheduled collection succeed.
- Structured experiments and their dashboard workflow are implemented. Local thumbnail-draft review and creator-visible YouTube Test & Compare import remain future G4 extensions.
- Automated daily opportunity summaries, personal AI coaching, weekly reports, and the PWA/Android boundary are planned but not implemented. Manual Watchlist and Demand research are implemented.
- Creator rendering is modularized. Dashboard, History, Analytics, and Settings renderers still share a compatibility bundle and should be extracted incrementally before several more complex pages are added.

## Rules for any AI agent working on this project

Before editing:

1. Read this roadmap, README.md, compose.yaml, core configuration, API routes, history store, and the relevant feature module.
2. Inspect the working tree. Never overwrite unrelated user changes.
3. Never delete the database, OAuth token, existing history, or channel snapshots unless the creator explicitly requests that exact deletion.
4. Use versioned, backup-first, reversible database migrations. Prefer additive changes; when a SQLite relationship requires a table rebuild, preserve and verify every row inside one transaction. Never require a destructive reset.
5. Show missing data as Not available. Never create guessed analytics values.
6. Add or update tests for every backend behavior and exercise changed dashboard actions in a browser test.

After editing:

1. Run Python compilation and targeted tests.
2. Rebuild with docker compose up -d --build.
3. Verify docker compose ps is healthy and only 127.0.0.1:8000 is published.
4. Test changed API endpoints and the matching dashboard flow.
5. Report what changed, what data was preserved, and any remaining limitation.

## Metadata quality standards

### Titles

Generate three materially different choices:

| Package | Use | Required characteristics |
|---|---|---|
| Search | Viewers actively seeking an answer | Main topic plus clear outcome |
| Browse | Home and Suggested viewers | Curiosity or emotion plus truthful payoff |
| Existing audience | Returning viewers | Channel-specific pattern plus real proof or story |

Every title must:

- Match the real video, creator brief, and available proof.
- Include the main topic naturally when search intent matters.
- Explain an outcome, conflict, transformation, lesson, or reason to watch.
- Be distinct from competitor wording.
- Avoid false certainty, unrelated trend terms, and misleading promises.
- Pair with a thumbnail that adds information rather than repeating the title.

Do not present predicted CTR as fact. Before personal data exists, label it as a low-confidence heuristic.

### Descriptions

For each description:

1. Put the main topic and viewer promise in the first two lines.
2. Explain what the video actually contains.
3. Add chapters only when appropriate.
4. Add a relevant playlist, related-video, or next-view suggestion when the creator provides one.
5. Add a short natural call to action.
6. Put relevant hashtags at the end.

YouTube recommends featuring one or two main words in the title and description, and the first lines are especially visible before viewers expand the description. https://support.google.com/youtube/answer/12948449?hl=en-GB

### Tags and hashtags

- Generate 5 to 12 tags only.
- Use tags for exact phrases, names, spelling variants, common misspellings, and useful Tamil/Tanglish transliterations.
- Do not generate unrelated viral, trending, fyp, or celebrity tags.
- Generate 1 to 3 focused hashtags. Never create a hashtag block.

YouTube says title, thumbnail, and description matter more for discovery than tags; tags are mainly useful for common misspellings. https://support.google.com/youtube/answer/146402?hl=en

YouTube can ignore all hashtags when more than 60 are used and prohibits misleading or excessive tagging. https://support.google.com/youtube/answer/6390658?hl=en

## Stage A — Link a package to a published video

### Goal

Create the missing relationship between a saved SEO package and an actual creator-owned YouTube video.

### Database migration

Add a published_video_links table. Do not modify or delete existing analysis_runs.

Required fields:

| Field | Purpose |
|---|---|
| id | Primary key |
| analysis_run_id | Linked saved package |
| youtube_video_id | Creator-owned YouTube video ID; unique |
| published_at | ISO-8601 publication time |
| selected_title | Exact title actually used |
| selected_thumbnail_package | A, B, C, or manual description |
| selected_description | Exact published description if edited |
| selected_tags_json | Exact tags used |
| selected_hashtags_json | Exact hashtags used |
| format, language, region | Comparison cohorts |
| notes | Optional creator note |
| linked_at, updated_at | Audit trail |

Create indexes for analysis_run_id, youtube_video_id, and published_at.

### Backend work

Add:

- POST /api/history/runs/{id}/link-video. Validate the video belongs to the connected channel before saving.
- GET /api/published-videos. Return links plus latest performance summary.
- PATCH /api/published-videos/{id}. Allow the creator to record a title, thumbnail, or description change.

Validation rules:

- Never accept an arbitrary YouTube video ID without checking ownership.
- A video may link to one analysis run only unless the creator explicitly replaces the link.
- Store creator-edited metadata exactly. Do not silently replace it with generated content.

### Dashboard work

Add to the History detail page:

- Mark as published
- Paste YouTube URL or select from recent owned videos
- Selected package A, B, C, or manual
- Optional fields for title/description edits made before upload
- Link status and last refresh time

### Acceptance checks

- A saved package links to one owned YouTube video.
- A link survives Docker restart.
- The UI distinguishes Generated package from Metadata actually published.
- No existing package or channel data is deleted.

## Stage B — Collect comparable performance snapshots

### Goal

Measure linked video performance at comparable ages, not merely total lifetime views.

### Snapshot schedule

For every linked video, collect snapshots at approximately:

- 24 hours after publish
- 7 days after publish
- 28 days after publish

Also provide a manual Refresh linked video performance action. The laptop app may refresh only while it is running; do not require a cloud background worker.

### Metrics to store

Store only metrics actually returned by authorized YouTube reports:

- Views
- Estimated minutes watched
- Average view duration
- Average view percentage
- Likes, comments, shares
- Subscribers gained

Where the connected report supports them, additionally store:

- Thumbnail impressions
- Thumbnail impressions click-through rate
- Traffic source
- Returning/new viewer information

Use null values for unavailable metrics. Never substitute views for impressions or invent CTR.

The YouTube Analytics API supports metrics including views, watch time, average view duration, average view percentage, likes, comments, shares, and subscribers gained. https://developers.google.com/youtube/analytics/metrics

### Cohort comparison rules

Compare videos only within a relevant cohort:

- Same format: Short, tutorial, quote, vlog, review, and so on.
- Same primary language where possible.
- Similar video age.
- Similar topic cluster when enough examples exist.

Never compare a 28-day tutorial with a 24-hour Short.

### Acceptance checks

- Every linked video has an age-based snapshot timeline.
- The dashboard shows Missing, Collecting, or actual values honestly.
- Repeated refreshes do not corrupt data.
- Retain raw snapshots for at least 12 months on the private laptop.

## Stage C — Personal learning engine

### Goal

Turn linked package plus outcome data into conservative recommendations.

### Evidence thresholds

| Evidence | Allowed recommendation |
|---|---|
| Fewer than 5 mature comparable videos | Collecting evidence; no winner claim |
| 5 to 9 mature comparable videos | Early signal |
| 10 to 19 mature comparable videos | Moderate evidence |
| 20 or more mature comparable videos | Strong historical pattern |

These thresholds are implemented once in `evidence_policy.py` and reused by cohort analytics, History diagnosis, channel learning, and the Gemini prompt. A mature observation requires verified ownership, comparable format/language metadata, and a valid completed 24h, 7d, or 28d snapshot selected for that cohort. Current public counts may be displayed, but they cannot qualify as learning evidence.

The learning engine must maintain three clearly labeled baselines:

1. **Channel baseline**: all owned videos with available real metrics, used only for broad context.
2. **SEO YT baseline**: videos linked to generated packages, used to evaluate this tool's recommendations.
3. **Comparable cohort baseline**: linked videos with the same format, language, similar duration, topic/emotion cluster, and performance age. This is the only baseline allowed for package winner/loser recommendations.

### Learn these features

For each cohort calculate:

- Median early view performance
- Retention and average percentage viewed
- Subscriber conversion per 1,000 views
- Engagement per 1,000 views
- Thumbnail CTR where available
- Best title style, title length range, and promise type
- Best upload day/time only when sample size is adequate

Use robust comparisons:

- Prefer medians over one extreme viral winner.
- Flag outliers so they do not dominate the result.
- Show sample size and confidence beside every recommendation.
- Do not make causal claims when topic demand or distribution may explain results.

Good recommendation:

> Based on 14 linked Tamil tutorial Shorts, specific How to titles with a visible result had higher median retention than generic tips titles. Confidence: moderate.

Bad recommendation:

> This title will get 10 percent CTR.

### Acceptance checks

- Every recommendation names its cohort, sample size, metric, time window, and confidence.
- The tool never calls one video a proven strategy.
- High-confidence personal patterns guide generation but do not become rigid templates.

## Stage D — Package experiments and post-publish decisions

### Goal

Track packaging choices and make responsible title/thumbnail improvement suggestions.

### Build

- Preserve the top 2 to 3 title-thumbnail packages for each analysis.
- Record which package was actually used.
- Let the creator log later manual title or thumbnail changes with timestamp and reason.
- Show a review candidate only when performance is below its relevant cohort and enough time has passed.
- Show before/after performance windows after a creator-approved metadata change.

### Guardrails

- Never automatically change live YouTube metadata.
- Never recommend a title change using only a few hours of data.
- Do not change a video already outperforming its cohort.
- Clearly separate observed result from suggestion.

### Acceptance checks

- Every experiment has package, date, reason, and before/after record.
- The creator explicitly approves every live metadata change.

## Stage E — Research and generation upgrades

Start this only after Stages A through C create usable linked data.

### Research upgrades

- Improve competitor clustering by topic, format, language, title pattern, and published age.
- Detect repeated competitor promises and identify gaps supported by the creator's proof.
- Keep cache keys normalized by language, region, and query.
- Retain different cache lifetimes for trending and evergreen topics.
- Do not scrape YouTube search pages. Use approved API data only.

### Generation upgrades

- Produce the Search, Browse, and Existing Audience packages defined above.
- Make title and thumbnail pairing explicit.
- Explain why a package matches channel history only when personal evidence exists.
- Generate a short and long description.
- Keep tags and hashtags optional; they are not the primary growth lever.
- Make selected language the fast default. Make other languages an optional generation action if Gemini latency or cost matters.

### Acceptance checks

- Packages are distinct, truthful, and connected to the creator brief.
- The model does not repeat generic templates for unrelated ideas.
- All metadata stays within YouTube limits and policy requirements.

## Stage F — Reliability and Android readiness

### Backend and data

- Keep FastAPI as the single business-logic API.
- Version database migrations and document each schema change.
- Add paginated history, history search, JSON export, and local encrypted backup.
- Add database integrity checks and backup-before-migration.
- Keep SQLite, OAuth tokens, Gemini key, YouTube API key, OAuth secret, and encryption key on the laptop.

### Required tests

- Unit tests for creator brief, title quality gate, keyword rules, score calculations, migrations, link validation, and learning thresholds.
- API tests for validation errors, rate limits, pagination, linking/unlinking, and OAuth expiry.
- Browser tests for sidebar routing, generation, History detail, mark-published flow, diagnostics, and errors.
- Docker test confirming localhost-only app binding and no Redis host port.

### Android boundary

Before Android implementation, choose one architecture:

1. Laptop companion mode: Android connects to the laptop only on a trusted local network. Requires authenticated pairing and stops working when the laptop is off.
2. Private backend mode: a secure personal backend is reachable by the phone. Requires a separate security and cost decision.
3. Export/import mode: laptop remains the engine; Android only views exported package/history files. Lowest complexity and no remote secrets.

Do not start Android implementation until one option is explicitly chosen.

## Operational checklist

Before every major feature:

- Confirm Docker is healthy.
- Confirm only localhost exposes the app.
- Back up win_engine.db.
- Confirm no secrets appear in git status, logs, response payloads, or screenshots.

Before declaring a stage complete:

- Run tests and Python compilation.
- Rebuild Docker.
- Verify the changed flow in a browser.
- Test both success and error paths.
- Update the Current implementation snapshot in this roadmap.

## Explicit non-goals

- No fixed 90 percent or 100 percent growth promise.
- No fake CTR prediction presented as fact.
- No misleading clickbait or unrelated tag stuffing.
- No automatic publishing or automatic live-video metadata changes.
- No public hosting, multi-user accounts, or external access without a new explicit security plan.

## Stage G — Personal research and optimization workspace

### Goal

Add the strongest useful workflows found in mature creator tools while preserving SEO YT's private, local, creator-controlled design. Build original features and use only approved YouTube and Google data. Do not copy another product's code, proprietary score, database, interface, or scraped data.

### Build order

Complete and verify each item before the next one:

1. Operationalize the existing opt-in due-snapshot collector and enrich comparable-cohort metadata without changing its disabled-by-default safety posture.
2. Idea backlog and topic opportunity workspace.
3. Competitor and outlier watchlist.
4. Published-video audit checklist.
5. Creator-approved experiment center and thumbnail/first-frame comparison.
6. Honest topic-demand explorer; search-position tracking only after an approved data source is chosen.

### G0 — Learning consistency and automatic collection

#### Shared evidence policy — completed in Phase 1

- `evidence_policy.py` is used by `channel_learning.py`, `history_store.py`, API responses, and the Gemini prompt builder.
- The implemented labels are: fewer than 5 mature comparable videos = Collecting evidence; 5–9 = Early signal; 10–19 = Moderate evidence; 20 or more = Strong historical pattern.
- A valid completed 24h/7d/28d snapshot is required for the selected cohort window. Current and legacy snapshots are never promoted automatically.
- Include cohort identity, sample size, window, median, comparison value, confidence, and data-capture time with every recommendation.
- Remove or migrate older conflicting labels so History, Analytics, generation, and reports cannot disagree.

#### Local due-snapshot collector

- Add a quota-aware scheduler inside the existing application process; do not add a cloud worker or another paid service.
- Run one due-snapshot scan after application startup and then at a conservative interval while Docker remains running.
- Support approximately 6-hour public-count observation plus immutable 24-hour, 7-day, and 28-day comparison snapshots. Analytics values that have not arrived yet remain null and may be filled only by a later official refresh.
- Make collection idempotent. Repeated scans may update the replaceable `current` observation but must not duplicate or silently rewrite a completed scheduled window.
- Record the last attempt, last success, next due time, API operation, and sanitized failure reason. Never record credentials or raw OAuth responses.
- Add a quota budget and backoff. Authentication, quota, and temporary API failures must not stop the application.
- Keep the existing manual Refresh action for immediate creator-controlled updates.

#### Baselines and cohort fields

- Backfill or derive `format`, `language`, `duration_bucket`, `topic_cluster`, and `emotion_or_intent` for linked videos without deleting original metadata.
- Keep channel-wide performance, SEO-YT-linked performance, and comparable cohort performance separate in storage and UI.
- Prefer median and median absolute deviation over arithmetic mean when enough observations exist.
- Flag an extreme video as an outlier and show it separately; never let one viral result define the generation prompt.

#### Acceptance checks

- Every learning consumer returns the same confidence for the same cohort.
- A cohort of four mature videos never changes Gemini's strategy as a learned winner.
- The fifth mature comparable video may produce only a directional observation.
- Restarting Docker catches up due snapshots without creating duplicates.
- API quota or OAuth failure is visible but does not break History, generation, or Docker health.
- Tests cover boundary samples of 0, 4, 5, 9, 10, 19, and 20 videos.

### G1 — Idea backlog and topic opportunity workspace

#### Database

Create `content_ideas` with: `id`, `topic`, `notes`, `format`, `language`, `region`, `visual_or_background`, `on_screen_text`, `target_duration_seconds`, `emotion_or_intent`, `search_angle`, `browse_angle`, `audience_angle`, `evidence_json`, `status`, `analysis_run_id`, `published_video_link_id`, `created_at`, and `updated_at`.

- `status` is one of `idea`, `scripted`, `package_generated`, `published`, or `archived`.
- Add indexes for `status`, `created_at`, and the format/language/region combination.
- Preserve dated research evidence. A refresh creates a new evidence snapshot or explicitly updates `updated_at`; it must never silently rewrite history.

#### API and UI

- `POST /api/ideas` creates a validated idea.
- `GET /api/ideas?status=&limit=&offset=` returns paginated newest-first results.
- `PATCH /api/ideas/{id}` changes only creator-approved fields and status.
- `POST /api/ideas/{id}/research` runs existing approved research and saves dated evidence.
- `POST /api/ideas/{id}/generate` invokes the existing generator and records `analysis_run_id`.

Create an Ideas page with list, filter, and detail panel. Every card shows topic, status, format/language, last research date, and a transparent opportunity explanation. The detail shows Search, Browse, and Existing Audience angles, competitor evidence, publication dates, and actions for Research, Generate package, Mark published, and Archive.

Show `Not enough personal evidence` when appropriate. Never display a guessed search-volume number, trend percentage, or confidence label.

#### Acceptance checks

- An idea survives Docker restart and links to its generated package and published video.
- Pagination and status filters work with 100+ saved ideas.
- Missing research data is represented honestly, not fabricated.
- The complete lifecycle is traceable: idea → script → generated package → published link → mature performance → learning.

#### Stage G1 implementation status (completed 23 August 2026 / Phase 6)

- Schema v4 additively creates `content_ideas` and immutable `content_idea_research_snapshots` with the documented status, creation-date, and format/language/region indexes. The verified backup-first migration preserves all existing History and link records.
- The documented create, paginated list, creator-field update, research, and generation endpoints are implemented, plus a read-only idea-detail endpoint required by the workspace.
- Research refreshes append a dated snapshot. Creator content edits invalidate only the current evidence pointer and retain older snapshots for traceability; status-only changes do not make research stale.
- Generation reuses the existing Creator brief, approved research fields, quality gate, History, retention assistant, and package generator. It does not create a second generator or History system.
- Linking the generated History run to a verified owned YouTube video automatically completes the idea's published association. Deleting a History run preserves the original idea and returns it to `scripted`.
- The Ideas page provides list, status filter, pagination, detail, Search/Browse/Existing Audience angles, public result publication dates, personal evidence state, Research, Generate package, Mark scripted, Mark published, Archive/Restore, and History actions.
- Missing public research and fewer than five mature comparable videos remain unavailable or `insufficient_evidence`; no monthly volume, trend percentage, or outcome confidence is fabricated.
- Verification covers 134 backend and 31 browser tests (165 total). Detailed architecture and limitations are in `docs/phases/PHASE_06.md`.

### G2 — Competitor and outlier watchlist

Create `competitor_channels` with unique `channel_id`, title, notes, format/language focus, created_at, and updated_at. Limit the private workspace to 20 saved channels.

- `POST /api/competitors` validates a channel ID through an approved API call.
- `GET /api/competitors` returns saved channels and latest refresh summary.
- `POST /api/competitors/{id}/refresh` records an immutable dated snapshot of recent public uploads.
- `DELETE /api/competitors/{id}` removes only the watchlist entry after creator confirmation; never delete package history.

Calculate a possible outlier only against the median of at least five recent comparable uploads from the same watched channel. Show formula, sample size, publication age, and capture date. Label it `possible outlier`, never `guaranteed viral video`.

UI must offer `Create different angle`, which opens a blank original brief. It must never prefill or offer to copy a competitor title or script.

Add a private daily-opportunities view generated only from saved watchlists, approved API research, dated evidence, and the creator's own gaps. Each suggestion must explain why it appeared and expire or refresh stale trend evidence. It must never present a competitor's wording as a ready-to-publish title.

#### Stage G2 implementation status (completed 23 August 2026 / Phase 7)

- Schema v5 additively creates normalized channel/video records, immutable channel/video snapshots, and immutable outlier analyses. The existing backup-first migration path preserves History, Ideas, links, analytics, and selections.
- The private UI and API validate public YouTube channel/video identifiers, prevent duplicates, support active/archive/restore lifecycle, refresh dated snapshots, and retain provenance. Archive is used instead of destructive deletion.
- Channel refresh retrieves recent uploads in a bulk video request and records public metadata only. The system never requests private competitor analytics or YouTube write scopes.
- Possible-outlier analysis compares a target only with the latest snapshots for at least five recent same-channel, comparable-format peers. It exposes target views, median, multiplier, sample, capture time, and limitations. Sparse evidence has no multiplier or score.
- The completed scope is manual evidence research. Automated daily opportunity summaries remain a later feature.

### G3 — Published-video audit checklist

Add `GET /api/published-videos/{id}/audit`. Return individual checks with `pass`, `review`, `missing`, or `not_available`, explanation, and evidence source. Do not create one misleading SEO percentage.

Evaluate only known fields:

- Title is truthful and has a clear topic/outcome.
- First two description lines state topic and viewer promise.
- Tags are 5–12 relevant phrases; hashtags are 1–3 focused terms.
- The opening frame, on-screen text, and claimed payoff agree with the title and are readable within the supplied duration.
- Package is linked, actual metadata is recorded, and an age snapshot is due or complete.
- Playlist, end-screen, card, and thumbnail checks are `not_available` unless connected API data supports them.

#### Stage G3 implementation status (completed 23 August 2026 / Phase 8)

- Schema v6 additively creates immutable `published_video_audits`; every refresh appends a new version instead of rewriting historical truth.
- Audits preserve primary generated metadata, explicit creator selection or unknown attribution, actual owned YouTube metadata, saved quality/retention/Idea/Demand traces available before publication, current observations, completed windows, and shared cohort evidence.
- Title, description, tags, and hashtags are deterministically labelled exact, changed, missing, unknown, or unavailable across generated-to-selected, selected-to-published, and generated-to-published comparisons.
- Findings include a code, severity, category, explanation, evidence, evidence state, and recommended interpretation. Summary states describe data availability and maturity, never success/failure or causality.
- Learning candidates reuse the shared evidence policy and remain insufficient, hypothesis-only, or mature comparable observations. No audit reconstructs unavailable historical facts from current public research.
- The Published Audits page and API expose candidates, filters, immutable versions, detail, findings, evidence, and refresh actions. Detailed contracts are in `docs/phases/PHASE_08.md`.

### G4 — Experiment center and thumbnail/first-frame comparison

Show two or three saved title/thumbnail packages side by side. Let the creator upload local thumbnail drafts for visual comparison; keep only local file paths or generated local assets.

- For Shorts, treat the first visible frame, on-screen hook, readability, and visual loop as first-class experiment assets rather than assuming a conventional thumbnail controls Shorts-feed performance.
- Provide mobile-size preview, safe-area overlay, contrast/readability checks, clutter warning, and title-image duplication warning.
- Let Gemini review an explicitly uploaded local image when quota is available. Label visual advice as an AI review, not measured performance.
- Allow manual recording or import of creator-visible YouTube Test & Compare results when supported. Do not invent an API result that YouTube does not expose.

- Require one changed variable per experiment: title, thumbnail, description, or tags.
- Save the latest real linked-video metrics as baseline.
- Allow a creator-selected follow-up date and show before/after metrics with dates and caveat that distribution can affect results.
- Never automatically change live YouTube metadata.
- Do not suggest experiments for videos younger than 14 days or already above cohort median unless the creator explicitly overrides.
- Mark multi-variable experiments `mixed / inconclusive`.

Every experiment retains original metadata, changed metadata, reason, baseline, follow-up, and creator approval timestamp.

#### Stage G4 implementation status (completed core scope 23 August 2026 / Phase 8)

- Schema v6 adds structured experiment definitions, explicit verified-video assignments, and immutable result snapshots beside the preserved legacy package-change log.
- Every comparison records controlled or observational mode, one named variable, hypothesis, control and variant definitions, primary/secondary metrics, minimum and target samples, one completed 24h/7d/28d window, lifecycle, and notes.
- A video is counted only after explicit creator assignment. Duplicate assignment, unverified links, invalid roles, and assignments to closed experiments are rejected.
- Comparison output shows assigned/eligible/mature group counts, missing metrics, mean, median, absolute and relative differences, evidence state, interpretation, limitations, and next collection step. At least five eligible videos per group are required for a direction.
- Results are limited to insufficient, directional control/variant, inconclusive, mixed, or observational pattern. No fake statistical significance or causal winner is calculated, and learning candidates are not automatically applied to generation.
- The Experiment Center page supports creation, filtering, detail, lifecycle, assignment, removal, and comparison. Thumbnail/first-frame draft analysis and creator-visible Test & Compare import remain future extensions, not fabricated API capabilities.

### G5 — Honest topic-demand explorer and search-position decision

Build a topic-demand explorer from dated, explainable signals available to this private tool:

- Relevant recent result count from approved API research.
- Publication freshness and recent view velocity.
- Possible outliers from both large and small channels.
- Repeated title/topic patterns and visible content gaps.
- The creator's connected YouTube search-query analytics when available.
- Evergreen versus time-sensitive classification.

Display the individual signals and their capture times. A combined opportunity label may summarize them, but it must never be labeled monthly search volume unless an approved source actually supplied monthly search volume.

Search position must not be built by scraping YouTube result pages. Before implementation, document and approve one legal, low-cost data source, including quota, retention, and terms. If no approved source fits the personal budget, do not implement ranking tracking.

Until then, use connected-channel YouTube Analytics search-term data as channel evidence, never as a claimed search ranking.

#### Stage G5 implementation status (completed 23 August 2026 / Phase 7)

- Schema v5 additively creates immutable `demand_research_snapshots`, with optional Idea linkage and a content fingerprint that exposes when saved research is stale after creator-content changes.
- Standalone topics and saved Ideas reuse the approved YouTube research service, Watchlist observations, and the shared mature personal-evidence policy. No second research, generation, or History system was introduced.
- Results expose dated public samples, recent-publication count, independent-channel count, captured-view median, matching possible outliers, personal-evidence state, reasons, provenance, and limitations.
- Deterministic labels are limited to `insufficient_evidence`, `emerging_signal`, `active_topic`, and `strong_observed_interest`. They are summaries of visible inputs, not demand scores, CTR predictions, search rank, monthly volume, CPC, or guarantees.
- Demand-to-generation actions use the existing Creator generator and History persistence. YouTube publishing and metadata changes remain manual.
- Search-position tracking remains unimplemented because no legal, approved, low-cost ranking source has been selected.

### Data boundaries and references

- Use the official YouTube Data API and YouTube Analytics API only for YouTube data.
- Keep Gemini local to this workflow; never send OAuth tokens, private analytics, or history to another product.
- Do not imitate vidIQ, TubeBuddy, or YouTube scores. Document every SEO YT formula and input.
- Treat keyword volume, competition, trend, and thumbnail predictions as estimates only when an approved source and capture date are available.
- Do not add a browser extension, scraper, paid keyword provider, or automatic metadata editor without a separate explicit decision.

Workflow references, not implementation dependencies:

- vidIQ research: https://support.vidiq.com/en/articles/9421214-keywords-research
- vidIQ channel audit: https://support.vidiq.com/en/articles/10141815-channel-audit
- TubeBuddy keyword explorer: https://www.tubebuddy.com/tools/keyword-explorer/
- TubeBuddy experiment guidance: https://support.tubebuddy.com/hc/en-us/articles/21191305824027-A-B-Testing-FAQs

## Stage H — Generation quality and anti-repetition engine

### Goal

Make every package truthful, natural, distinct, content-specific, and informed by mature personal evidence without turning successful patterns into repetitive templates.

### H1 — Structured creator brief

Before Gemini generation, normalize the creator's input into a stored brief containing:

- Video format and intended duration.
- Exact spoken dialogue, exact on-screen text, or explicit `no voice-over` state.
- Visual/background description and important objects or people.
- Core meaning, emotion, viewer problem, and intended payoff.
- Target audience, primary language, region, and content restrictions.
- Claims that are supported and interpretations that are not supported.
- Desired Search, Browse, or Existing Audience emphasis.

The original user input remains immutable in History. Store the normalized brief beside it rather than replacing it.

### H2 — Candidate diversity

Generate candidates across different truthful mechanisms, not synonym swaps:

- Direct emotional conflict.
- Curiosity with a specific payoff.
- Search/topic clarity.
- First-person personal framing.
- Existing-audience framing only when channel evidence exists.

Measure semantic similarity among candidates and against recent generated and published titles. Reject a candidate when it repeats a recent template, changes the video's meaning, introduces unsupported betrayal/breakup/result claims, or merely rearranges the same phrase.

Do not force every content type into all five mechanisms. A quiet quote Short may need emotional and curiosity variants; a tutorial may need outcome and problem-solving variants.

### H3 — Deterministic post-generation quality gate

Run a local validation pass after Gemini and before saving:

- Title matches the actual content and supplied proof.
- Title length and important-word placement are suitable for mobile display.
- Candidate titles are materially distinct.
- Description first lines state content and viewer relevance naturally.
- Description does not repeat a list of SEO phrases or invent facts.
- Tags are focused; retain the creator-required Shorts tags `shorts`, `yt`, `youtube shorts`, and `viral shorts` for Shorts.
- Hashtags contain 1–3 relevant terms and are not duplicated accidentally.
- Search/Browse/Audience labels match the actual candidate strategy.
- Emoji use is optional, relevant, and limited.
- Unicode is normalized and copy output contains no mojibake or invisible unwanted characters.

If too few candidates pass, make at most one repair request to Gemini. If Gemini fails or quota is exhausted, show a clearly labeled fallback and never describe it as Gemini output.

### H4 — Personal evidence injection

- Inject only mature comparable-cohort observations that meet the shared Stage C evidence policy.
- Include both positive and negative patterns with sample size, metric, window, and confidence.
- Never send OAuth tokens, API keys, raw private database files, or irrelevant channel history to Gemini.
- Cap the learning context so it does not consume quota or overpower the current video's meaning.
- Prefer diversity around a proven principle; never command Gemini to reproduce the exact winning title.

### H5 — Package explanations

For each recommended package, display:

- Intended discovery surface: Search, Browse, or Existing Audience.
- Content-specific reason it fits.
- Personal evidence used, or `No mature personal evidence used`.
- Main risk or tradeoff.
- Generated-versus-heuristic labels for every score.

Opportunity Score remains research context, not a predicted chance of growth. Title Quality remains a rule-based quality assessment, not predicted CTR.

### Acceptance checks

- A test set of at least 30 materially different briefs produces no cross-topic generic-template leakage.
- Quote, tutorial, vlog, review, and story fixtures retain their actual meaning.
- At least three title candidates per run are semantically distinct when the brief supports three legitimate angles.
- Descriptions read naturally and do not repeat raw tag phrases.
- Required Shorts tags remain present without causing unrelated tags to be added.
- Gemini quota exhaustion causes one clear fallback, not repeated paid or quota-consuming retries.
- History records the brief, raw model label, quality-gate decisions, selected output, and actual published metadata.

### Phase 4 implementation status (completed 23 August 2026)

Stage H is formally Phase 4. Its implementation is complete for this repository pass: candidates are locally filtered rather than padded; failed Gemini packages receive at most one repair; quota/empty output falls back without repair; mature comparable evidence is the only personal-performance input; the Creator records an explicit server-validated package selection; and History reports selected-versus-primary-versus-uploaded attribution without inferring unknown choices. Schema v3 adds only `analysis_package_selections` and preserves existing rows through the backup-first migration framework. Verification passed 83 backend tests and 27 browser tests (110 total). Detailed rules and limitations are in `docs/phases/PHASE_04.md`.

## Stage I — Hook, pacing, and retention assistant

**Implementation status: completed 23 August 2026 (Phase 5).** The implementation uses the existing schema-v3 analysis payload and selection record rather than duplicating data in a new table. Detailed behavior, provenance, tests, and limitations are documented in `docs/phases/PHASE_05.md`.

### Goal

Improve the video itself, especially the first seconds of Shorts, rather than treating metadata as the only growth lever.

### I1 — Pre-publish Short guidance

For a Short, calculate and display:

- Word count and estimated reading time for on-screen text.
- Whether the hook appears within the first second.
- Recommended minimum readable duration based on word count.
- Text contrast, safe-area, font-size, and line-count checklist.
- Whether title, opening frame, and on-screen text promise the same experience.
- Optional shorter on-screen version that preserves meaning; never silently replace an exact quote.
- Suggested clean loop or final visual beat.
- Mood/audio direction as creative guidance, not a claim that a sound will trend.

For narrated or long-form videos, provide a separate structure: opening promise, proof, pacing sections, payoff, and next-view transition. Do not apply Shorts rules to long-form content.

### I2 — Post-publish retention learning

- Store the actual duration, hook type, on-screen word count, visual type, audio/mood note, and loop type used when the creator links the video.
- Compare retention only inside mature comparable cohorts.
- Identify repeated retention drops only when official data exposes the required detail; otherwise report only average duration/percentage viewed.
- Learn visual or hook associations as correlations. Never claim that a sunset, rainy road, song, title, or tag caused the result.

### Acceptance checks

- A 17-word quote receives a realistic reading-time recommendation and no generic `add more curiosity turns` advice.
- Missing detailed retention data displays `Not available`.
- Long-form and Shorts receive separate pacing logic.
- Personal hook recommendations obey the shared evidence thresholds.

### Phase 5 completion notes

- Shorts and long-form content use separate deterministic pacing branches.
- Exact quotes are preserved and any shorter presentation is labelled as a generated structural alternative, never a silent replacement or attribution.
- Duration-based timing bands are emitted only when duration is creator-supplied; otherwise the risk map uses relative opening/setup/middle/payoff stages.
- The saved analysis payload retains the complete Phase 5 response, while explicit package selection stores a compact retention trace for later attribution.
- Linked History reports dynamically expose the comparable retention-learning state. A minimum of five eligible completed observations with real average-view-percentage values is required before displaying observed correlations.
- Official retention curves and exact drop timestamps are not available in the current integration and are never fabricated.
- Verification covers 114 backend and 29 browser tests (143 total). Schema remains version 3.

## Stage J — Personal AI coach and weekly channel report

### Goal

Provide a private, evidence-citing assistant over the creator's own structured history, analytics, ideas, competitors, and experiments.

### J1 — Evidence service before chat

Create deterministic query functions for:

- Best and weakest comparable linked videos by 24-hour, 7-day, and 28-day windows.
- Title mechanism, title length, topic/emotion, hook, visual, duration, and upload-time cohorts.
- Retention, engagement per 1,000 views, subscriber conversion, and view performance.
- Package usage: exact generated fields used, edited, or ignored.
- Experiments awaiting follow-up and ideas awaiting action.

The coach must receive a compact evidence object from these functions. It must not invent SQL, metrics, sample sizes, or channel facts inside the model response.

### J2 — Coach interface

Support questions such as:

- Why did this linked video underperform its cohort?
- Which title mechanisms work for my quote Shorts?
- What should I publish next, and what evidence supports it?
- Are sunset and rainy-road visuals associated with different retention?
- Is this published video a responsible title-change candidate?

Every answer must show evidence cards containing cohort, sample size, time window, comparison metric, confidence, and last refresh. If evidence is insufficient, answer with a collection plan rather than generic certainty.

Store coach conversations locally with rename and delete controls. Do not send an entire channel database when only a small evidence summary is required.

### J3 — Weekly private report

Generate a local weekly report containing:

- Strongest and weakest mature upload with fair cohort comparison.
- Meaningful retention, engagement, and subscriber-conversion movement.
- Package fields used versus changed before publishing.
- Mature patterns and explicitly labeled early observations.
- Videos missing package links or due snapshots.
- Experiments awaiting follow-up.
- Idea backlog state and three evidence-backed next actions.

The report may be generated on demand and on a local schedule while Docker is running. It must not email, publish, or upload anything automatically.

### Acceptance checks

- Coach answers reproduce the deterministic evidence values exactly.
- A channel with fewer than five comparable mature videos receives no winning-pattern claim.
- Deleting a chat does not delete packages, analytics, ideas, or experiments.
- Weekly report generation succeeds without Gemini by showing the deterministic metrics and collection status.

## Phase 3C — Frontend extraction (completed 16 August 2026)

### Delivered

- Extracted the embedded dashboard shell and CSS into `win_engine/api/static/index.html` and `css/app.css`.
- Added FastAPI same-origin static serving at `/static/*`; the default `/`, `/app`, and `/dashboard_view` routes now return the local shell.
- Added native ES modules for the shared API client, normalized errors, explicit in-memory state, hash-navigation metadata, and five page lifecycle seams.
- Kept all existing DOM IDs, hash routes, API payloads, request gates, truthfulness labels, Creator advanced-field behavior, History behavior, Analytics evidence separation, and Settings collector vocabulary.
- Preserved the embedded implementation at `/dashboard_legacy` as a route-only rollback path.
- Added deterministic browser coverage for static assets, module loading, and the legacy route. The extracted frontend passed 14 Chromium tests and the full local suite passed 79 tests against a fresh local FastAPI process.

### Deliberate limitations

- Dashboard, History, Analytics, and Settings renderers remain in `js/app.js` as a compatibility bundle while their page seams are introduced. Phase 3D-E later removed all Creator-only rendering and handlers from that bundle.
- Inline handlers generated inside legacy-compatible dynamic strings remain behind the documented `window` bridge. No new inline handlers were added to the static shell.
- Docker image rebuild/health and production-image browser-tool inspection were unavailable during Phase 3C itself; final Phase 3D verification later completed those checks successfully.

### Acceptance gate

Phase 3C is complete for local extraction and compatibility. The complete Phase 3D workflow is now delivered and verified without changing the API, database, permissions, or production dependency model.

## Phase 3D — Creator decision workflow (completed 16 August 2026)

### Completed increments

- **3D-A — state and workflow shell:** explicit in-memory Creator state, eight stages, preserved form values, entered-versus-inferred brief provenance, one Analyze owner, and stale-response protection.
- **3D-B — Research and provenance:** read-only rendering of existing research queries, research decision, public YouTube observations, local scoring candidates, keyword/entity signals, thumbnail metadata, generation context, warnings, and explicit unavailable/error states.
- **3D-C — package comparison and selection:** deterministic local package IDs, primary/alternative title and thumbnail cards, source-labelled heuristics, safe copy actions, and local selection with zero network calls.
- **3D-D — decision and checklist:** selected-package summary, evidence/unknown separation, source guide, eight manual acknowledgments, manual-publishing boundary, and full-analysis export with clearly marked local workflow state.
- **3D-E — Creator renderer migration:** `pages/creator.js` now owns Creator state, Analyze, rendering, selection, copy, checklist, and export. The old Creator renderer, inactive rollback callback block, and temporary Creator window bridge were removed from `app.js`.
- **3D-F — regression and usability:** active-frontend encoding artifacts were removed, responsive workflow styling was reviewed in real Chromium, request gates remained intact, and local plus Docker verification passed.

### Guardrails retained

- No new API endpoint, response field, schema, migration, database write, OAuth scope, YouTube write, collector behavior, Docker dependency, paid API, quota change, or Ollama change.
- Stage navigation and evidence presentation make no additional Gemini, YouTube, OAuth, or research calls.
- Public observations, local heuristics, AI suggestions, creator input, and insufficient evidence remain visibly distinct.
- Package selection and checklist interactions are local session state. They do not mutate the Analyze response, SQLite History, or YouTube.

### Verification gate

Phase 3D passed 65 backend tests, 27 deterministic Chromium tests, and 92 tests in full local discovery. The rebuilt `win-engine` container is healthy; its backend suite passes with browser tests correctly skipped, and the production image contains no Playwright, Chromium, Node, or Ollama.

## Stage K — Maintainable dashboard, PWA, and Android boundary

### Goal

Make the growing tool fast, testable, mobile-friendly, and safe without prematurely creating a public service.

### K1 — Frontend modularization (Phase 3C foundation complete)

Continue splitting the compatibility bundle into:

- HTML templates or a small static application shell.
- Shared design tokens and responsive CSS.
- Page-specific JavaScript modules.
- One reusable API client with timeout, error parsing, request cancellation, and stale-request protection.
- Reusable modal, toast, table, metric, empty-state, loading, and confirmation components.

Preserve routes and behavior during the split. Phase 3C already delivered the static shell, shared API/error/state/navigation modules, and page lifecycle seams; move renderer bodies one page at a time without redesigning or rewriting every feature in one unreviewable change.

### K2 — Performance and accessibility

- Load page data only when that page is opened.
- Cache read-only API results briefly and invalidate them after mutations.
- Paginate History, Ideas, competitors, experiments, and coach chats.
- Cancel obsolete requests and prevent duplicate refresh/generation clicks.
- Use semantic buttons, visible keyboard focus, labels, sufficient contrast, and mobile touch targets.
- Add browser tests for every sidebar route and critical action.

### K3 — Installable PWA

- Add a web-app manifest, icons, responsive layout, and conservative service worker.
- Cache only the static shell. Never cache secrets, OAuth callbacks, private analytics responses, or mutation responses.
- Show an offline state; do not claim generation or YouTube sync works offline.
- Keep the current Docker binding to `127.0.0.1` until an Android connection architecture is explicitly approved.

### K4 — Android decision gate

Choose and document one option before implementation:

1. **Laptop companion**: authenticated local-network pairing; laptop and Docker must be running.
2. **Private personal backend**: requires TLS, authentication, secret storage, updates, backups, and a separate cost/security approval.
3. **Export/import viewer**: phone consumes an encrypted export and cannot generate or sync live data.

Do not expose port 8000 to the LAN or internet merely to make the PWA reachable. No Android build may embed OAuth client secrets or an unencrypted Gemini key in recoverable application assets.

### Acceptance checks

- Existing desktop workflows remain functional after modularization.
- Main pages work at common phone widths without horizontal page overflow.
- Browser tests cover navigation, generation, History detail, linking, refresh, ideas, experiments, and errors.
- The installed PWA never serves stale private API data from a cache.
- An approved threat model and architecture decision exist before any network exposure.

## Stage L — Cost, quota, backup, and operational reliability

### Goal

Keep normal personal operation free or below the creator's one-dollar monthly target without sacrificing truthfulness or data safety.

### L1 — Quota and cost controls

- Add a local quota dashboard for Gemini calls, model used, successful generations, repair calls, failures, YouTube Data API operations, and Analytics refreshes.
- Cache normalized research queries by query, region, language, format, and freshness class.
- Reuse deterministic analysis locally instead of asking Gemini to recalculate it.
- Generate only the selected language by default.
- Permit at most one Gemini repair request for a failed quality gate.
- Stop immediately on a confirmed quota-exhausted response and show the reset guidance available from the provider response.
- Never silently switch to a paid provider, paid keyword API, or a more expensive model.

### L2 — Data protection and recovery

- Add a versioned migration registry and backup-before-migration.
- Run SQLite integrity checks and expose the last successful result in Settings.
- Provide creator-triggered encrypted backup and restore with a dry-run validation step.
- Provide JSON export for packages, links, snapshots, ideas, experiments, and deterministic reports without exporting secrets.
- Preserve at least 12 months of raw linked-video snapshots unless the creator explicitly changes retention.

### L3 — Operational diagnostics

- Settings must show Docker/app version, database path, schema version, database health, last backup, last YouTube sync, OAuth state, Gemini state, and quota summary without revealing secret values.
- Use structured sanitized logging and stable request IDs.
- Add health checks for database access and required internal services, but do not make temporary Gemini or YouTube failure mark the local app process unhealthy.
- Test OAuth expiry, revoked consent, API quota exhaustion, Gemini 429/5xx responses, SQLite lock contention, malformed model JSON, and Docker restart recovery.

### Acceptance checks

- A normal generation uses one Gemini call; a repair path uses no more than two total.
- Cached identical research does not repeat YouTube search operations inside its freshness window.
- Backup restore is verified against a temporary database before replacing the live database, and replacement requires explicit creator confirmation.
- No secret appears in logs, exports, browser storage, database history JSON, screenshots, or Git.
- Docker remains healthy and bound only to `127.0.0.1:8000`.

## Master execution sequence

### Phase 2 implementation status (15 August 2026)

- Schema 2 comparable metadata and creator edit audit: implemented and migrated with backup-first verification.
- Source-aware cohort filters and evidence reporting: implemented with language, format, duration bucket, and topic filters; unknown values remain excluded.
- Automatic snapshot collector: implemented but disabled by default; dry-run and quota safeguards are available.
- History comparable-metadata editor and collector status API: implemented.
- Optional Playwright browser smoke coverage: added; requires separate development installation and Chromium.
- Docker rebuild, in-container verification, and browser execution were subsequently completed during final Phase 3D verification.

### Phase 3A/3B implementation status (15 August 2026)

- Phase 3A completed the browser-test harness, deterministic request interception, and production-image separation for browser tooling.
- Phase 3B completed the embedded dashboard reality fixes: neutral unavailable states, evidence/current-data labels, normalized frontend API errors with request IDs, advanced-brief retention, truthful collector states, targeted copy-button safety, and request-count coverage.
- Phase 3B remains behaviorally compatible with the extracted dashboard. The complete Creator workflow and evidence presentation are now delivered through Phase 3D-A through 3D-F.
- Browser tests remain development-only and run with a separately installed Chromium; Playwright and Chromium are not production dependencies.

### Phase 3C implementation status (16 August 2026)

- Same-origin static HTML/CSS/native-module frontend is the default route.
- Shared API/error handling, explicit frontend state, navigation metadata, and page lifecycle seams are extracted.
- `/dashboard_legacy` preserves the embedded dashboard for route-only rollback.
- 27 deterministic Chromium tests and 92 full local tests pass after the completed Phase 3D workflow.
- The rebuilt Docker application is healthy on `127.0.0.1:8000`; same-origin assets and `/dashboard_legacy` return HTTP 200, and production excludes Playwright, Chromium, Node, and Ollama.

Agents must implement the remaining work in this order unless the creator explicitly reprioritizes it:

1. **J** — Add the evidence service, personal coach, and weekly report.
2. **K1 and K2** — Extract the remaining page renderers and optimize accessibility/performance; Creator ownership is complete.
3. **L** — Complete quota visibility, encrypted backup/restore, and operational diagnostics.
4. **K3 and K4** — Add the PWA only after the Android connection architecture is approved.

### Definition of personal feature parity

SEO YT does not need a commercial creator database, billing system, team workspace, public browser extension, or proprietary keyword-volume imitation. It reaches its intended personal parity when the creator can:

1. Save and research an original idea.
2. Generate distinct truthful packaging and hook guidance from the real content.
3. Compare competitors and possible outliers using transparent dated evidence.
4. Publish manually and link the exact owned video to its package.
5. Collect comparable performance automatically while Docker is running.
6. See what generated metadata was actually used and how the video performed.
7. Run creator-approved packaging experiments.
8. Receive conservative personal recommendations and weekly actions backed by sufficient mature data.
9. Use the workflow comfortably on desktop and, after an explicit security decision, Android.
10. Keep normal operation private and free or below the stated personal monthly budget.
