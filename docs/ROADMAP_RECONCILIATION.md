# Win-Engine OS - Roadmap Reconciliation

Reconciled 2026-08-28 against the repository at `3089f8a` (`audit and experiment page fix`). This is a source-based status report, not a claim that every external API or deployment has been live-verified. The working tree was not changed except for this document.

## 1. Executive Summary

Win-Engine OS is a local-first, single-creator YouTube research, packaging, publishing-decision, and post-publication learning tool. The core Idea -> Research -> Creator -> manual YouTube publish -> Link -> Observe -> Audit/Experiment loop exists. Stages A, G1-G3, G5, H, and I are implemented for their documented scope; G4 is only partly complete because structured comparisons exist but thumbnail/Test & Compare extensions do not.

The current application version is `0.13.0`. `win_engine/feedback/migrations.py` sets the current SQLite schema to version `8`, while several roadmap and phase documents still report versions 3, 5, or 6 and older test totals. That documentation drift is itself a release risk.

The most important boundary is cloud synchronization. Aiven/MySQL synchronization is optional, disabled by default, and is an offline-first mirror for selected History records. It is not a shared transactional database and it does not synchronize the full product. It can carry analysis packages, explicit package selections, one linked-video record, comparable metadata, snapshots, and deletion tombstones. It does not carry Ideas, Watchlist, Demand, Audits, structured Experiments, channel OAuth tokens, settings, or independent channel-sync state.

The code has strong evidence and safety rules (read-only YouTube OAuth, no automatic publishing, immutable observations, 5/10/20 learning thresholds), but production confidence is reduced by three facts: the container was stopped during this inspection, the host test run lacked required Python packages, and Chromium was not installed. The prior `187 backend / 38 browser` claims in the documentation cannot be treated as a current passing verification. The immediate priority is reproducible verification and data-contract hardening, followed by durability/evidence work; cosmetic UI work should follow architecture stabilization.

## 2. Current System State

### Runtime and deployment

- `app.py` creates a FastAPI application and serves the static frontend from the same origin.
- `compose.yaml` runs `win-engine` and Redis. The application is published only as `127.0.0.1:8000:8000`; Redis has no host port. The image is Python 3.11-slim with `curl` and the production requirements only; Node, Playwright, Chromium, and Ollama are not in the image.
- Both services were present but exited when inspected (`docker compose ps -a`), so the source/configuration supports a healthy deployment but this inspection did not establish a currently running container.
- The application lifespan starts the opt-in snapshot collector and cloud-sync worker when enabled and stops both on shutdown. A stopped laptop cannot collect snapshots or run synchronization.

### Configuration and integrations

- `win_engine/core/config.py` loads `WIN_ENGINE_*` settings from `.env`; defaults include bind host `127.0.0.1`, Gemini model `gemini-3.5-flash-lite`, SQLite `win_engine.db`, disabled snapshot collector, and disabled cloud sync.
- Gemini is the only configured AI path in the product contract. The generator has a deterministic, explicitly labelled local fallback.
- `YouTubeChannelService` uses encrypted refresh-token storage and scopes `youtube.readonly` and `yt-analytics.readonly`. Publishing and metadata writes are not requested.
- `YouTubeClient` uses the Data API v3 key pool with key rotation and cache-aware public research. OAuth is used for owned-channel metadata and Analytics.

### Persistence and evidence

- SQLite uses foreign keys, a busy timeout, WAL journal mode, and backup-first versioned migrations. Current schema creation includes History, package selections, published links, performance snapshots, Ideas, Watchlist, Demand, Audits, Experiment Center, and cloud-sync bookkeeping.
- Current display snapshots are kept separate from completed `24h`, `7d`, and `28d` windows. Only verified ownership, comparable metadata, a completed named window, and real metrics qualify for personal evidence.
- Learning thresholds are centralized in `feedback/evidence_policy.py`: 5 samples for an early signal, 10 for moderate evidence, and 20 for strong evidence. These are correlation-labelled and never treated as causal proof.

### Frontend state

- The UI is a static same-origin ES-module application. Native page modules exist for Creator, Ideas, Demand, Watchlist, Audits, and Experiments, with shared API, error, navigation, state, and utility modules.
- Dashboard, History, Analytics, and Settings still render substantial behavior through the 835-line `api/static/js/app.js` compatibility layer. Inline HTML handlers, shared DOM IDs, and compatibility markup remain important contracts.
- The UI modernization is therefore partial: the route/page surface exists, but ownership is not yet consistently modular and the static HTML/CSS layer remains tightly coupled to the legacy renderer.

## 3. Implemented Feature Matrix

