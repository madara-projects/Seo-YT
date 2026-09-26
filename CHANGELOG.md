# Changelog

## 2026-09-26 - Full audit and hardening

- Numbers are reported only when measured: hidden or missing YouTube statistics, unmeasured scores, unrun analytics and failed syncs show as unavailable instead of zero; lifetime upload views are no longer presented as 28-day views, and a failed part of a channel sync is named.
- Outlier scores need real view, subscriber and date data; unscored rows leave the ranking. Chapters are no longer invented, category presets are no longer shown as keyword signals, model tags are measured against the source, per-title quality labels come from the gate, and the creator's script is never rewritten.
- Research: API keys travel in a header, not the URL; the cache and key rotation are shared across requests; results without statistics are not cached; region and language reach YouTube; channel uploads cost 3 units instead of 102; Tamil and other non-Latin scripts are tokenized correctly; demand research fetches public results only.
- Gemini: capped retry waits, a separate cooldown for research calls, a per-request call and time budget, settings validated at startup, and prompt inputs treated as untrusted.
- YouTube channel: PKCE and a granted-scope check on connect, clear reasons when a connection fails, upstream quota and outage errors mapped to 429/502/503, a revoked grant mapped to 401, snapshot windows collected only once YouTube has reported every day in them, and gone or foreign videos dropped from collection.
- History: relinking a package away from a video with collected evidence now asks for confirmation instead of deleting it silently; a relink without a connected channel keeps verified ownership; performance verdicts compare the same window; failed retries no longer hide data; far fewer database queries per page.
- Cloud sync: rows apply one at a time, moved videos keep their evidence, deletions always apply, endless revision churn and thread death are fixed, no network call holds the database lock, pulls are incremental, and deletions no longer block the request.
- Database: schema v10 keeps the losing local edit with each sync conflict, records which channel each upload belongs to, and stores every format in one spelling; migrations run once at startup before background threads, back up once per process, keep the newest ten backups, and switch to WAL afterwards; a database that fails to prepare reports "degraded" health instead of failing every request, and the collector and cloud sync still start and retry it.
- Learning evidence: every spelling of a format ("Short", "YouTube Shorts", "YouTube Short quote video") is stored and filtered as one value, so Shorts made from the Create page count toward learning; Demand's "Long form" matches every known non-Short format; cohort queries apply every evidence rule; re-running the same script no longer counts its own earlier titles as repetition; Tamil titles are scored by word, not by letter; and a package written in "the video's language" passes the risk filter, refinement and final quality gate like any other.
- Snapshot collection: an outage or unexpected error no longer uses up a window's five attempts; a window is planned only once YouTube has reported all of it; videos verified for another channel are left alone; the Channel page lists only the connected channel's uploads.
- Quota: a cached search is found whichever query led the earlier run; after a failed statistics lookup the next run pays 2 units instead of a new 100-unit search; years and counts are no longer words a result must contain; near-duplicate follow-up searches are skipped; a relink that needs confirmation asks before any YouTube lookup; a script or topic with no words (emoji only) is refused before research. Gemini waits as long as a rate-limited response asks, moves a spent daily quota straight to the backup model, and calls it refused are not counted.
- Generation: one rule decides everywhere whether a video is a Short: its chosen format, then a stated length of up to three minutes, then YouTube's own words ("#shorts", "YouTube Short", "reel") or a standalone quote. "Short ribs" or "in short" no longer turns a tutorial into a Short, and a talk about "lessons" no longer gets Shorts tags. Quoted text becomes the mandatory quote only when the creator supplied or labelled it, or the video is a quote Short, never for a tutorial's button label; visual requirements come only from labelled notes ("Background:", "Visuals:", "B-roll:"); research no longer searches stock "quote concepts" that can mean the opposite of the quote; titles, hashtags and meanings written for test examples are gone; and Tamil, Tanglish and Hindi title and description scores that cannot be measured are reported as not measured instead of a fixed 70.
- Generated copy: fallback titles no longer claim "No Scam", "Real Methods That Work" or a fixed year, and the fallback description no longer claims a walkthrough; emoji variation marks and stray joiners no longer end up in tags or suggestions; Hindi sources ground research concepts; creator chapter lists are validated.
- Safety: DEBUG logging never prints OAuth tokens, client secrets or API keys; every spelling of a record id shares one rate-limit budget, on the current and the upgraded FastAPI alike; allowed hosts may carry a port; a malformed Origin is refused rather than failing; closed experiments refuse new assignments, removals and comparisons; deleting a package linked to a video says, before it happens, that the video's collected evidence goes with it; backups are single self-contained files.
- API: Host allow-list, one error envelope with request IDs and security headers on every response, per-route budgets with a stricter one for quota-spending requests, a request-body cap, stricter validation (trimmed text, ISO dates, normalised regions, strict video IDs), POST-only diagnostics, and no access log (the OAuth code travelled in query strings).
- Classic dashboard: correct audit verdicts and markup, escaped output everywhere, no inline event handlers, no external fonts, and full History paging. The older embedded copy at `/dashboard_legacy` was removed; Settings links to the classic dashboard at `/app`. Bulk deletes of more than 100 packages go in batches, the cloud-deletion message says what was actually requested, missing values read "Not available" rather than zero, and a History page that fails to load keeps the pages already shown.
- React interface: the contract changes above, a confirmation step for evidence-deleting relinks, the research-backed tag and pacing cards ported from the removed dashboard, and dead code and dependencies removed. A failed summary shows "Unavailable" instead of empty-library messages, a slow research no longer pulls you back to its page, dialogs return focus to what opened them, and quota costs are stated as they now are (about 3 units for a channel refresh, 1 for the live check).
- Docker: a `.dockerignore` that keeps databases, backups, secrets, tests and docs out of the image; a read-only root filesystem with all capabilities dropped; pinned base images. Dependencies were upgraded to releases without known vulnerabilities.
- Tests are hermetic (no `.env`, no environment keys, no network, a throwaway database) and run with pytest from `requirements-dev.txt`.

