# Phase 8 — Published Audits and Experiment Center

Completed: 23 August 2026  
Application version: `0.13.0`  
Database schema: `6`

## Purpose

Phase 8 completes Roadmap stages G3 and G4 as the post-publication decision loop. It connects saved Ideas, research, generation, quality checks, retention guidance, creator selection, verified published videos, YouTube observations, audits, hypotheses, comparisons, and evidence-gated learning without treating correlation as causation.

## G3 Published Video Audit

Each audit is an immutable snapshot associated with a verified linked-video record and its original analysis run. A refresh appends a version; it never rewrites an older audit.

The audit preserves:

- original creator query and generated primary package;
- explicit selected package and selection trace, or `unknown` when no selection exists;
- actual owned-video title, description, tags, and extracted hashtags, or `unavailable` when metadata has not been captured;
- published format, language, duration when available, timestamps, and field provenance;
- saved generation-quality, rejected-title, package reason/mechanism/trade-off, discovery-surface, personalization, retention, first-frame, pacing, Idea, Demand, and Watchlist context when those historical payloads exist;
- current display snapshots separately from completed 24h/7d/28d observation windows;
- available views, likes, comments, shares, average view percentage, and average-view duration without inventing missing metrics;
- deterministic findings, summary state, evidence state, limitations, and shared-policy learning candidates.

Title, description, tags, and hashtags are compared across three independent states: generated, explicitly selected, and published. Comparison states are exact match, changed, missing, unknown, or unavailable. A generated package is never assumed to be the published package.

Audit summary states are `not_enough_data`, `collecting_evidence`, `observable`, `mature_observation`, `inconclusive`, and `actionable_observation`. These describe evidence availability and maturity—not video success, failure, or causal attribution.

Each finding contains a code, severity, category, explanation, evidence/provenance, evidence state, and recommended interpretation. Learning candidates remain `insufficient_evidence`, `hypothesis_only`, or `mature_comparable_evidence` through the existing 5/10/20 evidence policy.

## G4 Experiment / Comparison Center

The structured Experiment Center is additive to the older single-video `package_experiments` change log. It does not replace or reinterpret those historical records.

An experiment records:

- name, description, explicit hypothesis, and controlled or observational mode;
- one named variable and category;
- exact control and variant definitions;
- primary metric, optional secondary metrics, target/minimum sample, and one comparable 24h/7d/28d window;
- draft/planned/active/paused/completed/cancelled/inconclusive lifecycle;
- dates, notes, timestamps, explicit verified-video assignments, and immutable comparison snapshots.

Only creator-assigned verified linked videos count. Similarity never creates assignment. A video can be a control, variant, or—for observational mode—an observational reference. Duplicate assignments, invalid roles, unverified videos, invalid lifecycle transitions, and new assignments to closed experiments are rejected.

The comparison engine uses only completed snapshots from the experiment's selected window. For every available metric it shows group sample sizes, mean, median, absolute difference, relative difference, and observed direction. It also exposes assigned, eligible, and mature counts plus missing/incomplete evidence.

At least five eligible control and five eligible variant videos are required before a directional result. No p-value or fake statistical significance is produced. Result states are:

- `insufficient_evidence`
- `directional_control`
- `directional_variant`
- `inconclusive`
- `mixed_results`
- `observational_pattern`

Controlled assignment documents creator intent but does not eliminate distribution, topic, audience, timing, or content confounders. Therefore all results remain directional associations, not causal proof. Observational mode is prominently labelled as not a controlled experiment.

Eligible completed comparisons can expose a learning candidate through the shared evidence policy. They are never automatically inserted into future Gemini prompts or applied to generation.

## Database migration

The backup-first v5-to-v6 migration adds four tables:

- `published_video_audits`
- `experiments`
- `experiment_video_assignments`
- `experiment_result_snapshots`

The migration is additive and retry-safe. Existing History, package selections, Ideas, Demand snapshots, Watchlist evidence, OAuth state, linked videos, comparable metadata, performance snapshots, and legacy package experiments are preserved. Foreign keys and indexes enforce ownership and lifecycle relationships.

## APIs

Published Audits:

- `GET /api/audits`
- `GET /api/audits/{link_id}`
- `POST /api/audits/{link_id}/refresh`
- `GET /api/audits/{link_id}/findings`
- `GET /api/audits/{link_id}/evidence`

Experiment Center:

- `POST|GET /api/experiment-center/experiments`
- `GET|PATCH /api/experiment-center/experiments/{experiment_id}`
- `POST /api/experiment-center/experiments/{experiment_id}/assignments`
- `DELETE /api/experiment-center/experiments/{experiment_id}/assignments/{assignment_id}`
- `POST /api/experiment-center/experiments/{experiment_id}/compare`

All endpoints use the existing local access behavior, request IDs, normalized errors, validation, rate limiting, and security headers. No YouTube write action is performed.

## Frontend

The sidebar now includes Published Audits and Experiments.

Published Audits provides linked-video filters, audit/evidence states, publication and Idea context, immutable refresh, a generated/selected/published comparison table, historical intelligence, actual observations, findings, learning candidates, provenance, and limitations.

Experiment Center provides controlled/observational creation, explicit hypotheses and definitions, status/type filters, assignment groups, lifecycle actions, metric comparison tables, result/evidence labels, limitations, and learning candidates. Duplicate-action guards prevent repeated form or comparison requests.

The pages are native ES modules using the shared same-origin API, error, navigation, state, and escaping utilities. Browser tooling remains outside production.

## Evidence and security rules

- Missing values display `UNAVAILABLE`; sparse samples display `INSUFFICIENT EVIDENCE`.
- Current display snapshots are not mature learning evidence.
- YouTube metrics are video-level observations and cannot isolate title, tag, hook, thumbnail, or timing effects.
- Retention curves, competitor private analytics, CTR, search rank, and causal effects are not inferred.
- OAuth remains `youtube.readonly` and `yt-analytics.readonly`; publishing and metadata edits remain manual.
- The app remains bound to `127.0.0.1:8000`, Redis remains internal, and no scraper, paid provider, external AI provider, Node, Playwright, Chromium, or Ollama is added to production.

## Verification

Phase 8 adds 25 backend and 4 deterministic Chromium tests. The repository passes:

- 179 backend tests
- 38 browser tests
- 217 tests total

Coverage includes v5 migration preservation, schema integrity, immutable audit versions, all three metadata states, unknown selection, unavailable data, current/mature evidence, findings and provenance, experiment validation and lifecycle, assignments, duplicate/invalid prevention, insufficient samples, directional control/variant, inconclusive, mixed, observational results, missing windows, immutable results, learning candidates, navigation, detail rendering, duplicate clicks, and unavailable states.

## Known limitations

- YouTube does not expose which metadata element caused a view or retention result.
- A planned experiment in this personal tool is not randomized and cannot remove YouTube distribution or content confounders.
- Five videos per group is a conservative display threshold, not scientific proof.
- Historical traces can show only fields that were persisted at the time.
- Thumbnail/first-frame local draft upload, image review, and creator-visible YouTube Test & Compare import remain future extensions.
- Playlist, cards, end screens, private competitor analytics, retention curves, and unsupported metrics remain unavailable.

## Next milestone

Stage J: unify mature evidence into a private evidence service, personal coach, and weekly report while retaining the same provenance, sample, correlation, and manual-decision boundaries.