| Feature | Roadmap status | Actual status | Implementation location | Test coverage | Notes |
|---|---|---|---|---|---|
| Creator Studio | Complete (Phase 3D) | COMPLETE | `api/static/js/pages/creator.js`, `routes.py`, `generation/` | `test_engine.py`; browser Creator workflows | Eight-stage creator decision flow, manual publish boundary, package selection. |
| Creator Brief | Complete (H) | COMPLETE | `analysis/creator_brief.py`, `core/schemas.py` | `test_engine.py`, Phase 4 tests/browser | Structured provenance, quote/visual/voice-over/claim constraints. |
| Generation | Complete | COMPLETE | `generation/seo_generator.py`, `generation/strategy_engine.py`, `llm/seo_writer.py` | `test_engine.py`, Phase 4 tests | Search/Browse/Returning Audience packages and local fallback. |
| Generation Quality Gate | Complete (H) | COMPLETE for documented rules | `analysis/generation_quality.py`, `llm/seo_writer.py` | `test_phase4_generation_quality.py` | One Gemini repair maximum; no padding or fabricated alternatives. |
| Retention Assistant | Complete (I) | COMPLETE for pre-publish guidance | `analysis/retention_assistant.py`, `analysis/pacing_engine.py` | `test_phase5_retention_assistant.py`, browser | Deterministic hook/first-frame/pacing/quote risk; measured retention remains unavailable until YouTube evidence exists. |
| History | Complete | IMPLEMENTED BUT NEEDS HARDENING | `feedback/history_store.py`, `pages/history.js`, `routes.py` | `test_engine.py`, integrity tests, browser History workflows | Local records are durable; cloud coverage is only a subset of the product. |
| Ideas Workspace | Complete (G1) | COMPLETE for documented scope | `analysis/idea_workspace.py`, `feedback/history_store.py`, `pages/ideas.js` | `test_stage_g1_ideas.py`, browser | Lifecycle, pagination, immutable research, generation/linkage. |
| Idea Research | Complete (G1) | COMPLETE for documented scope | `routes.py`, `ingestion/research_service.py` | `test_stage_g1_ideas.py` | Dated public evidence and stale-evidence protection. |
| Watchlist | Complete (G2) | COMPLETE for documented scope | `feedback/intelligence_store.py`, `pages/watchlist.js` | `test_phase7_intelligence.py`, browser | Public channels/videos and immutable snapshots; not private competitor analytics. |
| Outlier Analysis | Complete (G2) | COMPLETE for documented scope | `scoring/outlier_engine.py`, intelligence store | `test_phase7_intelligence.py` | Same-channel median heuristic; requires at least five comparable uploads. |
| Demand Explorer | Complete (G5) | COMPLETE for documented scope | `analysis/demand_explorer.py`, `routes.py`, `pages/demand.js` | `test_phase7_intelligence.py`, browser | Honest classifications; no invented search volume, CTR, or rank. |
| Published Audits | Complete (G3) | COMPLETE for documented scope | `feedback/audit_experiment_store.py`, `analysis/audit_experiment.py`, `pages/audits.js` | `test_phase8_audit_experiments.py`, browser | Immutable versions separate generated, selected, published, observed states. |
| Experiment Center | Complete (G4) | PARTIALLY COMPLETE | `feedback/audit_experiment_store.py`, `analysis/audit_experiment.py`, `pages/experiments.js` | `test_phase8_audit_experiments.py`, browser | Controlled/observational assignments and comparisons exist; thumbnail draft/Test & Compare import does not. |
| Analytics | Complete | IMPLEMENTED BUT NEEDS HARDENING | `integrations/youtube_channel.py`, `pages/analytics.js`, `history_store.py` | YouTube channel tests, browser fixtures | Read-only live channel/Analytics refresh; API lag and credentials remain external dependencies. |
| Personal Evidence | Complete (C) | IMPLEMENTED BUT NEEDS HARDENING | `feedback/evidence_policy.py`, `channel_learning.py`, `learning_engine.py` | Phase 5 and YouTube tests | Correctly conservative, but small real-channel samples remain display-only. |
| Learning Loop | Complete for evidence policy | IMPLEMENTED BUT NEEDS HARDENING | `feedback/learning_engine.py`, `channel_learning.py`, audit/experiment stores | Phase 5/7/8 tests | No automatic prompt injection or causal winner; richer coach/report is not built. |
| Cloud Sync | New v7/v8 | IMPLEMENTED BUT NEEDS HARDENING | `feedback/cloud_sync.py`, cloud tables, Settings page | `test_cloud_sync.py` (6 methods) | Optional History transport only; disabled/unconfigured by default. |
| Local SQLite persistence | Complete (F) | COMPLETE for local scope | `feedback/migrations.py`, `history_store.py` | Migration/integrity tests | Current schema is 8, not the v6 stated by older docs. |
| Delete/tombstone synchronization | New v8 | IMPLEMENTED BUT NEEDS HARDENING | `history_store.py`, `cloud_sync.py` | Cloud-sync tests and deletion assertions in integrity tests | Local delete queues a revisioned tombstone; full-domain deletion is not synchronized. |
| Conflict handling | Not fully specified | IMPLEMENTED BUT NEEDS HARDENING | `cloud_sync.py` revision/hash upserts | Limited cloud-sync unit coverage | Highest revision wins; no vector clocks, merge UI, or tie-break contract. |
| OAuth | Complete read-only scope | IMPLEMENTED BUT NEEDS HARDENING | `integrations/youtube_channel.py`, OAuth routes | `test_phase1_youtube_channel.py`, browser OAuth states | Token is encrypted locally; a missing/invalid encryption key requires reconnect. |
| YouTube API ingestion | Complete | IMPLEMENTED BUT NEEDS HARDENING | `ingestion/youtube_client.py`, `research_service.py` | Engine/Phase 7/YouTube tests | Key rotation, caching, and public research are implemented; live quota/network behavior needs environment verification. |
| Snapshot collection | Stage G0 | IMPLEMENTED BUT NEEDS HARDENING | `feedback/snapshot_collector.py` | `test_phase2_metadata_collector.py`, browser Settings | Opt-in, single-process, quota-safe collector; disabled by default and unavailable while the process is off. |
| Dashboard | Complete compatibility surface | IMPLEMENTED BUT NEEDS HARDENING | `api/static/index.html`, `app.js`, `pages/dashboard.js` | Browser navigation/smoke workflows | Large shared renderer and legacy route increase regression risk. |
| Settings | Complete compatibility surface | IMPLEMENTED BUT NEEDS HARDENING | `index.html`, `app.js`, `pages/settings.js`, diagnostics routes | Browser Settings/collector states | Shows configuration and diagnostics without secret values; cloud and collector states are operationally dependent. |
| Diagnostics | Complete | IMPLEMENTED BUT NEEDS HARDENING | `/diagnostics`, `/api/settings/status`, `/ready`, `pages/settings.js` | Browser fixture states; no full live integration run here | Generic internal errors preserve request IDs but do not expose root causes to the UI. |
| Backup/restore | Backup-first migration | PARTIALLY COMPLETE | `migrations.py` online backup and `backups/` | `test_phase1_migrations.py` | Verified backup-before-migration exists; user-facing encrypted backup restore is not implemented. |
| Authentication/security | Local access controls | IMPLEMENTED BUT NEEDS HARDENING | `api/app.py`, `middleware.py`, `routes.py`, config | Integrity/browser error/security assertions | Localhost boundary, request IDs, headers, CSP, rate limits, and admin token for reset/readiness; most local API routes rely on localhost trust. |
| PWA/mobile preparation | Planned K3/K4 | NOT STARTED | No service worker, manifest, or mobile client | None | Keep API contracts stable before choosing a mobile architecture. |
| UI architecture/modularization | K1 in progress | PARTIALLY COMPLETE | `app.js`, native `pages/*.js`, `navigation.js`, `state.js` | Browser route/workflow tests | Creator and newer pages are modular; Dashboard/History/Analytics/Settings remain compatibility-owned. |