## 2026-08-23 - Phase 8 / Stages G3 and G4

- Added immutable Published Video Audit snapshots that separate generated package, explicit creator selection or unknown attribution, and actual owned-video metadata.
- Added deterministic intent-versus-actual comparisons, saved pre-publish quality/retention/Idea/Demand context, current and completed observation windows, provenance-aware findings, summary states, and shared-policy learning candidates.
- Added a structured Experiment Center beside the legacy single-video package-change log, with controlled/observational mode, explicit hypotheses and variables, control/variant definitions, verified linked-video assignments, lifecycle validation, and immutable result snapshots.
- Added conservative metric comparisons over one selected completed 24h/7d/28d window, including sample sizes, means, medians, differences, relative differences, missing metrics, and explicit insufficient/directional/inconclusive/mixed/observational states.
- No statistical significance, causal winner, CTR, retention, or growth value is fabricated. Experiment learning candidates are evidence-gated and are not automatically applied to generation.
- Added Published Audits and Experiments pages through native frontend modules and the existing shared API/error/navigation layer.
- Added 25 backend and 4 browser tests, bringing verification to 179 backend and 38 browser tests (217 total).
- Preserved read-only YouTube OAuth, manual publishing, localhost-only Docker, internal Redis, immutable history, and production dependency boundaries.

## 2026-08-23 - Phase 7 / Stages G2 and G5

