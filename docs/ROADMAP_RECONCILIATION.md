# Win-Engine OS - Roadmap Reconciliation

> **Historical record, updated 2026-10-06.** This reconciliation was written on 2026-08-28. Statements that describe the system as it is now were corrected on 2026-10-06; verification results, test counts and judgements dated 2026-08-28 are kept as a record of that day. For current behaviour, read `README.md`, `docs/ROADMAP.md` and `CHANGELOG.md`.
>
> **What changed after this reconciliation's commit `3089f8a` (2026-08-27), up to 2026-10-06** (app version `0.13.0`, schema v12):
> - **2026-08-28, Phase 2C data durability:** schema v9 (`cloud_sync_conflicts`: deterministic equal-revision sync conflict decisions recorded); see [DATA_DURABILITY_SYNC_REPORT.md](DATA_DURABILITY_SYNC_REPORT.md).
> - **2026-09-26, full audit and hardening:** schema v10 (each sync conflict keeps the losing local edit, uploads recorded by channel, one spelling per format); hermetic backend tests run with pytest; `/dashboard_legacy` removed; hardened Docker images.
> - **2026-09-26, one interface at the root:** the React interface (`frontend/`, built into `win_engine/api/static/app/`) is served at `/` and on each page path. The classic dashboard (static HTML/CSS/native ES modules, the eight-stage Creator workflow), its static files and its Chromium tests were removed; `/next/*`, `/app` and `/dashboard_view` redirect (308) to the same page.
> - **2026-09-26, outcome learning:** schema v11 (YouTube quota ledger by bucket, YouTube Studio Test & Compare records, snapshot traffic sources), upload-ready chapters, the Shorts path, Opportunity Score inputs and calibration, and a one-request retention-curve probe.
> - **2026-10-03, AI Shorts:** schema v12 (`ai_short_plans`) and a quote-to-Google-Flow prompt page.
> - **2026-10-05, package audit:** quote titles, honest verdicts, real hashtags, 25 research results per search.

Reconciled 2026-08-28 against the repository at `3089f8a` (`audit and experiment page fix`); current-state statements re-checked against the code on 2026-10-06. This is a source-based status report, not a claim that every external API or deployment has been live-verified. The working tree was not changed except for this document.

## 1. Executive Summary

Win-Engine OS is a local-first, single-creator YouTube research, packaging, publishing-decision, and post-publication learning tool. The core Idea -> Research -> Creator -> manual YouTube publish -> Link -> Observe -> Audit/Experiment loop exists. Stages A, G1-G3, G5, H, and I are implemented for their documented scope; G4 is only partly complete: structured comparisons exist, YouTube Studio Test & Compare records for long videos were added on 2026-09-26, and a thumbnail draft lab does not exist. Since 2026-10-03 an AI Shorts page turns a quote into Google Flow prompts and a lean Shorts package.

The current application version is `0.13.0`. `win_engine/feedback/migrations.py` sets the current SQLite schema to version `12` (it was `8` when this reconciliation was first written; v9-v12 are listed in section 2).

The most important boundary is cloud synchronization. Aiven/MySQL synchronization is optional, disabled by default, and is an offline-first mirror for selected History records. It is not a shared transactional database and it does not synchronize the full product. It can carry analysis packages, explicit package selections, one linked-video record, comparable metadata, snapshots (with their traffic sources since 2026-09-26), YouTube Studio test records (since 2026-09-26), and deletion tombstones. It does not carry Ideas, Watchlist, Demand, Audits, structured Experiments, AI Shorts plans (only their History run), the quota ledger, channel OAuth tokens, settings, or independent channel-sync state.

The code has strong evidence and safety rules (read-only YouTube OAuth, no automatic publishing, immutable observations, 5/10/20 learning thresholds). On 2026-08-28, production confidence was reduced by three facts: the container was stopped during that inspection, the host test run lacked required Python packages, and Chromium was not installed; the then-documented `187 backend / 38 browser` results could not be treated as a passing verification. Since 2026-09-26 the backend tests are hermetic (no `.env`, network or real database) and run with pytest from `requirements-dev.txt`, and the Chromium suite was removed together with the classic dashboard; the React interface has its own type check, Vitest tests and Playwright specs. The 2026-08-28 priority order (verification, then durability/evidence, with UI work after architecture stabilization) is kept in section 13 with each item's status as of 2026-10-06.

## 2. Current System State

### Runtime and deployment

- `app.py` creates the FastAPI application (`win_engine/api/app.py`), which serves the React interface's production build from `win_engine/api/static/app/` at `/` and on each page path, from the same origin as the API. `/` opens `/creator`, or the page a classic `/#hash` bookmark names.
- `compose.yaml` runs `win-engine` and Redis. The application is published only as `127.0.0.1:8000:8000`; Redis has no host port. The image is `python:3.11.16-slim` with the production requirements only, runs as a non-root user (UID 10001) on a read-only root filesystem with a tmpfs `/tmp`, all capabilities dropped and `no-new-privileges`, with `mem_limit` 1g, 2 CPUs and `pids_limit` 256; its health check uses Python's own HTTP client (no curl). Redis `7.4.11-alpine` runs as the `redis` user, read-only, with all capabilities dropped, `no-new-privileges`, `maxmemory` 128mb (`allkeys-lru`), `mem_limit` 256m and `pids_limit` 64. Node, Playwright, Chromium, and Ollama are not in the image; the frontend bundle is built with Node outside Docker.
- On 2026-08-28 both services were present but exited when inspected (`docker compose ps -a`); the 2026-10-06 update did not inspect running containers either, so neither date establishes a currently running container.
- The application lifespan starts the opt-in snapshot collector and cloud-sync worker when enabled and stops both on shutdown; since 2026-09-26 migrations run once at startup before these threads. A stopped laptop cannot collect snapshots or run synchronization.

### Configuration and integrations