Features present in code but underrepresented in the older roadmap include thumbnail-resolution intelligence, dynamic niche threshold helpers, content-similarity/differentiation scoring, entity/keyword extraction, first-frame and pacing analysis, automation/publish checklists, session-expansion/pinned-comment suggestions, and the shared request/error/security middleware. These are heuristics or workflow helpers, not proof of reach or a substitute for YouTube Analytics.

## 4. Roadmap Phase Status

Each item below uses exactly one status classification based on source/tests, not on a phase document's assertion alone.

| Stage/phase | Status | Evidence and reconciliation |
|---|---|---|
| A - package-to-video linking | COMPLETE | Owned-video verification, persisted link routes, metadata, and linking tests exist. |
| B - age-based snapshots | IMPLEMENTED BUT NEEDS HARDENING | Current and named windows exist, but collection is manual/opt-in and live API verification was not run here. |
| C - personal learning | IMPLEMENTED BUT NEEDS HARDENING | Central 5/10/20 policy and cohort logic exist; real-channel sample maturity is intentionally sparse. |
| D - legacy package experiments | PARTIALLY COMPLETE | Legacy change log and new structured Center coexist; planned richer thumbnail/Test & Compare workflow is absent. |
| E - Search/Browse/Audience packages | COMPLETE | Generator and Creator surfaces implement the three discovery contexts. |
| F - reliability/test suite | IMPLEMENTED BUT NEEDS HARDENING | Schema 8, WAL, backup-first migration, FK checks, middleware, and tests exist; documentation is stale and current host verification is dependency-blocked. |
| 3D - Creator decision workflow | COMPLETE | Creator module, explicit selection, checklist, provenance, copy/export, and browser workflows exist. |
| G0 - optional snapshot collector | IMPLEMENTED BUT NEEDS HARDENING | Scheduler, due-window planning, retry state, dry-run, and Settings status exist; it is deliberately disabled by default. |
| G1 - Ideas | COMPLETE | Schema v4 work, lifecycle, research snapshots, pagination, generation linkage, and tests exist. |
| G2 - Watchlist | COMPLETE | Schema v5 watchlist and immutable public snapshots/outlier analysis exist. |
| G3 - Published Audits | COMPLETE | Schema v6 audit tables, immutable refresh, provenance, findings, and tests exist; current schema has since advanced to 8. |
| G4 - Experiment Center | PARTIALLY COMPLETE | Structured controlled/observational comparisons are implemented; draft thumbnail/Test & Compare import remains future work. |
| G5 - Demand Explorer | COMPLETE | Dated classifications, public/watchlist/personal evidence boundaries, and Idea integration exist. |
| H - generation quality/anti-repetition | COMPLETE | Quality gate, Unicode/quote/claim checks, diversity, one-repair policy, and selection persistence exist. |
| I - hook/pacing/retention assistant | COMPLETE | Deterministic pre-publish guidance and evidence-labelled retention learning exist. |
| J - evidence service/coach/reports | NOT STARTED | No unified evidence service, personal coach, or weekly report module/API is present. |
| K1 - remaining frontend modularization | PARTIALLY COMPLETE | Native page modules exist, but four major surfaces remain in `app.js`. |
| K2 - performance/accessibility hardening | PARTIALLY COMPLETE | Loading/error/escaping/CSP patterns exist; no comprehensive performance or accessibility acceptance suite is present. |
| K3 - PWA | NOT STARTED | No manifest/service worker/installable shell. |
| K4 - Android decision/client | NOT STARTED | No mobile client or API/mobile decision gate. |
| L1 - quota/cost dashboard | PARTIALLY COMPLETE | Caching, rate limits, API-key rotation, and diagnostics exist; no quota/cost ledger/dashboard. |
| L2 - encrypted backup/restore/quota | PARTIALLY COMPLETE | Online backup-before-migration exists; encrypted user backup, restore, and quota UX do not. |
| L3 - operational diagnostics | PARTIALLY COMPLETE | Health/readiness/settings, collector status, and cloud status exist; no durable event/audit log or complete operator workflow. |

