# Phase 7 — Private Watchlist and Honest Demand Explorer

Completed: 23 August 2026  
Application version: `0.12.0`  
Database schema: `5`

## Scope

Phase 7 implements Roadmap stages G2 and G5 as one coherent evidence workflow. A creator can save verified public YouTube channels and videos, capture dated public snapshots, inspect conservative same-channel possible-outlier analysis, research a topic from visible public and eligible personal signals, connect research to a saved Idea, and send the result through the existing Creator generator and History system.

This phase does not publish videos, edit live metadata, access private competitor analytics, scrape YouTube, claim search position, or promise performance.

## Architecture and reuse

- `IntelligenceStore` uses the existing SQLite database, `HistoryStore` connection behavior, WAL configuration, runtime foreign keys, and backup-first migrations.
- `YouTubeClient` remains the single official public-data integration. Channel refresh uses one recent-upload lookup followed by a bulk video-details request instead of one request per video.
- Demand research reuses `ResearchService`, the shared cohort evidence policy, saved Ideas, the existing package generator, and existing History persistence.
- New native modules `pages/watchlist.js` and `pages/demand.js` use the shared frontend API/error/navigation layer. The existing eight-stage Creator workflow is unchanged.

## Schema v5

The additive v4-to-v5 migration creates:

- `watchlist_channels`: normalized verified channel identity, creator notes/focus, lifecycle, and latest research time.
- `watchlist_channel_snapshots`: immutable captured channel statistics and provenance.
- `watchlist_videos`: normalized verified public video identity, optional watched-channel relationship, format inference, notes, lifecycle, and latest research time.
- `watchlist_video_snapshots`: immutable captured public video statistics and metadata.
- `watchlist_outlier_analyses`: immutable derived analyses with classification, peer sample, median, multiplier when justified, explanation, and limitations.
- `demand_research_snapshots`: immutable topic/Idea research payloads, classification, reasons, provenance, limitations, and Idea-content fingerprint.

Foreign keys preserve referential integrity. Archiving retains evidence. Existing package History, Ideas, selected packages, OAuth state, linked videos, and performance snapshots are not reset or rewritten.

## Watchlist behavior

Channels and videos are resolved through the official YouTube Data API before they are saved. Missing or unavailable identifiers are rejected and duplicates return a conflict. The creator can search/filter records, open details, refresh research, and archive or restore entries.

Each refresh appends a new snapshot. Older snapshots and analyses remain immutable. Channel refresh stores public channel statistics plus recent public uploads; video refresh stores public title, description, tags, publication time, duration-derived format, views, likes, comments, and capture provenance when supplied by the API.

## Possible-outlier rules

An analysis compares the target video's latest public view snapshot only with the latest snapshots of recent uploads from the same channel and comparable known format.

- At least five positive-view peers are required.
- The baseline is the peer median, not a cross-channel average.
- `multiplier = target captured views / peer median captured views` only when the minimum sample and positive median exist.
- A multiplier of at least `2.5` is labelled `possible_outlier`; a lower observed multiplier is `observed_normal`.
- Sparse or invalid evidence is `insufficient_evidence`, and no multiplier or numeric score is shown.
- The UI exposes sample size, baseline, target, format, capture time, publication context, and explicit limitations.

This is an observation, not proof that a title, keyword, thumbnail, or publishing time caused the result.

## Demand Explorer rules

Demand research accepts a topic directly or the creator fields from a saved Idea. It records:

- sampled relevant public results and their publication dates;
- results published within the current 90-day observation window;
- distinct observed channels;
- median captured public views where views are available;
- topic-matching saved Watchlist videos with qualifying possible-outlier evidence;
- mature comparable personal evidence, only through the shared 5/10/20 policy;
- capture time, sources, reasons, unavailable states, and limitations.

The deterministic classifications are `insufficient_evidence`, `emerging_signal`, `active_topic`, and `strong_observed_interest`. They summarize the displayed evidence. They are not keyword-volume scores, CTR predictions, growth probabilities, search rankings, or guarantees.

Idea-linked snapshots store an Idea-content fingerprint. If the creator changes the underlying Idea content, the previous snapshot stays intact but is displayed as stale. Status-only changes do not invalidate topic evidence.

## API surface

Watchlist:

- `POST|GET /api/watchlist/channels`
- `GET|PATCH /api/watchlist/channels/{id}`
- `POST /api/watchlist/channels/{id}/research`
- `POST|GET /api/watchlist/videos`
- `GET|PATCH /api/watchlist/videos/{id}`
- `POST /api/watchlist/videos/{id}/research`
- `POST /api/watchlist/videos/{id}/analyze-outlier`

Demand:

- `POST|GET /api/demand/research`
- `GET /api/demand/research/{id}`
- `POST /api/ideas/{id}/demand-research`
- `POST /api/demand/research/{id}/generate`

All routes retain the existing request-ID, normalized error, rate-limit, security-header, and localhost deployment behavior.

## User workflow

1. Save a public channel or video in Watchlist.
2. Refresh it to append current public evidence.
3. Analyze a video; interpret a possible-outlier label only with its peer sample and limitations.
4. Open Demand and research an original topic, or start Demand research from an Idea.
5. Review every dated signal, unavailable state, source, and limitation.
6. Generate through the existing Creator engine when the evidence and original content justify proceeding.
7. Select/save the package in existing History, upload manually, link the owned video, and let mature personal evidence accumulate.

## Safety and privacy

- OAuth remains read-only; no YouTube write or upload scope was added.
- Competitor evidence is public Data API evidence only.
- Gemini receives the existing generation context only; tokens and credentials are never included.
- No browser extension, scraper, paid keyword provider, automatic metadata editor, or parallel analytics database was added.
- App exposure remains `127.0.0.1:8000`; Redis remains internal to Compose.

## Verification

Phase 7 adds 20 backend tests and 3 deterministic Chromium workflows. The completed repository passes 154 backend tests and 34 browser tests, 188 total.

Coverage includes schema integrity and v4 migration preservation; immutable snapshots; lifecycle and duplicate behavior; public-resource validation; sparse, qualifying, and normal outlier cases; all four demand classifications; stale fingerprints; provenance and limitation fields; mature personal-evidence gating; Watchlist UI actions; duplicate-click protection; Demand UI; and Idea-to-Demand-to-existing-generation integration.

Docker verification must confirm schema `5`, SQLite integrity, healthy services, localhost-only app exposure, internal Redis, HTTP 200 for the static dashboard and legacy rollback route, read-only OAuth scopes, and absence of Playwright, Chromium, Node, and Ollama from the production image.

## Known limitations

- Public snapshots reflect capture time and can differ from current YouTube counts.
- YouTube quota or API availability can prevent a refresh; prior evidence remains available and dated.
- Public APIs do not expose competitor impressions, CTR, retention, traffic sources, or causal explanations.
- Video format is inferred from public duration when available; unavailable duration produces an unknown format.
- Demand classifications use sampled research, not the whole YouTube corpus.
- Search-position tracking remains intentionally absent until a legal, approved, low-cost source is documented.
- Automated daily opportunity summaries are not part of this phase.
- Watchlist evidence becomes more useful only after the creator deliberately saves and refreshes relevant records.

## Next milestone

Roadmap stages G3 and G4: an evidence-specific published-video audit and the complete experiment/thumbnail/first-frame comparison workflow. These must continue to preserve manual publishing, honest unavailable states, and one-variable experiment discipline.