- `win_engine/core/config.py` loads `WIN_ENGINE_*` settings from `.env`; defaults include bind host `127.0.0.1`, Gemini model `gemini-3.5-flash-lite`, SQLite `runtime/data/win_engine.db`, 25 YouTube results per search (at most 50, `WIN_ENGINE_YOUTUBE_MAX_RESULTS`), disabled snapshot collector, and disabled cloud sync.
- Gemini is the only configured AI path in the product contract. The generator has a deterministic, explicitly labelled local fallback.
- `YouTubeChannelService` uses encrypted refresh-token storage, PKCE and a granted-scope check on connect (2026-09-26), and scopes `youtube.readonly` and `yt-analytics.readonly`. Publishing and metadata writes are not requested.
- `YouTubeClient` uses the Data API v3 key pool with key rotation and cache-aware public research; keys travel in a header. OAuth is used for owned-channel metadata and Analytics.
- Since 2026-09-26, `feedback/quota_ledger.py` counts every YouTube request per Pacific quota day, per bucket and per key slot (`key1`, `key2`…) or `oauth`: `search.list` has its own bucket (default 100 calls a day, `WIN_ENGINE_YOUTUBE_SEARCH_CALLS_PER_DAY`), every other Data API method draws from a shared bucket (default 10,000 units a day, `WIN_ENGINE_YOUTUBE_UNITS_PER_DAY`; this app's reads cost 1 unit each), and Analytics calls are only counted. Settings shows today's use and research warns at 90%; nothing is blocked.

### Persistence and evidence

- SQLite uses foreign keys, a busy timeout, WAL journal mode, and backup-first versioned migrations (one backup per process, newest ten kept). Current schema creation includes History, package selections, published links, performance snapshots, Ideas, Watchlist, Demand, Audits, Experiment Center, cloud-sync bookkeeping, the YouTube quota ledger, YouTube Studio tests, snapshot traffic sources, and AI Shorts plans.
- Schema history since this reconciliation: v9 (Phase 2C, 2026-08-28) adds `cloud_sync_conflicts` and records deterministic equal-revision cloud-sync conflict decisions; v10 (2026-09-26) keeps the losing local edit with each sync conflict, records which channel each upload belongs to, and stores one spelling per format; v11 (2026-09-26) adds the quota ledger, YouTube Studio tests and snapshot traffic sources; v12 (2026-10-03) adds `ai_short_plans`.
- Current display snapshots are kept separate from completed `24h`, `7d`, and `28d` windows. Only verified ownership, comparable metadata, a completed named window, and real metrics qualify for personal evidence.
- Learning thresholds are centralized in `feedback/evidence_policy.py`: 5 samples for an early signal, 10 for moderate evidence, and 20 for strong evidence. These are correlation-labelled and never treated as causal proof.

### Frontend state

- Since 2026-09-26 the only interface is the React app in `frontend/` (TypeScript, one page component per route in `frontend/src/pages/`), built into `win_engine/api/static/app/`, which is now the only content of `win_engine/api/static/`.
- Navigation (`frontend/src/layouts/navigation.ts`): Studio (Dashboard, Creator, AI Shorts, History), Performance (Channel), Research lab (Ideas, Demand, Audits, Experiments, Watchlist), System (Settings).
- The Creator page is an input screen (choose Short or Long video, then the script/brief) followed by four result tabs: Package, Compare options, Research and insights, Before you publish.
- **Removed 2026-09-26:** the static same-origin ES-module application this section described on 2026-08-28 (native page modules, the 835-line `api/static/js/app.js` compatibility layer, static `index.html`/CSS with inline handlers, the eight-stage Creator workflow), `/dashboard_legacy` (removed in the 2026-09-26 audit) and the classic dashboard at `/app`. `/next/*`, `/app` and `/dashboard_view` now redirect (308) to the same React page.

## 3. Implemented Feature Matrix

Statuses were re-checked on 2026-10-06; locations are relative to `win_engine/` unless they start with `frontend/`.

| Feature | Roadmap status | Actual status | Implementation location | Test coverage | Notes |
|---|---|---|---|---|---|
| Creator Studio | Complete (Phase 3D) | COMPLETE | `frontend/src/pages/Creator.tsx`, `routes.py`, `generation/` | `test_engine.py`; `frontend/e2e/creator.spec.ts`, Creator page tests | Input screen (Short or Long video, then script/brief) and four result tabs; manual publish boundary, package selection. The classic eight-stage flow was removed 2026-09-26. |
| Creator Brief | Complete (H) | COMPLETE | `analysis/creator_brief.py`, `core/schemas.py` | `test_engine.py`, `test_creator_brief.py`, Phase 4 tests | Structured provenance, quote/visual/voice-over/claim constraints. |
| Generation | Complete | COMPLETE | `generation/seo_generator.py`, `generation/strategy_engine.py`, `llm/seo_writer.py` | `test_engine.py`, Phase 4 tests | Search/Browse/Returning Audience packages and local fallback. Since 2026-09-26 a long video's valid chapters (first at 0:00, at least three, each at least 10 s, the final one checked against the stated length) are placed in its descriptions; Shorts get none. |
| Generation Quality Gate | Complete (H) | COMPLETE for documented rules | `analysis/generation_quality.py`, `llm/seo_writer.py` | `test_phase4_generation_quality.py` | One Gemini repair maximum; no padding or fabricated alternatives. Verdicts are RED/YELLOW/GREEN by safety and completeness (2026-10-05). |
| AI Shorts | New (2026-10-03) | COMPLETE for documented scope | `generation/ai_shorts.py`, `generation/flow_prompts.py`, `feedback/ai_shorts_store.py`, `frontend/src/pages/AiShorts.tsx` | `test_ai_shorts_api.py`, `test_ai_shorts_store.py`, `test_flow_prompts.py`, `frontend/e2e/ai-shorts.spec.ts` | The creator types only a quote; one Google Flow (Veo 3.1) prompt per 8-second part (two by default, one to three), Flow steps, a first-frame on-screen text plan and a lean Shorts package with no YouTube Data API research (at most six Gemini calls since 2026-10-10; tags checked against free YouTube search suggestions). Saved as a History run; plans stay on the device. |
| Retention Assistant | Complete (I) | COMPLETE for pre-publish guidance | `analysis/retention_assistant.py`, `analysis/pacing_engine.py`, `feedback/retention_probe.py` | `test_phase5_retention_assistant.py`, `test_retention_probe.py` | Deterministic hook/first-frame/pacing/quote risk. Since 2026-09-26 a linked video's retention curve can be checked with one Analytics request that stores nothing; learning across many curves is not built. |
| History | Complete | IMPLEMENTED BUT NEEDS HARDENING | `feedback/history_store.py`, `frontend/src/pages/History.tsx`, `routes.py` | `test_engine.py`, integrity tests, History page tests | Local records are durable; cloud coverage is only a subset of the product. AI Shorts runs link back to their plan (2026-10-05). |
| Ideas Workspace | Complete (G1) | COMPLETE for documented scope | `analysis/idea_workspace.py`, `feedback/history_store.py`, `frontend/src/pages/Ideas.tsx` | `test_stage_g1_ideas.py`, `frontend/e2e/ideas.spec.ts` | Lifecycle, pagination, immutable research, generation/linkage. |
| Idea Research | Complete (G1) | COMPLETE for documented scope | `routes.py`, `ingestion/research_service.py` | `test_stage_g1_ideas.py` | Dated public evidence and stale-evidence protection. |
| Watchlist | Complete (G2) | COMPLETE for documented scope | `feedback/intelligence_store.py`, `frontend/src/pages/Watchlist.tsx` | `test_phase7_intelligence.py`, Watchlist page tests | Public channels/videos and immutable snapshots; not private competitor analytics. |
| Outlier Analysis | Complete (G2) | COMPLETE for documented scope | `scoring/outlier_engine.py`, intelligence store | `test_phase7_intelligence.py`, `test_outlier_scores.py` | Same-channel median heuristic; requires at least five comparable uploads. |
| Demand Explorer | Complete (G5) | COMPLETE for documented scope | `analysis/demand_explorer.py`, `routes.py`, `frontend/src/pages/Demand.tsx` | `test_phase7_intelligence.py`, `frontend/e2e/demand.spec.ts` | Honest classifications; no invented search volume, CTR, or rank. |
| Published Audits | Complete (G3) | COMPLETE for documented scope | `feedback/audit_experiment_store.py`, `analysis/audit_experiment.py`, `frontend/src/pages/Audits.tsx` | `test_phase8_audit_experiments.py`, `frontend/e2e/audits.spec.ts` | Immutable versions separate generated, selected, published, observed states. |
| Experiment Center | Complete (G4) | PARTIALLY COMPLETE | `feedback/audit_experiment_store.py`, `analysis/audit_experiment.py`, `feedback/studio_tests.py`, `frontend/src/pages/Experiments.tsx` | `test_phase8_audit_experiments.py`, `test_studio_tests.py`, `frontend/e2e/experiments.spec.ts` | Controlled/observational assignments and comparisons exist; since 2026-09-26 up to three packages can be prepared for YouTube Studio's Test & Compare on a long video and the result read in Studio recorded. A thumbnail/first-frame draft lab does not exist. |
| Analytics (Channel page) | Complete | IMPLEMENTED BUT NEEDS HARDENING | `integrations/youtube_channel.py`, `frontend/src/pages/Channel.tsx`, `history_store.py` | YouTube channel tests, Channel page tests | Read-only live channel/Analytics refresh; API lag and credentials remain external dependencies. |
| Personal Evidence | Complete (C) | IMPLEMENTED BUT NEEDS HARDENING | `feedback/evidence_policy.py`, `channel_learning.py`, `learning_engine.py` | Phase 5 and YouTube tests | Correctly conservative, but small real-channel samples remain display-only. Since 2026-09-26 completed windows keep traffic sources and cohorts can be compared by dominant source at 5+ videos. |
| Opportunity Score breakdown and calibration | New (2026-09-26) | IMPLEMENTED BUT NEEDS HARDENING | `analysis/gap_engine.py`, `feedback/score_calibration.py`, `frontend/src/pages/Dashboard.tsx` | `test_opportunity_score_breakdown.py`, `test_score_calibration.py` | Each score shows its inputs, weights, missing-data warnings and confidence, labelled a local heuristic; a Dashboard card compares past scores with published results and says when evidence is insufficient. |
| Learning Loop | Complete for evidence policy | IMPLEMENTED BUT NEEDS HARDENING | `feedback/learning_engine.py`, `channel_learning.py`, audit/experiment stores | Phase 5/7/8 tests, `test_channel_learning.py` | No causal winner. Channel learning reaches the writer only when the evidence level allows it and, since 2026-10-05, only when the top videos beat the rest by a real margin; a coach/report is not built. |
| Cloud Sync | New v7-v10 | IMPLEMENTED BUT NEEDS HARDENING | `feedback/cloud_sync.py`, cloud tables, Settings page | `test_cloud_sync.py` and `test_cloud_sync_*.py` (push, pull, devices, lifecycle, resilience) | Optional History transport only; disabled/unconfigured by default. Since the 2026-09-26 audit rows apply one at a time, pulls are incremental, no network call holds the database lock, and Studio tests and traffic sources travel with their package. AI Shorts plans stay local. |
| Local SQLite persistence | Complete (F) | COMPLETE for local scope | `feedback/migrations.py`, `history_store.py` | Migration/integrity tests | Current schema is 12 (v12, 2026-10-03). |
| Delete/tombstone synchronization | New v8 | IMPLEMENTED BUT NEEDS HARDENING | `history_store.py`, `cloud_sync.py` | Cloud-sync tests and deletion assertions in integrity tests | Local delete queues a revisioned tombstone; deletions always apply since 2026-09-26; full-domain deletion is not synchronized. |
| Conflict handling | v9-v10 | IMPLEMENTED BUT NEEDS HARDENING | `cloud_sync.py` revision/hash upserts, `cloud_sync_conflicts` | Cloud-sync conflict tests | Higher revision wins; equal revisions go to the greater payload hash on every device; each conflict is recorded with the losing local edit (v10) and Settings shows a conflict count. No vector clocks or merge UI. |
| OAuth | Complete read-only scope | IMPLEMENTED BUT NEEDS HARDENING | `integrations/youtube_channel.py`, OAuth routes | `test_phase1_youtube_channel.py`, `test_oauth_return.py` | Token is encrypted locally; PKCE and a granted-scope check since 2026-09-26; a missing/invalid encryption key requires reconnect. |
| YouTube API ingestion | Complete | IMPLEMENTED BUT NEEDS HARDENING | `ingestion/youtube_client.py`, `research_service.py`, `feedback/quota_ledger.py` | Engine/Phase 7/YouTube tests, `test_research_service.py` | Key rotation, caching, public research and (since 2026-09-26) a per-bucket quota ledger; a Short searches only Shorts, a long video searches every length unless its stated length sits well inside YouTube's medium or long band. Live quota/network behavior needs environment verification. |
| Snapshot collection | Stage G0 | IMPLEMENTED BUT NEEDS HARDENING | `feedback/snapshot_collector.py` | `test_phase2_metadata_collector.py`, `test_snapshot_collector.py` | Opt-in, single-process, quota-safe collector; disabled by default and unavailable while the process is off. |
| Dashboard | React page (2026-09-26) | IMPLEMENTED BUT NEEDS HARDENING | `frontend/src/pages/Dashboard.tsx` | Dashboard page tests, `frontend/e2e/pages.spec.ts` | The classic `index.html`/`app.js` dashboard was removed 2026-09-26; the React page includes the score-calibration card. |
| Settings | React page (2026-09-26) | IMPLEMENTED BUT NEEDS HARDENING | `frontend/src/pages/Settings.tsx`, diagnostics routes | Settings page tests | Shows configuration, diagnostics and today's YouTube quota without secret values; cloud and collector states are operationally dependent. |
| Diagnostics | Complete | IMPLEMENTED BUT NEEDS HARDENING | `POST /diagnostics`, `/api/settings/status`, `/ready`, `frontend/src/pages/Settings.tsx` | Route and Settings page tests; no full live integration run here | Generic internal errors preserve request IDs but do not expose root causes to the UI. Diagnostics is POST-only since 2026-09-26. |
| Backup/restore | Backup-first migration | PARTIALLY COMPLETE | `migrations.py` online backup and `runtime/data/backups/` | `test_phase1_migrations.py` | Verified backup-before-migration exists (newest ten kept); user-facing encrypted backup restore is not implemented. |
| Authentication/security | Local access controls | IMPLEMENTED BUT NEEDS HARDENING | `api/app.py`, `routes.py`, config | `test_app_middleware.py`, `test_request_guards.py`, `test_response_headers.py`, integrity tests | Localhost boundary, Host allow-list, request IDs, headers, CSP, rate limits, and admin token for reset/readiness; most local API routes rely on localhost trust. |
| PWA/mobile preparation | Planned K3/K4 | NOT STARTED | No service worker, manifest, or mobile client | None | Keep API contracts stable before choosing a mobile architecture. |
| UI architecture/modularization | K1 in progress | SUPERSEDED (2026-09-26) | `frontend/` (React) | Vitest and Playwright (`frontend/e2e`) | The classic `app.js`/native-module split was removed with the classic dashboard; every page is a React page. |

Features present in code but underrepresented in the older roadmap include thumbnail-resolution intelligence, dynamic niche threshold helpers, content-similarity/differentiation scoring, entity/keyword extraction, first-frame and pacing analysis, automation/publish checklists, session-expansion/pinned-comment suggestions, and the shared request/error/security middleware. These are heuristics or workflow helpers, not proof of reach or a substitute for YouTube Analytics.

## 4. Roadmap Phase Status

Each item below uses exactly one status classification based on source/tests, not on a phase document's assertion alone. Statuses were re-checked on 2026-10-06.

| Stage/phase | Status | Evidence and reconciliation |
|---|---|---|
| A - package-to-video linking | COMPLETE | Owned-video verification, persisted link routes, metadata, and linking tests exist. |
| B - age-based snapshots | IMPLEMENTED BUT NEEDS HARDENING | Current and named windows exist (collected only once YouTube has reported every day in them, with traffic sources since 2026-09-26), but collection is manual/opt-in and live API verification was not run here. |
| C - personal learning | IMPLEMENTED BUT NEEDS HARDENING | Central 5/10/20 policy and cohort logic exist, plus traffic-source cohorts and score calibration (2026-09-26); real-channel sample maturity is intentionally sparse. |
| D - legacy package experiments | PARTIALLY COMPLETE | Legacy change log and new structured Center coexist; YouTube Studio Test & Compare records for long videos were added 2026-09-26; a thumbnail draft workflow is absent. |
| E - Search/Browse/Audience packages | COMPLETE | Generator and Creator surfaces implement the three discovery contexts. |
| F - reliability/test suite | IMPLEMENTED BUT NEEDS HARDENING | Schema 12, WAL, backup-first migration, FK checks, middleware, and tests exist; since 2026-09-26 the backend suite is hermetic and runs with pytest. Live API, cloud and restore behaviour remain unverified by tests. |
| 3D - Creator decision workflow | COMPLETE | React Creator page (2026-09-26): input screen then Package, Compare options, Research and insights, and Before you publish tabs, with explicit selection, checklist, provenance, copy/export, and Playwright specs. |
| G0 - optional snapshot collector | IMPLEMENTED BUT NEEDS HARDENING | Scheduler, due-window planning, retry state, dry-run, and Settings status exist; it is deliberately disabled by default. |
| G1 - Ideas | COMPLETE | Schema v4 work, lifecycle, research snapshots, pagination, generation linkage, and tests exist. |
| G2 - Watchlist | COMPLETE | Schema v5 watchlist and immutable public snapshots/outlier analysis exist. |
| G3 - Published Audits | COMPLETE | Schema v6 audit tables, immutable refresh, provenance, findings, and tests exist; current schema has since advanced to 12. |
| G4 - Experiment Center | PARTIALLY COMPLETE | Structured controlled/observational comparisons are implemented; YouTube Studio Test & Compare preparation and result records were added 2026-09-26 (long videos only); a draft thumbnail lab remains future work. |
| G5 - Demand Explorer | COMPLETE | Dated classifications, public/watchlist/personal evidence boundaries, and Idea integration exist. |
| H - generation quality/anti-repetition | COMPLETE | Quality gate, Unicode/quote/claim checks, diversity, one-repair policy, and selection persistence exist. |
| I - hook/pacing/retention assistant | COMPLETE | Deterministic pre-publish guidance and evidence-labelled retention learning exist; a one-request retention-curve probe was added 2026-09-26. |
| AI Shorts | COMPLETE (2026-10-03) | Quote-only input, per-part Google Flow prompts, Flow steps, first-frame text plan, lean Shorts package saved as a History run, schema v12 and tests exist. |
| J - evidence service/coach/reports | NOT STARTED | No unified evidence service, personal coach, or weekly report module/API is present (re-checked 2026-10-06). |
| K1 - remaining frontend modularization | SUPERSEDED (2026-09-26) | The classic dashboard and `app.js` were removed; every page is a React page in `frontend/src/pages/`. |
| K2 - performance/accessibility hardening | PARTIALLY COMPLETE | Loading/error/escaping/CSP patterns exist and the React dialogs return focus to their opener; no comprehensive performance or accessibility acceptance suite is present. |
| K3 - PWA | NOT STARTED | No manifest/service worker/installable shell. |
| K4 - Android decision/client | NOT STARTED | No mobile client or API/mobile decision gate. |
| L1 - quota/cost dashboard | IMPLEMENTED for YouTube quota (2026-09-26) | Caching, rate limits, API-key rotation, diagnostics, a per-bucket YouTube quota ledger and a Settings card for today's use exist; there is no Gemini cost ledger. |
| L2 - encrypted backup/restore/quota | PARTIALLY COMPLETE | Online backup-before-migration exists (newest ten kept) and quota UX was added 2026-09-26; encrypted user backup and restore do not exist. |
| L3 - operational diagnostics | PARTIALLY COMPLETE | Health/readiness/settings, collector status, cloud status, conflict count and quota use exist; no durable event/audit log or complete operator workflow. |

## 5. Newly Added Features Since Previous Roadmap

The code on 2026-08-28 was materially beyond the earlier A-F roadmap:

1. Phase 4 structured Creator Brief provenance, deterministic generation gate, semantic diversity, one-repair Gemini policy, explicit selected-package persistence, and truthful generated/selected/uploaded attribution.
2. Phase 5 deterministic retention assistant, duration-aware pacing, first-frame and quote guidance, risk maps, practical alternatives, and evidence-gated comparable average-view-percentage learning.
3. Phase 6 Ideas Workspace with immutable dated research, lifecycle, pagination, stale-evidence protection, Creator generation linkage, and publication linkage.
4. Phase 7 Watchlist and Demand Explorer with public snapshots, same-channel outlier baselines, honest classifications, and Idea integration.
5. Phase 8 immutable Published Audits and the structured Experiment Center with verified assignments and evidence-window comparisons.
6. Schema versions 7 and 8 add cloud-sync package mappings, outbox, and deletion tombstones.
7. Native frontend page modules for newer surfaces and shared navigation/state/error utilities (removed 2026-09-26 with the classic dashboard; replaced by the React interface).
8. Additional underrepresented helpers: thumbnail intelligence, dynamic thresholds, entity/keyword signals, similarity/differentiation, automation checklists, and session-expansion suggestions.

Added after this reconciliation (see `CHANGELOG.md`):

9. Schema v9 (Phase 2C, verified 2026-08-28): deterministic equal-revision conflicts recorded; schema v10 (2026-09-26): each conflict keeps the losing local edit, uploads by channel, one spelling per format.
10. The React interface at `/` and on every page path (2026-09-26), replacing the classic dashboard.
11. Upload-ready chapters, the Shorts path, the per-bucket quota ledger, Studio Test & Compare records, traffic-source cohorts, Opportunity Score inputs and calibration, and the retention-curve probe (2026-09-26, schema v11).
12. AI Shorts (2026-10-03, schema v12) and the package audit of quote titles, verdicts, hashtags and research (2026-10-05).

## 6. Cloud Sync Architecture and Readiness

### What is synchronized

`CloudSyncService._package_payload()` serializes each `analysis_runs` record with its full saved package JSON, the explicit package selection and quality gate, and (when present) one `published_video_links` record. The linked record includes selected/published metadata, ownership state, channel provenance, comparable metadata, and all saved performance snapshots (with traffic sources for completed windows since 2026-09-26). Since 2026-09-26 the payload also carries the package's YouTube Studio test records. A remote row is stored in `seo_yt_synced_packages` as a JSON payload keyed by a UUID.

### What is not synchronized

Ideas and their research snapshots, Watchlist channels/videos/snapshots/outlier analyses, Demand research, Published Audit versions/findings, structured Experiment definitions/assignments/results, legacy experiment history not embedded in the package payload, AI Shorts plans (their History run syncs; the plan stays on the device that made it), the YouTube quota ledger, channel OAuth connection/tokens, YouTube channel-sync records, settings, API keys, Gemini configuration, collector state, and operational diagnostics do not go through this service. Channel Analytics can be reflected only indirectly when a linked video's snapshots are inside the package payload.

### Source of truth and another-device behavior

Each laptop's SQLite file remains its local source of truth. Aiven is a transport/mirror of the selected History projection, not an authoritative transactional source. On a new device, a configured `run_once()` pulls remote rows, creates local `analysis_runs` with locally generated IDs, restores selection/link/comparable/snapshot data, and records a local UUID mapping. It can reconstruct the synchronized History projection, but it cannot recreate the rest of the product state or OAuth session. A device must be running for its worker or manual sync request to execute. Since 2026-09-26 pulls are incremental (only recent rows after the first full pull) and rows apply one at a time.

### Outbox and idempotency

`_stage_local_packages()` hashes the payload, creates/reuses a `sync_uuid`, increments a revision when content changes, and upserts one `cloud_sync_outbox` row. Push uses MySQL upserts keyed by UUID and revision, and since 2026-09-26 no cloud call holds the local write lock. Repeating a successful push is idempotent for the same content hash/revision; at most 100 queued deletions and 100 package rows are processed per pass, packages that carry a link first.

### Tombstones and delete behavior

`HistoryStore.delete_analysis_run()` deletes the local run transactionally, clears Idea pointers/status as required, and queues a revisioned `cloud_sync_tombstones` row. Push writes a deleted remote row; pull applies a remote tombstone by clearing the mapped local run and Idea pointers. A tombstone is retained locally so an older active row cannot resurrect, and since 2026-09-26 a deletion always applies (a pushed deletion the cloud did not keep is queued again). This is correct for synchronized packages, but it does not delete an Idea, Audit, Watchlist item, or Experiment because those objects are outside the sync contract.

### Conflicts, retries, and failures

A higher revision wins. Since v9, equal revisions with different content go to the lexicographically greater SHA-256 payload hash, the same rule the cloud upsert applies, so every device converges without depending on clocks; a local tombstone blocks active rows after it is seen. Each conflict is recorded in `cloud_sync_conflicts`, since v10 (2026-09-26) with the losing local edit's payload kept for recovery, and Settings shows the conflict count. There is no vector clock, merge UI, causal ordering, or per-field merge.

Cloud connection requires host, database, user, password, device ID, and a readable CA certificate. TLS hostname checking is requested through PyMySQL; credentials come from environment settings and are not placed in payload JSON. When disabled/unconfigured, the service returns that state and leaves local History usable. Connection or schema errors set `offline/pending`, retain the outbox/tombstones, and are retried later; a failed run backs off before retrying, and a manual run that reaches the cloud ends the wait. There is no durable failure queue for active package rows beyond the outbox.

### Readiness judgment

The design is reasonable as an optional offline-first History mirror and is safer than treating GitHub as a database. It is not ready to be called production-grade multi-device synchronization until the scope is explicit and tested. Required work (status as of 2026-10-06 in brackets where it changed):

- Decide whether the product promises “History only” or full workspace synchronization; document that promise in the UI and guide.
- Add a versioned remote schema/migration contract, payload/schema validation, row-level tenant/workspace identity, and a least-privilege database user.
- Specify equal-revision/concurrent-edit behavior and expose conflicts rather than silently choosing a winner. [Equal revisions resolve deterministically and every conflict is recorded with the losing local edit (v9-v10); there is no merge or review UI beyond the Settings count.]
- Add end-to-end tests for push/pull/replay, reconnect, duplicate devices, concurrent updates, tombstone ordering, corrupted payloads, remote schema drift, and interrupted passes. [Since 2026-09-26 `tests/test_cloud_sync_*.py` cover push, pull, replay, devices, deletion ordering, skipped rows and lost connections against test doubles; no live Aiven run.]
- Add integrity checks and a recoverable cloud export/import path before making remote data authoritative.
- Extend or explicitly exclude Ideas, Watchlist, Demand, Audits, Experiments, AI Shorts plans, and linked-video relationships from the user-facing multi-device promise.
- Add durable sync telemetry (last success, per-item error, retry age, remote/local counts) without exposing credentials.

## 7. History/Data Durability

Local durability is the strongest part of the system. Migrations are backup-first and retry-safe; SQLite online backups are independently reopened and integrity-checked; foreign keys and WAL are enabled on managed connections; deletion is wrapped in `BEGIN IMMEDIATE` and checks `PRAGMA foreign_key_check`. History detail recovers the complete Creator Brief content from package JSON when older `query` columns contain only a truncated value. Package selections, linked metadata, snapshots, audits, and experiment result versions use relational constraints and immutable/append-only patterns where specified.

The durability gap is recovery and replication scope. There is no user-facing encrypted backup/restore workflow (only automatic pre-migration backups, newest ten kept), no tested restore from Aiven into a fresh complete workspace, no remote backup retention policy, and cloud synchronization does not include all tables. SQLite remains the authoritative local file, so two devices can legitimately have divergent non-History state.

## 8. Learning System Status

The system intentionally refuses to claim a winner from sparse or unverified data. `verified_ownership()` requires verified channel provenance and timestamp; `mature_snapshot()` accepts only complete named `24h`, `7d`, or `28d` windows with real views; comparable metadata requires format and language. The shared 5/10/20 policy drives cohort analytics, History diagnosis, retention learning, audits, and experiment candidates. Current snapshots are descriptive display data, not mature evidence. Audit and experiment outputs explicitly state that video-level observations cannot isolate title, tag, hook, thumbnail, timing, or causal effects.

Since 2026-09-26 the learning side also records YouTube Studio Test & Compare results for long videos, keeps traffic sources per completed snapshot window (dominant-source cohorts at 5+ comparable videos), offers a one-request retention-curve probe that stores nothing, and shows Opportunity Score inputs, weights and confidence with a Dashboard calibration card.

This is working as a safety policy, not as a high-volume learning service. The collector is opt-in and disabled by default, YouTube Analytics may be delayed, and the connected channel must accumulate verified comparable videos. Stage J (unified evidence service, coach, and reports) is still not started and should not loosen thresholds or auto-feed unreviewed conclusions into Gemini.

## 9. Test Health

### Current commands (2026-10-06)

- Backend: `pip install -r requirements-dev.txt`, then `python -m pytest tests`. The suite is hermetic (no `.env`, environment keys, network, or real database) since 2026-09-26.
- Frontend, from `frontend/`: `npm ci`, `npx tsc -b --noEmit`, `npx vitest run`, `npm run build`. Playwright (`npx playwright test`, specs in `frontend/e2e`) drives a running app.
- The Chromium suite `tests/browser/` and `requirements-browser.txt` were removed on 2026-09-26 with the classic dashboard.

### Static inventory (2026-08-28, historical)

On 2026-08-28 the repository contained 190 backend test methods across 11 backend files and 40 browser test methods in `tests/browser/test_critical_workflows.py` (230 methods by static count). Many backend test files have been added since; the 2026-08-28 principal mapping, with the browser line updated, was:

- Core generation/brief: `test_engine.py`.
- Migration/integrity/ownership: `test_phase1_migrations.py`, `test_phase1_integrity.py`, `test_phase1_youtube_channel.py`.
- Collector: `test_phase2_metadata_collector.py`.
- Quality gate: `test_phase4_generation_quality.py`.
- Retention/evidence: `test_phase5_retention_assistant.py`.
- Ideas: `test_stage_g1_ideas.py`.
- Watchlist/Demand: `test_phase7_intelligence.py`.
- Audits/Experiment Center: `test_phase8_audit_experiments.py`.
- Cloud transport: `test_cloud_sync.py` (since 2026-09-26 also `test_cloud_sync_*.py`).
- Browser navigation and critical workflows: `tests/browser/test_critical_workflows.py` with fixtures (removed 2026-09-26; the React interface's page tests sit beside each page in `frontend/src/pages/` and its Playwright specs in `frontend/e2e/`).

### Verification performed for this reconciliation (2026-08-28, historical)

The host command `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_*.py' -v` could not execute the full suite. Five migration/retention groups ran successfully (45 tests reported by unittest), while ten test modules/setup paths errored before their assertions:

| Failure path | Exact failure | Root cause | Application regression? | Windows-specific? | Production impact | Recommended fix |
|---|---|---|---|---|---|---|
| Browser class setup | Playwright executable missing at `C:\Users\moham\AppData\Local\ms-playwright\...\headless_shell.exe` | Chromium is not installed in this host environment | No evidence of app regression; test infrastructure failure | Host-path-specific, not an application Windows defect | None in the production image; blocks browser verification | Provision the pinned browser in a dedicated test environment; do not add it to production Docker. |
| `test_cloud_sync` | `ModuleNotFoundError: No module named 'pydantic'` | Backend requirements are absent from the host interpreter | No assertion ran | No; environment provisioning issue | None directly; cannot verify cloud behavior | Use the repository's locked/declared test environment. |
| `test_engine`, `test_phase4_generation_quality` | `ModuleNotFoundError: No module named 'httpx'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; generation behavior unverified here | Provision requirements and rerun. |
| `test_phase1_integrity`, `test_phase7_intelligence`, `test_stage_g1_ideas` | `ModuleNotFoundError: No module named 'fastapi'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; route behavior unverified here | Provision requirements and rerun. |
| `test_phase1_youtube_channel`, `test_phase2_metadata_collector`, `test_phase8_audit_experiments` | `ModuleNotFoundError: No module named 'pydantic'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; integration/collector/audit behavior unverified here | Provision requirements and rerun. |

The prior documentation claim of 187 backend and 38 browser passes versus three failures in each suite was not reproducible from that environment and is a historical report. No assertion-level production failure could be identified without those dependencies. Python compilation and `git diff --check` were reported in the supplied state, but were not rerun because the task permitted only the reconciliation document. The `unittest` command above is historical; use the pytest command in "Current commands".

As assessed on 2026-08-28, coverage was strong for deterministic rules and fixture-driven workflows, but weak for live OAuth/YouTube quota behavior, Aiven TLS/schema/reconnect/concurrency, full multi-device reconstruction, restore, Windows process shutdown/restart, and accessibility/performance. Since 2026-09-26 cloud-sync push/pull/device/resilience behaviour is covered against test doubles; live OAuth, live quota, live Aiven, restore, and accessibility/performance remain uncovered.

## 10. Architecture Health

The backend is a workable modular monolith, but request handlers in `api/routes.py` (786 lines on 2026-08-28, about 1,300 on 2026-10-06) instantiate stores and call synchronous external clients directly. `history_store.py` (2,053 lines on 2026-08-28, about 2,700 on 2026-10-06) is the central persistence seam for History, learning, Ideas, linked videos, snapshots, and deletion. This makes the product coherent for one local user but increases coupling as cloud sync and Stage J grow.

The frontend seam this section described on 2026-08-28 (`app.js` owning Dashboard, History, Analytics, and Settings beside native page modules, static `index.html` with inline handlers) was removed on 2026-09-26. The React interface in `frontend/` has one component per page in `frontend/src/pages/`, one navigation source in `frontend/src/layouts/navigation.ts`, and a typed API client in `frontend/src/api/` (types generated from the backend's OpenAPI schema into `schema.d.ts`); its production build is committed in `win_engine/api/static/app/` because the Docker image does not run Node.

Cloud sync serializes a projection by reaching through History's schema rather than a versioned domain contract. Learning, audit, and experiment code correctly share evidence policy, but their records are not part of cloud replication. The snapshot collector and cloud worker are single-process background threads; synchronous API calls and in-memory rate limits do not provide a multi-worker job system.

## 11. Technical Debt

Ranked on 2026-08-28; status as of 2026-10-06 added where it changed.

| Rank | Debt | Why it matters |
|---|---|---|
| CRITICAL | Full verification is not reproducible from a clean environment | Release status cannot distinguish source regressions from missing dependencies/browser binaries. [Largely addressed 2026-09-26: hermetic pytest suite from `requirements-dev.txt` and documented frontend checks; live API behaviour is still unverified.] |
| CRITICAL | Cloud sync scope and authority are ambiguous | Users may expect all workspace data on another laptop while only a History projection is copied. |
| HIGH | `app.js` compatibility ownership | [Removed 2026-09-26 with the classic dashboard; every page is a React page.] |
| HIGH | Cloud revision/tombstone conflict contract | Schema drift and conflicts without a review UI can lose user intent. [Equal revisions resolve deterministically since v9 (2026-08-28); since 2026-09-26 deletions always apply and the losing local edit is kept with each conflict.] |
| HIGH | No complete backup/restore or cloud recovery drill | A local SQLite failure or partial remote pull has no tested end-user recovery path. |
| HIGH | Synchronous external calls in request/background paths | YouTube/MySQL latency can block requests; process shutdown interrupts collection/sync. |
| MEDIUM | Monolithic routes/store and direct SQL | Feature additions require broad changes and make migration/domain boundaries harder to review. |
| MEDIUM | Documentation drift | Docs written on one date (this one included) disagree with later code; check dates against `CHANGELOG.md`. |
| MEDIUM | Fixture-heavy UI coverage | UI contracts are tested with fixtures and Playwright against a running app, but live channel, OAuth, cloud, and error timing are not. |
| LOW | Repeated formatting/labels and inline styling | [The classic dashboard's inline styling was removed 2026-09-26.] |

## 12. Remaining Product Work

Status as of 2026-10-06:

1. Establish a reproducible test/build/verification environment and resolve any assertion-level failures after dependencies are available. [Done for backend and frontend checks on 2026-09-26; live API, cloud and restore verification remains.]
2. Define and harden the cloud contract (History-only mirror versus full workspace), including recovery and conflict behavior. [Conflict behaviour hardened 2026-09-26; scope decision and recovery remain.]
3. Make evidence collection and YouTube/API failure states durable, observable, and quota-aware while retaining manual/opt-in boundaries. [Quota ledger and warnings done 2026-09-26.]
4. Build Stage J only after evidence and synchronization are trustworthy: a provenance-backed evidence service, private coach, and weekly report. [Not started.]
5. Extract frontend page ownership and shared components before a broad visual redesign. [Superseded 2026-09-26 by the React interface.]
6. Add encrypted backup/restore, quota/cost visibility, and operational diagnostics. [YouTube quota visibility done 2026-09-26; encrypted backup/restore not started.]
7. Decide on PWA/mobile only after the stable same-origin API and offline/data model are explicit. [Not started.]
8. Further future work named since: daily opportunity summaries, a thumbnail/first-frame draft lab, and learning across many retention curves. [Not started.]

## 13. Recommended Execution Order

### NEXT 1 - Reproducible release verification

- **Status (2026-10-06):** largely done. The backend suite is hermetic and runs with `python -m pytest tests` (2026-09-26); the browser suite named below was removed with the classic dashboard, and the React interface is checked with its type check, Vitest, build, and Playwright. Live-environment verification (OAuth, quota, Aiven, image health) remains.
- **Goal:** obtain a clean, repeatable backend and frontend result and classify assertion failures.
- **Why now:** every later completion claim depends on trustworthy tests.
- **Dependencies:** declared Python requirements (`requirements-dev.txt`), the frontend lockfile and a Playwright browser, Docker/host run instructions.
- **Exact work:** add a documented test bootstrap, run the whole backend suite and the frontend checks, capture failure artifacts, verify Python compilation, `git diff --check`, image health, localhost binding, and Redis isolation. (The 2026-08-28 plan named 190 backend and 40 browser methods; those counts are historical.)
- **Backend/database/API:** no behavior change initially; only add diagnostics if a reproducible failure proves necessary. Do not reset or rewrite the user database.
- **Frontend:** exercise every page of the React interface with Playwright (`frontend/e2e`).
- **Tests:** preserve deterministic fixtures and add regression tests only for confirmed failures.
- **Security:** never print `.env`, OAuth tokens, Gemini keys, or cloud passwords in logs/artifacts.
- **Done:** clean-environment results are recorded with exact failures and production impact.
- **Must not change:** schemas, permissions, publishing behavior, or UI design while establishing the baseline.

### NEXT 2 - Data durability and cloud-sync contract

- **Status (2026-10-06):** partly done. Deterministic equal-revision resolution with recorded conflicts (v9, 2026-08-28), plus the losing local edit kept with each conflict (v10), deletions that always apply, incremental pulls and multi-device tests against test doubles (all 2026-09-26) exist. Payload/remote-schema versioning, workspace identity, least privilege, encrypted export/import and restore remain.
- **Goal:** make multi-device History synchronization predictable and recoverable.
- **Why now:** Aiven is currently only a partial projection and can be misunderstood as a full backup/database.
- **Dependencies:** NEXT 1 and a written History-only/full-workspace decision.
- **Exact work:** version payloads and remote schema, validate payloads, define workspace/device identity and least privilege, add replay/reconnect tests against a live database, and build encrypted export/import plus restore verification.
- **Backend/database/API:** prefer additive tables/columns and backup-first migrations; expose sync contract, last-success/error age, conflicts, and recovery status. Do not make cloud rows authoritative until restore tests pass.
- **Frontend:** explain exactly what syncs and what remains local; show actionable pending/conflict/error states.
- **Tests:** two-device temp databases, duplicate replay, interrupted pass, corrupt payload, remote schema upgrade, deletion ordering, restore.
- **Security:** TLS CA validation, least-privilege credentials, no secrets in payloads, no GitHub-as-database.
- **Done:** documented data coverage, deterministic conflict policy, tested recovery, and truthful UI status.
- **Must not change:** read-only YouTube scopes or automatic publishing.

### NEXT 3 - Evidence collection and YouTube resilience

- **Status (2026-10-06):** partly done. The quota ledger (2026-09-26), windows collected only once YouTube has reported every day in them, outages that no longer use up a window's attempts, and mapped revoked-grant/quota/outage errors exist. Restart-safe scheduling and an explicit manual fallback remain to be confirmed.
- **Goal:** make current/24h/7d/28d observations reliable without inflating evidence.
- **Why now:** learning quality is bounded by missing, delayed, or unverified snapshots.
- **Dependencies:** NEXT 1; cloud decision from NEXT 2 for snapshot replication.
- **Exact work:** durable collector attempts/backoff, restart-safe scheduling, OAuth expiry/reconnect states, Analytics lag handling, ownership re-verification, and explicit manual fallback.
- **Backend/database/API:** add only additive attempt/operation records if needed; preserve `complete`/retryable distinctions and 5/10/20 policy.
- **Frontend:** make due, collecting, retryable, unavailable, and complete states distinct; never show guessed metrics.
- **Tests:** mocked API quota/expiry/network/empty rows, restart, due-window idempotency, collector disabled/dry-run, live smoke in a disposable channel fixture.
- **Security:** maintain read-only scopes and redact provider responses.
- **Done:** a stopped process leaves honest pending state; a restarted process retries safely and evidence counts remain correct.
- **Must not change:** maturity thresholds or causal language.

### NEXT 4 - Stage J evidence service, coach, and reports

- **Status (2026-10-06):** not started.
- **Goal:** turn mature, provenance-backed observations into useful private guidance.
- **Why now:** only after evidence and replication are trustworthy.
- **Dependencies:** NEXT 2 and NEXT 3; existing evidence policy is the gate.
- **Exact work:** unified evidence query model, cohort explanations, private coach recommendations, weekly report, and explicit “insufficient evidence” output.
- **Backend/database/API:** use read models/views or additive tables; preserve source IDs, windows, sample sizes, and provenance.
- **Frontend:** a compact evidence dashboard with source links, sample thresholds, limitations, and manual accept/reject actions.
- **Tests:** threshold boundaries, mixed cohorts, stale data, missing metrics, report reproducibility, no prompt injection below policy.
- **Security:** keep reports local and redact tokens/credentials.
- **Done:** every recommendation is traceable to eligible rows and is never presented as a guarantee.
- **Must not change:** Gemini-only provider rule, manual publishing, or evidence policy.

### NEXT 5 - Backend and frontend architecture extraction

- **Status (2026-10-06):** the frontend half is superseded: the classic dashboard, `app.js`, its hash routes and `/dashboard_legacy` were removed on 2026-09-26 and every page is a React page. The backend half (service seams between route handlers and stores) remains future work.
- **Goal:** establish stable domain ownership in the backend.
- **Why now:** `api/routes.py` and the central History store are the main regression multipliers.
- **Dependencies:** NEXT 1-4 contracts.
- **Exact work:** centralize API/error handling and separate route handlers from service/store interfaces.
- **Backend/database/API:** no endpoint or schema break; introduce small service seams and contract tests.
- **Frontend:** none required; the React interface already has one owner per page.
- **Tests:** API contract tests and the existing frontend checks.
- **Security:** preserve CSP, escaping, request IDs, and same-origin behavior.
- **Done:** one owner per domain, stable tests, and no endpoint regression.
- **Must not change:** user-visible evidence semantics during extraction.

### NEXT 6 - UI modernization and accessibility/performance

- **Status (2026-10-06):** UI modernization done with the React interface (2026-09-26: full-width pages, a sidebar that folds into an icon rail, theme switching). An accessibility audit and performance budgets remain.
- **Goal:** make the product accessible and fast at every width.
- **Why now:** the interface is now stable enough to set acceptance criteria.
- **Dependencies:** the React interface and verified API contracts.
- **Exact work:** focus/keyboard behavior checks, consistent unavailable/error states, and performance budgets.
- **Backend/API:** no business-logic changes; retain response shapes or version intentionally.
- **Tests:** Playwright smoke at target widths, keyboard/focus checks, reduced-motion checks, accessibility audit, no console/page errors.
- **Security:** retain escaping/CSP and avoid third-party script dependencies.
- **Done:** all routes are usable at desktop/mobile widths with stable semantics and no regressions.
- **Must not change:** package generation outputs or evidence wording merely for presentation.

### NEXT 7 - PWA/mobile decision and implementation

- **Status (2026-10-06):** not started.
- **Goal:** provide an intentional mobile experience only after the local/cloud model is settled.
- **Why now:** mobile offline semantics depend on whether the cloud layer is History-only or full workspace.
- **Dependencies:** NEXT 2 and NEXT 5; stable API/auth/session decision.
- **Exact work:** choose responsive PWA versus separate Android client, define offline queue/conflicts, add manifest/service worker/install/update UX, then evaluate native wrapper only if justified.
- **Backend/database/API:** version APIs, add device/session capabilities only with a threat model; do not expose localhost-only assumptions directly to the Internet.
- **Frontend/tests:** offline/read-only states, sync queue, reconnect, install/update, mobile browser coverage.
- **Security:** explicit remote authentication and secret storage design before leaving localhost.
- **Done:** a documented decision, threat model, offline contract, and tested installable client.
- **Must not change:** local single-user safety boundaries without an explicit product decision.

## 14. Future UI Modernization Strategy

**Superseded on 2026-09-26.** The 2026-08-28 strategy (progressively replacing the Dashboard/History/Analytics/Settings sections rendered by `app.js` and the static `index.html`, keeping hash routes and the `/dashboard_legacy` rollback path until parity tests passed) no longer applies: the classic dashboard, its static files, its Chromium tests and `/dashboard_legacy` were removed, and the React interface in `frontend/` is served at `/` and on every page path. Old addresses (`/next/*`, `/app`, `/dashboard_view`, classic `/#hash` bookmarks) open the same React page. Remaining UI work is the accessibility and performance acceptance in NEXT 6.

## 15. PWA/Mobile Strategy

There is currently no manifest, service worker, mobile client, or mobile-specific authentication. The present localhost-only deployment is appropriate for a private laptop, not a remotely reachable mobile backend. First decide whether mobile needs read-only package browsing, package generation, full editing, or sync administration. Then define a remote API/auth/threat model and offline conflict contract. A PWA is the lower-cost first option if the same-origin API and cloud contract become stable; a native Android client should wait for evidence that a wrapper cannot meet offline, notifications, or secure credential requirements. Never solve mobile sharing by putting OAuth or Gemini secrets in GitHub or the client.

## 16. Security Boundaries

- YouTube OAuth is limited to `youtube.readonly` and `yt-analytics.readonly`; there is no upload, metadata-edit, or delete scope. Connect uses PKCE and checks the granted scopes.
- OAuth refresh tokens are encrypted with Fernet before local SQLite storage; the encryption key remains configuration, not database payload.
- Gemini, YouTube keys, OAuth client credentials, admin token, and Aiven credentials are environment inputs and must remain outside source, logs, screenshots, and cloud payloads.
- Docker binds the app to localhost and keeps Redis internal; both containers run unprivileged on read-only filesystems with all capabilities dropped. CSP, `nosniff`, frame, referrer, permissions, and no-store headers are installed by middleware; a Host allow-list, request IDs and rate limits are present.
- The admin token protects readiness and database reset in non-development environments. Most local routes rely on the localhost trust boundary rather than a user/session system.
- Aiven uses a CA path and TLS hostname checking in the client, but cloud row isolation, least privilege, remote rotation, and conflict auditing remain future hardening.
- The tool is advisory: publishing and all live YouTube changes remain manual.

## 17. Definition of Done for Each Remaining Phase

| Phase | Done means |
|---|---|
| NEXT 1 / verification | Clean provisioned backend and frontend runs, exact failures classified, Docker health/bind/Redis checks recorded, no secrets exposed. |
| NEXT 2 / durability and sync | Scope documented, payload/remote schema versioned, conflicts and tombstones tested, restore/replay proven, UI states truthful. |
| NEXT 3 / evidence | Restart-safe due collection, quota/expiry/error telemetry, ownership and maturity rules preserved, no guessed metrics, tests pass. |
| NEXT 4 / Stage J | Coach/report recommendations trace to eligible evidence, thresholds and limitations visible, no causal or guaranteed claims. |
| NEXT 5 / architecture | One owner per backend domain, shared API/error seams, no endpoint/schema regression. (The frontend half was superseded on 2026-09-26.) |
| NEXT 6 / UI | Responsive/accessibility/performance acceptance passes across all pages, evidence semantics retained. |
| NEXT 7 / mobile | Explicit platform decision, threat/offline model, versioned API, secure auth, install/reconnect tests, and documented support boundary. |

## 18. Risks and Dependencies

- Google OAuth approval, refresh-token expiry, Analytics processing delay, API quota, and network availability are external dependencies.
- Aiven free-tier availability, idle shutdown, TLS certificate handling, capacity, and credentials are external dependencies; cloud sync must fail soft to local History.
- Two laptops can be offline for different periods; unsynchronized non-History tables (and AI Shorts plans) will diverge by design.
- The current database is schema 12; any migration must be additive, backup-first, and tested from every supported version.
- Synchronous API calls, one-process workers, and in-memory rate limits are not a distributed production scheduler.
- Playwright runs depend on a browser installed outside production Docker and on a running app.
- Existing user data and channel tokens must not be reset or copied into test fixtures.
- API response shapes are contracts for the React interface, whose client types them in `frontend/src/api/`; a backend change that breaks a shape breaks the page that reads it.

## 19. Files/Modules Relevant to Each Phase

Paths updated on 2026-10-06; the classic `api/static/js/`, `api/static/index.html` and `api/static/css/` files listed on 2026-08-28 no longer exist.

| Phase/workstream | Primary files/modules |
|---|---|
| Verification/deployment | `README.md`, `docs/ROADMAP.md`, `CHANGELOG.md`, `requirements.txt`, `requirements-dev.txt`, `frontend/package.json`, `frontend/playwright.config.ts`, `Dockerfile`, `compose.yaml`, `app.py`, `win_engine/api/app.py` |
| Creator/brief/generation | `win_engine/analysis/creator_brief.py`, `generation/seo_generator.py`, `generation/strategy_engine.py`, `generation/expansion_engine.py` (chapters), `llm/seo_writer.py`, `llm/gemini_client.py`, `api/routes.py`, `frontend/src/pages/Creator.tsx` |
| AI Shorts | `generation/ai_shorts.py`, `generation/flow_prompts.py`, `feedback/ai_shorts_store.py`, `frontend/src/pages/AiShorts.tsx`, `tests/test_ai_shorts_api.py`, `tests/test_ai_shorts_store.py`, `tests/test_flow_prompts.py` |
| Quality/retention/evidence | `analysis/generation_quality.py`, `analysis/retention_assistant.py`, `analysis/pacing_engine.py`, `feedback/evidence_policy.py`, `feedback/learning_engine.py`, `feedback/channel_learning.py`, `feedback/retention_probe.py`, `feedback/score_calibration.py` |
| History/durability | `feedback/history_store.py`, `feedback/migrations.py`, `frontend/src/pages/History.tsx`, `tests/test_phase1_integrity.py`, `tests/test_phase1_migrations.py` |
| YouTube/OAuth/Analytics | `integrations/youtube_channel.py`, `ingestion/youtube_client.py`, `ingestion/research_service.py`, `feedback/quota_ledger.py`, `core/config.py`, OAuth/refresh routes, `frontend/src/pages/Channel.tsx`, `tests/test_phase1_youtube_channel.py` |
| Snapshot collector | `feedback/snapshot_collector.py`, `api/routes.py`, `frontend/src/pages/Settings.tsx`, `tests/test_phase2_metadata_collector.py`, `tests/test_snapshot_collector.py` |
| Ideas/Watchlist/Demand | `analysis/idea_workspace.py`, `analysis/demand_explorer.py`, `feedback/intelligence_store.py`, `frontend/src/pages/Ideas.tsx`, `Demand.tsx`, `Watchlist.tsx`, `tests/test_stage_g1_ideas.py`, `tests/test_phase7_intelligence.py` |
| Audits/Experiments | `analysis/audit_experiment.py`, `feedback/audit_experiment_store.py`, `feedback/studio_tests.py`, `frontend/src/pages/Audits.tsx`, `Experiments.tsx`, Phase 8 routes/tests, `tests/test_studio_tests.py` |
| Cloud sync | `feedback/cloud_sync.py`, cloud tables in `feedback/migrations.py`, `core/config.py`, `compose.yaml` CA volume, `tests/test_cloud_sync.py`, `tests/test_cloud_sync_*.py` |
| Stage J learning/reporting | `feedback/evidence_policy.py`, `feedback/learning_engine.py`, `feedback/channel_learning.py`, audit/experiment stores (new evidence service/report modules are not present) |
| Architecture extraction | `api/routes.py`, `feedback/history_store.py` (the frontend half was superseded on 2026-09-26; see `frontend/src/`) |
| UI | `frontend/src/pages/`, `frontend/src/layouts/navigation.ts`, `frontend/src/api/`, `frontend/e2e/`; built into `win_engine/api/static/app/` |
| Backup/security/mobile | `feedback/migrations.py`, `api/app.py` (middleware), `core/config.py`, `Dockerfile`, `compose.yaml`; no PWA/mobile files currently exist |