## 5. Newly Added Features Since Previous Roadmap

The current code is materially beyond the earlier A-F roadmap:

1. Phase 4 structured Creator Brief provenance, deterministic generation gate, semantic diversity, one-repair Gemini policy, explicit selected-package persistence, and truthful generated/selected/uploaded attribution.
2. Phase 5 deterministic retention assistant, duration-aware pacing, first-frame and quote guidance, risk maps, practical alternatives, and evidence-gated comparable average-view-percentage learning.
3. Phase 6 Ideas Workspace with immutable dated research, lifecycle, pagination, stale-evidence protection, Creator generation linkage, and publication linkage.
4. Phase 7 Watchlist and Demand Explorer with public snapshots, same-channel outlier baselines, honest classifications, and Idea integration.
5. Phase 8 immutable Published Audits and the structured Experiment Center with verified assignments and evidence-window comparisons.
6. Schema versions 7 and 8 add cloud-sync package mappings, outbox, and deletion tombstones.
7. Native frontend page modules for newer surfaces and shared navigation/state/error utilities.
8. Additional underrepresented helpers: thumbnail intelligence, dynamic thresholds, entity/keyword signals, similarity/differentiation, automation checklists, and session-expansion suggestions.

## 6. Cloud Sync Architecture and Readiness

### What is synchronized

`CloudSyncService._package_payload()` serializes each `analysis_runs` record with its full saved package JSON, the explicit package selection and quality gate, and (when present) one `published_video_links` record. The linked record includes selected/published metadata, ownership state, channel provenance, comparable metadata, and all saved performance snapshots. A remote row is stored in `seo_yt_synced_packages` as a JSON payload keyed by a UUID.

### What is not synchronized

Ideas and their research snapshots, Watchlist channels/videos/snapshots/outlier analyses, Demand research, Published Audit versions/findings, structured Experiment definitions/assignments/results, legacy experiment history not embedded in the package payload, channel OAuth connection/tokens, YouTube channel-sync records, settings, API keys, Gemini configuration, collector state, and operational diagnostics do not go through this service. Channel Analytics can be reflected only indirectly when a linked video's snapshots are inside the package payload.

### Source of truth and another-device behavior

Each laptop's SQLite file remains its local source of truth. Aiven is a transport/mirror of the selected History projection, not an authoritative transactional source. On a new device, a configured `run_once()` pulls remote rows, creates local `analysis_runs` with locally generated IDs, restores selection/link/comparable/snapshot data, and records a local UUID mapping. It can reconstruct the synchronized History projection, but it cannot recreate the rest of the product state or OAuth session. A device must be running for its worker or manual sync request to execute.

### Outbox and idempotency

`_stage_local_packages()` hashes the payload, creates/reuses a `sync_uuid`, increments a revision when content changes, and upserts one `cloud_sync_outbox` row. Push uses MySQL upserts keyed by UUID and revision. Repeating a successful push is idempotent for the same content hash/revision; at most 100 queued deletions and 100 package rows are processed per pass.

### Tombstones and delete behavior

`HistoryStore.delete_analysis_run()` deletes the local run transactionally, clears Idea pointers/status as required, and queues a revisioned `cloud_sync_tombstones` row. Push writes a deleted remote row; pull applies a remote tombstone by clearing the mapped local run and Idea pointers. A tombstone is retained locally so an older active row cannot resurrect. This is correct for synchronized packages, but it does not delete an Idea, Audit, Watchlist item, or Experiment because those objects are outside the sync contract.

### Conflicts, retries, and failures

The conflict policy is last/highest revision wins. Remote active upserts accept an incoming revision when it is greater than or equal to the stored revision; pulls skip a local mapping at an equal or newer revision. A local tombstone blocks active rows after it is seen. There is no vector clock, merge UI, causal ordering, deterministic tie-break for equal concurrent revisions, or per-field merge.

Cloud connection requires host, database, user, password, device ID, and a readable CA certificate. TLS hostname checking is requested through PyMySQL; credentials come from environment settings and are not placed in payload JSON. When disabled/unconfigured, the service returns that state and leaves local History usable. Connection or schema errors set `offline/pending`, retain the outbox/tombstones, and are retried by the next interval/manual run. Cloud retries have interval-based repetition; there is no explicit exponential backoff or durable failure queue for active package rows.

### Readiness judgment

The design is reasonable as an optional offline-first History mirror and is safer than treating GitHub as a database. It is not ready to be called production-grade multi-device synchronization until the scope is explicit and tested. Required work:

