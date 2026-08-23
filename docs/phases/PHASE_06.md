# Phase 6 - Stage G1 Idea Backlog & Topic Opportunity Workspace

## Objective

Provide one private, durable workflow for original creator ideas: save the idea, collect dated approved research, generate through the existing Win-Engine, associate the saved package, link the verified published video, and eventually expose mature comparable learning. The workspace must never invent demand, search volume, trends, confidence, or performance outcomes.

## Implemented functionality

- Create an idea from creator-supplied topic, notes, format, language, region, visual/background, on-screen text, duration, emotion/intent, and Search/Browse/Existing Audience angles.
- List newest-first with status filtering and bounded limit/offset pagination suitable for more than 100 records.
- Inspect complete idea details, lifecycle associations, angles, visual plan, latest valid evidence, older research history, public result publication dates, and personal-evidence state.
- Update only creator-approved fields or lifecycle status.
- Append an immutable research snapshot using the existing approved YouTube Data API research service.
- Generate a package with the existing structured brief, generator, quality gate, retention assistant, and History system.
- Automatically record the generated `analysis_run_id` and automatically associate a verified linked owned video.
- Mark scripted, mark published only when a verified link exists, archive, restore, and open the generated package in History.
- Preserve an idea if its generated History run is explicitly deleted, returning it to `scripted` instead of deleting creator input.

## Architecture changes

- `analysis/idea_workspace.py` owns creator-input assembly, safe evidence serialization, transparent opportunity explanation, and approved generator-payload rehydration.
- `HistoryStore` remains the single persistence boundary and now owns idea CRUD, immutable snapshots, generation association, and published-link association.
- Existing `ResearchService`, `build_creator_brief`, `generate_seo_suggestions`, `analysis_runs`, `published_video_links`, and cohort evidence rules are reused directly.
- `pages/ideas.js` is a native ES module following the extracted static frontend architecture. It does not add a framework or second frontend server.
- The existing Creator workflow and History remain unchanged and authoritative.

## API changes

- `POST /api/ideas` creates a validated idea.
- `GET /api/ideas?status=&limit=&offset=` returns bounded, newest-first pagination and total count.
- `GET /api/ideas/{id}` returns the detail required by the Ideas panel.
- `PATCH /api/ideas/{id}` changes only creator-approved fields and valid statuses.
- `POST /api/ideas/{id}/research` runs approved research and appends a dated snapshot.
- `POST /api/ideas/{id}/generate` reuses valid current research or collects it when absent, invokes the existing generator, and records the History association.

All routes use the application's existing same-origin boundary, rate limiting, normalized errors, request IDs, and security headers. No YouTube write route or automatic publishing action was added.

## Database changes

Schema version advances from 3 to 4 through the existing verified online-backup-first migration system.

`content_ideas` contains the roadmap-specified fields: `id`, `topic`, `notes`, `format`, `language`, `region`, `visual_or_background`, `on_screen_text`, `target_duration_seconds`, `emotion_or_intent`, `search_angle`, `browse_angle`, `audience_angle`, `evidence_json`, `status`, `analysis_run_id`, `published_video_link_id`, `created_at`, and `updated_at`.

Status is constrained to `idea`, `scripted`, `package_generated`, `published`, or `archived`. Foreign keys to History and published links use `ON DELETE SET NULL`, while explicit History deletion also returns generated/published ideas to `scripted`.

`content_idea_research_snapshots` stores immutable `content_idea_id`, capture time, and evidence JSON. Indexes cover status, creation time, format/language/region, and idea research capture time. Existing rows are not rewritten or deleted.

## Frontend changes

The sidebar now includes Ideas Workspace. The page contains:

- status filter, result count, previous/next pagination, and refresh;
- original-idea creation form;
- cards with topic, lifecycle status, format/language/region, last research date, and transparent opportunity explanation;
- detail panel with Search, Browse, Existing Audience, visual, text, duration, package, and published-link information;
- dated public research, publication dates, captured view counts, and personal-evidence state;
- explicit Research, Generate package, Mark scripted, Mark published, Archive/Restore, and Open History actions;
- honest loading, empty, stale, unavailable, and error states.

Mark published is disabled until the generated package is linked to a verified owned YouTube video. Publishing itself remains manual in YouTube Studio.

## Evidence rules

- Only fields returned by the approved research workflow are persisted; runtime objects, OAuth values, API keys, and tokens are excluded.
- Every research action appends a captured snapshot and updates the current evidence pointer explicitly.
- Editing creator content marks current evidence stale but preserves older snapshots. Status-only changes do not invalidate research.
- The opportunity explanation reports captured relevant-result count, research-query count, possible-outlier count, and observed publication dates.
- Public views are labelled as values at capture time, not projected demand.
- Empty research states that search volume, demand, trend percentage, and confidence are unavailable.
- Personal evidence uses the shared comparable-cohort policy. Fewer than five mature videos remains `insufficient_evidence`; mature results remain historical observations, not causal conclusions.

## Tests

- Backend: 134 passing, including 20 dedicated Stage G1 tests.
- Browser: 31 passing, including Ideas navigation, honest missing evidence, dated research rendering, creation, existing-generator action, and status filtering.
- Total: 165 passing.

Dedicated coverage includes fresh schema/indexes, backup-first v3-to-v4 migration, History preservation, Docker-style reopen persistence, validation, creator-only updates, 105-item pagination, filtering, immutable snapshots, stale evidence, missing data, lifecycle linkage, verified publication association, safe History deletion, evidence sanitization, generator defaults, API contracts, repeated research, and generator wiring. No test requires live Gemini, YouTube, OAuth, or the public internet.

## Security and privacy boundaries

- Application access remains localhost-only.
- Redis remains internal-only.
- YouTube scopes remain `youtube.readonly` and `yt-analytics.readonly`.
- No automatic upload, publishing, metadata change, scraper, paid keyword provider, Ollama, public service, or multi-user feature was added.
- Research snapshots contain only JSON-safe approved research data and creator-visible evidence; secrets and runtime service objects are excluded.
- Production Docker continues to exclude Node, npm, Playwright, Chromium, and Ollama.

## Known limitations

- Research quality and availability depend on the configured YouTube Data API quota and official public metadata.
- The official source does not supply trustworthy monthly keyword volume, so the workspace does not display it.
- Possible-outlier signals are public observations, not viral predictions.
- Idea editing is currently field-based through creation and lifecycle actions; a richer inline editing form can be added only if a future roadmap milestone requires it. The PATCH API already supports all documented creator fields.
- An idea can show mature personal evidence only after enough verified comparable published videos complete the selected snapshot window.
- Publishing and metadata changes remain manual outside the application.

## Acceptance criteria

- Ideas persist across Docker restart through the mounted SQLite database.
- Generated packages and verified published links are stored on the same idea lifecycle.
- Status filtering and bounded pagination work beyond 100 ideas.
- Research refreshes append rather than overwrite historical evidence.
- Missing and stale research are explicit and never converted into guessed demand.
- Search, Browse, Existing Audience, competitor/public evidence, publication dates, and required actions are available in the detail workflow.
- The lifecycle from idea to script, package, verified published link, mature performance, and shared learning is traceable using existing system relationships.
- Existing Phase 1-5 behavior, legacy route, read-only OAuth, and production dependency boundaries remain verified.

## Final status

**Complete for the documented Stage G1 scope.** The next authoritative roadmap work is Stage G2 together with the compatible Stage G5 research explorer foundation, followed by G3/G4.
