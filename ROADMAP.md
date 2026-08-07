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

The core implementation for Stages A through F is present and verified locally. Personal recommendations remain in the Collecting evidence state until real linked videos reach the documented sample thresholds.

- **Stage A (Package-to-Video Linking)**: `published_video_links` table, video ownership validation, `POST /api/history/runs/{id}/link-video`, `GET /api/published-videos`, `PATCH /api/published-videos/{id}`, and 1-click **🔗 Link Video** actions in the dashboard.
- **Stage B (Age-Based Snapshots)**: `video_performance_snapshots` table and manual due-snapshot refresh for 24h, 7d, and 28d timelines. It stores only metrics returned by YouTube Analytics.
- **Stage C (Personal Learning Engine)**: Cohort analytics engine (`GET /api/learning/cohorts`) with honest evidence confidence thresholds (`Collecting evidence`, `Directional observation`, `Moderate-confidence pattern`, `Evidence-based recommendation`) and cohort median calculations.
- **Stage D (Package Experiments)**: `package_experiments` table and experiment logging endpoints (`POST /api/experiments`) with a real saved performance baseline; all live YouTube changes remain manual.
- **Stage E (Search/Browse/Audience Packages)**: Gemini multilingual generation producing dedicated Search, Browse, and Returning Audience title/thumbnail packages.
- **Stage F (Reliability & Test Suite)**: Unit test suite for persistence and cohort thresholds, SQLite WAL persistence, no-cache headers, and verified Docker `127.0.0.1:8000` binding. Browser automation remains a future test-harness improvement, not a product blocker.

## Rules for any AI agent working on this project

Before editing:

1. Read this roadmap, README.md, compose.yaml, core configuration, API routes, history store, and the relevant feature module.
2. Inspect the working tree. Never overwrite unrelated user changes.
3. Never delete the database, OAuth token, existing history, or channel snapshots unless the creator explicitly requests that exact deletion.
4. Use additive, reversible database migrations. Use CREATE TABLE IF NOT EXISTS, additive columns, and indexes. Never require a destructive reset.
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
| Fewer than 5 linked videos in a cohort | Collecting evidence; no winner claim |
| 5 to 9 linked videos | Directional observation with low confidence |
| 10 to 19 linked videos | Moderate-confidence pattern |
| 20 or more linked videos with repeated outcome | Evidence-based recommendation |

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

1. Idea backlog and topic opportunity workspace.
2. Competitor and outlier watchlist.
3. Published-video audit checklist.
4. Creator-approved experiment center and thumbnail comparison.
5. Search-position tracking only after an approved data source is chosen.

### G1 — Idea backlog and topic opportunity workspace

#### Database

Create `content_ideas` with: `id`, `topic`, `notes`, `format`, `language`, `region`, `search_angle`, `browse_angle`, `audience_angle`, `evidence_json`, `status`, `analysis_run_id`, `published_video_link_id`, `created_at`, and `updated_at`.

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

### G2 — Competitor and outlier watchlist

Create `competitor_channels` with unique `channel_id`, title, notes, format/language focus, created_at, and updated_at. Limit the private workspace to 20 saved channels.

- `POST /api/competitors` validates a channel ID through an approved API call.
- `GET /api/competitors` returns saved channels and latest refresh summary.
- `POST /api/competitors/{id}/refresh` records an immutable dated snapshot of recent public uploads.
- `DELETE /api/competitors/{id}` removes only the watchlist entry after creator confirmation; never delete package history.

Calculate a possible outlier only against the median of at least five recent comparable uploads from the same watched channel. Show formula, sample size, publication age, and capture date. Label it `possible outlier`, never `guaranteed viral video`.

UI must offer `Create different angle`, which opens a blank original brief. It must never prefill or offer to copy a competitor title or script.

### G3 — Published-video audit checklist

Add `GET /api/published-videos/{id}/audit`. Return individual checks with `pass`, `review`, `missing`, or `not_available`, explanation, and evidence source. Do not create one misleading SEO percentage.

Evaluate only known fields:

- Title is truthful and has a clear topic/outcome.
- First two description lines state topic and viewer promise.
- Tags are 5–12 relevant phrases; hashtags are 1–3 focused terms.
- Package is linked, actual metadata is recorded, and an age snapshot is due or complete.
- Playlist, end-screen, card, and thumbnail checks are `not_available` unless connected API data supports them.

### G4 — Experiment center and thumbnail comparison

Show two or three saved title/thumbnail packages side by side. Let the creator upload local thumbnail drafts for visual comparison; keep only local file paths or generated local assets.

- Require one changed variable per experiment: title, thumbnail, description, or tags.
- Save the latest real linked-video metrics as baseline.
- Allow a creator-selected follow-up date and show before/after metrics with dates and caveat that distribution can affect results.
- Never automatically change live YouTube metadata.
- Do not suggest experiments for videos younger than 14 days or already above cohort median unless the creator explicitly overrides.
- Mark multi-variable experiments `mixed / inconclusive`.

Every experiment retains original metadata, changed metadata, reason, baseline, follow-up, and creator approval timestamp.

### G5 — Search-position tracking decision

Search position must not be built by scraping YouTube result pages. Before implementation, document and approve one legal, low-cost data source, including quota, retention, and terms. If no approved source fits the personal budget, do not implement ranking tracking.

Until then, use connected-channel YouTube Analytics search-term data as channel evidence, never as a claimed search ranking.

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