- Decide whether the product promises “History only” or full workspace synchronization; document that promise in the UI and guide.
- Add a versioned remote schema/migration contract, payload/schema validation, row-level tenant/workspace identity, and a least-privilege database user.
- Specify equal-revision/concurrent-edit behavior and expose conflicts rather than silently choosing a winner.
- Add end-to-end tests for push/pull/replay, reconnect, duplicate devices, concurrent updates, tombstone ordering, corrupted payloads, remote schema drift, and interrupted passes.
- Add integrity checks and a recoverable cloud export/import path before making remote data authoritative.
- Extend or explicitly exclude Ideas, Watchlist, Demand, Audits, Experiments, and linked-video relationships from the user-facing multi-device promise.
- Add durable sync telemetry (last success, per-item error, retry age, remote/local counts) without exposing credentials.

## 7. History/Data Durability

Local durability is the strongest part of the system. Migrations are backup-first and retry-safe; SQLite online backups are independently reopened and integrity-checked; foreign keys and WAL are enabled on managed connections; deletion is wrapped in `BEGIN IMMEDIATE` and checks `PRAGMA foreign_key_check`. History detail recovers the complete Creator Brief content from package JSON when older `query` columns contain only a truncated value. Package selections, linked metadata, snapshots, audits, and experiment result versions use relational constraints and immutable/append-only patterns where specified.

The durability gap is recovery and replication scope. There is no user-facing encrypted backup/restore workflow, no tested restore from Aiven into a fresh complete workspace, no remote backup retention policy, and cloud synchronization does not include all tables. SQLite remains the authoritative local file, so two devices can legitimately have divergent non-History state.

## 8. Learning System Status

The system intentionally refuses to claim a winner from sparse or unverified data. `verified_ownership()` requires verified channel provenance and timestamp; `mature_snapshot()` accepts only complete named `24h`, `7d`, or `28d` windows with real views; comparable metadata requires format and language. The shared 5/10/20 policy drives cohort analytics, History diagnosis, retention learning, audits, and experiment candidates. Current snapshots are descriptive display data, not mature evidence. Audit and experiment outputs explicitly state that video-level observations cannot isolate title, tag, hook, thumbnail, timing, or causal effects.

This is working as a safety policy, not as a high-volume learning service. The collector is opt-in and disabled by default, YouTube Analytics may be delayed, and the connected channel must accumulate verified comparable videos. Stage J (unified evidence service, coach, and reports) should not loosen thresholds or auto-feed unreviewed conclusions into Gemini.

## 9. Test Health

### Static inventory

The repository contains 190 backend test methods across 11 backend files and 40 browser test methods in `tests/browser/test_critical_workflows.py` (230 methods by static count). The principal mapping is:

- Core generation/brief: `test_engine.py`.
- Migration/integrity/ownership: `test_phase1_migrations.py`, `test_phase1_integrity.py`, `test_phase1_youtube_channel.py`.
- Collector: `test_phase2_metadata_collector.py`.
- Quality gate: `test_phase4_generation_quality.py`.
- Retention/evidence: `test_phase5_retention_assistant.py`.
- Ideas: `test_stage_g1_ideas.py`.
- Watchlist/Demand: `test_phase7_intelligence.py`.
- Audits/Experiment Center: `test_phase8_audit_experiments.py`.
- Cloud transport: `test_cloud_sync.py`.
- Browser navigation and critical workflows: `tests/browser/test_critical_workflows.py` with fixtures.

### Verification performed for this reconciliation

The host command `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_*.py' -v` could not execute the full suite. Five migration/retention groups ran successfully (45 tests reported by unittest), while ten test modules/setup paths errored before their assertions:

| Failure path | Exact failure | Root cause | Application regression? | Windows-specific? | Production impact | Recommended fix |
|---|---|---|---|---|---|---|
| Browser class setup | Playwright executable missing at `C:\Users\moham\AppData\Local\ms-playwright\...\headless_shell.exe` | Chromium is not installed in this host environment | No evidence of app regression; test infrastructure failure | Host-path-specific, not an application Windows defect | None in the production image; blocks browser verification | Provision the pinned browser in a dedicated test environment; do not add it to production Docker. |
| `test_cloud_sync` | `ModuleNotFoundError: No module named 'pydantic'` | Backend requirements are absent from the host interpreter | No assertion ran | No; environment provisioning issue | None directly; cannot verify cloud behavior | Use the repository's locked/declared test environment. |
| `test_engine`, `test_phase4_generation_quality` | `ModuleNotFoundError: No module named 'httpx'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; generation behavior unverified here | Provision requirements and rerun. |
| `test_phase1_integrity`, `test_phase7_intelligence`, `test_stage_g1_ideas` | `ModuleNotFoundError: No module named 'fastapi'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; route behavior unverified here | Provision requirements and rerun. |
| `test_phase1_youtube_channel`, `test_phase2_metadata_collector`, `test_phase8_audit_experiments` | `ModuleNotFoundError: No module named 'pydantic'` | Backend requirements are absent | No assertion ran | No; environment provisioning issue | None directly; integration/collector/audit behavior unverified here | Provision requirements and rerun. |

The prior documentation claim of 187 backend and 38 browser passes versus three failures in each suite is not reproducible from this environment and should be treated as a historical report until rerun from a provisioned environment. No assertion-level production failure could be identified without those dependencies. Python compilation and `git diff --check` were reported in the supplied state, but were not rerun because the task permits only the reconciliation document.

Coverage is strong for deterministic rules and fixture-driven workflows, but weak for live OAuth/YouTube quota behavior, Aiven TLS/schema/reconnect/concurrency, full multi-device reconstruction, restore, Windows process shutdown/restart, and accessibility/performance.