- Added private verified public-channel and public-video watchlists with active/archive lifecycle, duplicate protection, filtering, immutable refresh snapshots, and explicit YouTube Data API provenance.
- Added schema-v5 normalized watchlist channel/video records, immutable channel/video snapshots, immutable outlier analyses, and immutable demand-research snapshots through the existing backup-first migration path.
- Added conservative possible-outlier analysis using at least five comparable recent uploads from the same watched channel, with the median, multiplier, sample, capture time, format, and limitations visible. Sparse evidence returns `insufficient_evidence` without a fabricated score.
- Added the Honest Demand Explorer for standalone topics and saved Ideas using approved public research, publication freshness, independent-channel coverage, matching watchlist evidence, and evidence-gated personal observations.
- Added transparent deterministic demand classifications without inventing monthly search volume, CPC, search rank, CTR, causation, or guaranteed outcomes.
- Connected Ideas to Demand research and Demand to the existing Creator generator and History persistence; no parallel generator, History store, YouTube publishing, or metadata-write path was added.
- Added 20 backend and 3 browser tests, bringing verification to 154 backend and 34 browser tests (188 total).
- Preserved localhost-only Docker, internal Redis, read-only YouTube scopes, immutable historical evidence, and production dependency boundaries.

## 2026-08-23 - Phase 6 / Stage G1

- Added the private Ideas Workspace with create, list, status filter, pagination, detail, research, generation, lifecycle, archive, and History navigation actions.
- Added backup-first SQLite schema v4 with `content_ideas`, immutable `content_idea_research_snapshots`, lifecycle foreign keys, and documented indexes.
- Added validated create/list/detail/update/research/generate APIs using existing request-ID, error, rate-limit, and security middleware.
- Reused the existing approved YouTube research, structured Creator brief, package generator, quality gate, retention assistant, History persistence, package association, linked-video system, and shared cohort evidence policy.
- Added transparent dated opportunity explanations based only on observed public result counts, research angles, possible-outlier signals, publication dates, and eligible personal evidence.
- Added stale-evidence protection: changing creator content invalidates current research while preserving every older dated snapshot; status-only changes retain current evidence.
- Added automatic idea-to-History and verified-published-video linkage without any YouTube write permission or publishing action.
- Added 20 backend and 2 browser tests, bringing verification to 134 backend and 31 browser tests (165 total).

## 2026-08-23 - Phase 5

- Added a deterministic, provider-independent hook, first-frame, pacing, exact-quote, and retention-risk analyzer with explicit source provenance.
- Added duration-aware timing only when creator duration exists, with honest relative-stage fallback when exact timing is unavailable.
- Added practical structural alternatives, final-package alignment, and package-selection retention traceability without inventing facts or performance guarantees.
- Added evidence-gated retention learning over verified comparable completed snapshots with real average-view-percentage data; small samples remain `insufficient_evidence` and mature patterns are labelled observational correlation.
- Integrated the assistant into the existing Creator Angle and Decision stages and added saved History/linked-report trace presentation without changing the eight-stage workflow.
- Reused schema-v3 analysis and selection persistence; no database migration or competing History system was required.
- Added 31 backend and 2 deterministic browser tests, bringing verification to 114 backend and 29 browser tests (143 total).
- Preserved read-only YouTube access, manual publishing, localhost-only Docker, internal Redis, and production dependency boundaries.

## 2026-08-23 - Phase 4

- Added truthful structured Creator-brief provenance and optional exact-quote, voice-over, visual, claim, intent, and constraint inputs.
- Added deterministic generation quality, semantic diversity, recent-title repetition, factual-claim, quote-fidelity, Shorts-tag, hashtag, and Unicode language checks.
- Removed duplicate title padding and added an honest fewer-alternatives result.
- Added a maximum-one Gemini repair policy; empty and quota responses continue to the labelled fallback without another generation request.
- Added evidence-policy-aware personalization and package reason, mechanism, trade-off, quality, and provenance traces.
- Added additive SQLite schema v3 package-selection persistence and selected/primary/uploaded History attribution.
- Added a 30-brief deterministic acceptance fixture and Phase 4 backend/browser coverage.
- Preserved localhost-only Docker, internal Redis, read-only YouTube OAuth, manual publishing, and the `/dashboard_legacy` rollback route.