## 10. Architecture Health

The backend is a workable modular monolith, but request handlers in `api/routes.py` (786 lines) instantiate stores and call synchronous external clients directly. `history_store.py` (2,053 lines) is the central persistence seam for History, learning, Ideas, linked videos, snapshots, and deletion. This makes the product coherent for one local user but increases coupling as cloud sync and Stage J grow.

The frontend has a deliberate extraction seam, yet `app.js` (835 lines) still owns Dashboard, History, Analytics, and Settings alongside global state and compatibility rendering. New modules and the legacy renderer can therefore disagree about formatting, loading/error states, and DOM ownership. Static `index.html` also contains inline handlers/styles and mojibake-prone display text, while tests depend on stable IDs and fixture payload shapes.

Cloud sync serializes a projection by reaching through History's schema rather than a versioned domain contract. Learning, audit, and experiment code correctly share evidence policy, but their records are not part of cloud replication. The snapshot collector and cloud worker are single-process background threads; synchronous API calls and in-memory rate limits do not provide a multi-worker job system.

## 11. Technical Debt

| Rank | Debt | Why it matters |
|---|---|---|
| CRITICAL | Full verification is not reproducible from a clean environment | Release status cannot distinguish source regressions from missing dependencies/browser binaries. |
| CRITICAL | Cloud sync scope and authority are ambiguous | Users may expect all workspace data on another laptop while only a History projection is copied. |
| HIGH | `app.js` compatibility ownership | Shared globals and duplicate render paths make UI fixes regress other pages and cause stale/unstable loading states. |
| HIGH | Cloud revision/tombstone conflict contract | Equal concurrent revisions, schema drift, and silent winner selection can lose user intent. |
| HIGH | No complete backup/restore or cloud recovery drill | A local SQLite failure or partial remote pull has no tested end-user recovery path. |
| HIGH | Synchronous external calls in request/background paths | YouTube/MySQL latency can block requests; process shutdown interrupts collection/sync. |
| MEDIUM | Monolithic routes/store and direct SQL | Feature additions require broad changes and make migration/domain boundaries harder to review. |
| MEDIUM | Documentation drift | README/ROADMAP/phase docs disagree on schema and test totals, undermining operational decisions. |
| MEDIUM | Fixture-heavy browser coverage | UI contracts are tested, but live channel, OAuth, cloud, and error timing are not. |
| LOW | Repeated formatting/labels and inline styling | Inconsistent unavailable/error presentation and higher cost of eventual redesign. |

## 12. Remaining Product Work

1. Establish a reproducible test/build/verification environment and resolve any assertion-level failures after dependencies are available.
2. Define and harden the cloud contract (History-only mirror versus full workspace), including recovery and conflict behavior.
3. Make evidence collection and YouTube/API failure states durable, observable, and quota-aware while retaining manual/opt-in boundaries.
4. Build Stage J only after evidence and synchronization are trustworthy: a provenance-backed evidence service, private coach, and weekly report.
5. Extract frontend page ownership and shared components before a broad visual redesign.
6. Add encrypted backup/restore, quota/cost visibility, and operational diagnostics.
7. Decide on PWA/mobile only after the stable same-origin API and offline/data model are explicit.

## 13. Recommended Execution Order

### NEXT 1 - Reproducible release verification

- **Goal:** obtain a clean, repeatable backend and Chromium result and classify assertion failures.
- **Why now:** every later completion claim depends on trustworthy tests.
- **Dependencies:** declared Python requirements, pinned Playwright browser, Docker/host run instructions.
- **Exact work:** add a documented test bootstrap, run all 190 backend and 40 browser methods, capture failure artifacts, verify Python compilation, `git diff --check`, image health, localhost binding, and Redis isolation.
- **Backend/database/API:** no behavior change initially; only add diagnostics if a reproducible failure proves necessary. Do not reset or rewrite the user database.
- **Frontend:** exercise every route and critical DOM contract in Chromium.
- **Tests:** preserve deterministic fixtures and add regression tests only for confirmed failures.
- **Security:** never print `.env`, OAuth tokens, Gemini keys, or cloud passwords in logs/artifacts.
- **Done:** clean-environment results are recorded with exact failures and production impact.
- **Must not change:** schemas, permissions, publishing behavior, or UI design while establishing the baseline.

### NEXT 2 - Data durability and cloud-sync contract

- **Goal:** make multi-device History synchronization predictable and recoverable.
- **Why now:** Aiven is currently only a partial projection and can be misunderstood as a full backup/database.
- **Dependencies:** NEXT 1 and a written History-only/full-workspace decision.
- **Exact work:** version payloads and remote schema, validate payloads, define workspace/device identity and least privilege, specify equal-revision conflicts, add replay/reconnect/concurrency/tombstone tests, and build encrypted export/import plus restore verification.
- **Backend/database/API:** prefer additive tables/columns and backup-first migrations; expose sync contract, last-success/error age, conflicts, and recovery status. Do not make cloud rows authoritative until restore tests pass.
- **Frontend:** explain exactly what syncs and what remains local; show actionable pending/conflict/error states.
- **Tests:** two-device temp databases, duplicate replay, interrupted pass, corrupt payload, remote schema upgrade, deletion ordering, restore.
- **Security:** TLS CA validation, least-privilege credentials, no secrets in payloads, no GitHub-as-database.
- **Done:** documented data coverage, deterministic conflict policy, tested recovery, and truthful UI status.
- **Must not change:** read-only YouTube scopes or automatic publishing.

### NEXT 3 - Evidence collection and YouTube resilience

- **Goal:** make current/24h/7d/28d observations reliable without inflating evidence.
- **Why now:** learning quality is bounded by missing, delayed, or unverified snapshots.
- **Dependencies:** NEXT 1; cloud decision from NEXT 2 for snapshot replication.
- **Exact work:** durable collector attempts/backoff, restart-safe scheduling, quota ledger, OAuth expiry/reconnect states, Analytics lag handling, ownership re-verification, and explicit manual fallback.
- **Backend/database/API:** add only additive attempt/operation records if needed; preserve `complete`/retryable distinctions and 5/10/20 policy.
- **Frontend:** make due, collecting, retryable, unavailable, and complete states distinct; never show guessed metrics.
- **Tests:** mocked API quota/expiry/network/empty rows, restart, due-window idempotency, collector disabled/dry-run, live smoke in a disposable channel fixture.
- **Security:** maintain read-only scopes and redact provider responses.
- **Done:** a stopped process leaves honest pending state; a restarted process retries safely and evidence counts remain correct.
- **Must not change:** maturity thresholds or causal language.

### NEXT 4 - Stage J evidence service, coach, and reports

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

- **Goal:** establish stable page/domain ownership before a visual rewrite.
- **Why now:** `app.js` and the central History store are the main regression multipliers.
- **Dependencies:** NEXT 1-4 contracts; keep existing DOM IDs during migration.
- **Exact work:** extract History, Analytics, Settings, then Dashboard into modules; centralize API/error/loading/date formatting; separate route handlers from service/store interfaces.
- **Backend/database/API:** no endpoint or schema break; introduce small service seams and contract tests.
- **Frontend:** progressive replacement behind the same hash routes and `data-testid`/ID contracts; retain `/dashboard_legacy` until parity is proven.
- **Tests:** page-level browser parity, navigation race/duplicate-click/error tests, API contract tests.
- **Security:** preserve CSP, escaping, request IDs, and same-origin behavior.
- **Done:** one owner per page, no duplicate render path, stable tests, and measurable bundle/latency improvements.
- **Must not change:** user-visible evidence semantics during extraction.

### NEXT 6 - UI modernization and accessibility/performance

- **Goal:** make the stable product compact, clear, responsive, and accessible.
- **Why now:** redesigning before ownership settles would recreate compatibility debt.
- **Dependencies:** NEXT 5 and verified DOM/API contracts.
- **Exact work:** reusable cards/tables/status components, responsive two-pane layouts, focus/keyboard behavior, consistent unavailable/error states, reduced inline CSS, and performance budgets.
- **Backend/API:** no business-logic changes; retain response shapes or version intentionally.
- **Tests:** Chromium visual smoke at target widths, keyboard/focus checks, reduced-motion checks, accessibility audit, no console/page errors.
- **Security:** retain escaping/CSP and avoid third-party script dependencies.
- **Done:** all routes are usable at desktop/mobile widths with stable semantics and no regressions.
- **Must not change:** package generation outputs or evidence wording merely for presentation.

### NEXT 7 - PWA/mobile decision and implementation

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

Structurally obsolete surfaces are the Dashboard/History/Analytics/Settings sections still rendered by `app.js`, the monolithic static `index.html` markup with inline event handlers/styles, and duplicated legacy/new formatting paths. They should be progressively replaced, not redesigned in one destructive pass.

Split order should be History (largest data and cloud-status coupling), Analytics (YouTube refresh/evidence states), Settings (diagnostics/collector/cloud operational states), then Dashboard (cross-page summaries). Creator, Ideas, Demand, Watchlist, Audits, and Experiments already provide the desired native-module pattern and should become references, not be rewritten unnecessarily.

Keep hash routes, stable IDs, `data-testid` attributes, keyboard labels, request-ID error text, and the `/dashboard_legacy` rollback path until parity tests pass. Introduce shared components for cards, tables, chips, empty/loading/error states, date/number formatting, and API requests. The final architecture should have one page owner, one state boundary per workflow, a thin same-origin API client, and backend domain services independent of HTML. Perform visual redesign only after NEXT 5 proves ownership and contracts.

## 15. PWA/Mobile Strategy

There is currently no manifest, service worker, mobile client, or mobile-specific authentication. The present localhost-only deployment is appropriate for a private laptop, not a remotely reachable mobile backend. First decide whether mobile needs read-only package browsing, package generation, full editing, or sync administration. Then define a remote API/auth/threat model and offline conflict contract. A PWA is the lower-cost first option if the same-origin API and cloud contract become stable; a native Android client should wait for evidence that a wrapper cannot meet offline, notifications, or secure credential requirements. Never solve mobile sharing by putting OAuth or Gemini secrets in GitHub or the client.

## 16. Security Boundaries

- YouTube OAuth is limited to `youtube.readonly` and `yt-analytics.readonly`; there is no upload, metadata-edit, or delete scope.
- OAuth refresh tokens are encrypted with Fernet before local SQLite storage; the encryption key remains configuration, not database payload.
- Gemini, YouTube keys, OAuth client credentials, admin token, and Aiven credentials are environment inputs and must remain outside source, logs, screenshots, and cloud payloads.
- Docker binds the app to localhost and keeps Redis internal. CSP, `nosniff`, frame, referrer, permissions, and no-store headers are installed by middleware; request IDs and rate limits are present.
- The admin token protects readiness and database reset in non-development environments. Most local routes rely on the localhost trust boundary rather than a user/session system.
- Aiven uses a CA path and TLS hostname checking in the client, but cloud row isolation, least privilege, remote rotation, and conflict auditing remain future hardening.
- The tool is advisory: publishing and all live YouTube changes remain manual.

## 17. Definition of Done for Each Remaining Phase

| Phase | Done means |
|---|---|
| NEXT 1 / verification | Clean provisioned backend and browser runs, exact failures classified, Docker health/bind/Redis checks recorded, no secrets exposed. |
| NEXT 2 / durability and sync | Scope documented, payload/remote schema versioned, conflicts and tombstones tested, restore/replay proven, UI states truthful. |
| NEXT 3 / evidence | Restart-safe due collection, quota/expiry/error telemetry, ownership and maturity rules preserved, no guessed metrics, tests pass. |
| NEXT 4 / Stage J | Coach/report recommendations trace to eligible evidence, thresholds and limitations visible, no causal or guaranteed claims. |
| NEXT 5 / architecture | One owner per page/domain, shared API/error/state seams, legacy parity tests pass, no endpoint/schema regression. |
| NEXT 6 / UI | Responsive/accessibility/performance acceptance passes across all pages, stable IDs and evidence semantics retained. |
| NEXT 7 / mobile | Explicit platform decision, threat/offline model, versioned API, secure auth, install/reconnect tests, and documented support boundary. |

## 18. Risks and Dependencies

- Google OAuth approval, refresh-token expiry, Analytics processing delay, API quota, and network availability are external dependencies.
- Aiven free-tier availability, idle shutdown, TLS certificate handling, capacity, and credentials are external dependencies; cloud sync must fail soft to local History.
- Two laptops can be offline for different periods; unsynchronized non-History tables will diverge by design.
- The current database is schema 8 while phase docs describe older schemas; any migration must be additive, backup-first, and tested from every supported version.
- Synchronous API calls, one-process workers, and in-memory rate limits are not a distributed production scheduler.
- Browser test execution depends on a pinned Playwright/Chromium installation outside production Docker.
- Existing user data and channel tokens must not be reset or copied into test fixtures.
- UI IDs and fixture payloads are implicit contracts; extraction without parity tests will break navigation or saved workflows.

## 19. Files/Modules Relevant to Each Phase

| Phase/workstream | Primary files/modules |
|---|---|
| Verification/deployment | `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `requirements.txt`, `requirements-browser.txt`, `Dockerfile`, `compose.yaml`, `app.py`, `win_engine/api/app.py` |
| Creator/brief/generation | `win_engine/analysis/creator_brief.py`, `generation/seo_generator.py`, `generation/strategy_engine.py`, `llm/seo_writer.py`, `llm/gemini_client.py`, `api/routes.py`, `api/static/js/pages/creator.js` |
| Quality/retention/evidence | `analysis/generation_quality.py`, `analysis/retention_assistant.py`, `analysis/pacing_engine.py`, `feedback/evidence_policy.py`, `feedback/learning_engine.py`, `feedback/channel_learning.py` |
| History/durability | `feedback/history_store.py`, `feedback/migrations.py`, `api/static/js/pages/history.js`, `api/static/js/app.js`, `tests/test_phase1_integrity.py`, `tests/test_phase1_migrations.py` |
| YouTube/OAuth/Analytics | `integrations/youtube_channel.py`, `ingestion/youtube_client.py`, `ingestion/research_service.py`, `core/config.py`, OAuth/refresh routes, `tests/test_phase1_youtube_channel.py` |
| Snapshot collector | `feedback/snapshot_collector.py`, `api/routes.py`, Settings markup/module, `tests/test_phase2_metadata_collector.py` |
| Ideas/Watchlist/Demand | `analysis/idea_workspace.py`, `analysis/demand_explorer.py`, `feedback/intelligence_store.py`, `api/static/js/pages/ideas.js`, `demand.js`, `watchlist.js`, `tests/test_stage_g1_ideas.py`, `tests/test_phase7_intelligence.py` |
| Audits/Experiments | `analysis/audit_experiment.py`, `feedback/audit_experiment_store.py`, `api/static/js/pages/audits.js`, `experiments.js`, Phase 8 routes/tests |
| Cloud sync | `feedback/cloud_sync.py`, cloud tables in `feedback/migrations.py`, `core/config.py`, `compose.yaml` CA volume, `tests/test_cloud_sync.py` |
| Stage J learning/reporting | `feedback/evidence_policy.py`, `feedback/learning_engine.py`, `feedback/channel_learning.py`, audit/experiment stores (new evidence service/report modules are not present) |
| Architecture extraction | `api/static/js/app.js`, `api/static/js/pages/*.js`, `navigation.js`, `state.js`, `api.js`, `errors.js`, `utils.js`, `api/routes.py`, `feedback/history_store.py` |
| UI modernization | `api/static/index.html`, `api/static/css/app.css`, page modules, browser fixtures/tests |
| Backup/security/mobile | `feedback/migrations.py`, `core/middleware.py`, `core/config.py`, `api/app.py`, `Dockerfile`, `compose.yaml`; no PWA/mobile files currently exist |
