# Phase 4 - Generation Quality & Anti-Repetition Engine

## Objective

Improve generated Creator packages through truthfulness, meaningful diversity, evidence discipline, and traceability. Phase 4 is the implementation milestone for roadmap Stage H. It does not replace completed Phases 1-3 or revive the obsolete historical Phases 1-14 plan; that historical material is not present in this repository.

## Scope and completed implementation

- Structured Creator briefs distinguish `creator_supplied`, `inferred`, `unknown`, and `unavailable` for topic, audience, language, format, duration, exact quote, on-screen text, voice-over, visuals, claims, restrictions, intent, constraints, promise, angle, proof, title style, and thumbnail direction.
- Completeness is based on known applicable fields and can no longer default to 100% when important values are unknown.
- A provider-independent local gate normalizes Unicode and validates content before presentation.
- Title candidates are filtered for semantic duplicates, recent generated/published repetition, unsupported claims, generic templates, vague content, and language mismatch. The engine returns fewer choices instead of padding duplicates.
- Gemini receives one normal request. A repairable local-gate failure permits one repair request and one revalidation. Empty/quota/provider failure does not cause a repair request and uses the labelled local fallback.
- Personalization uses the existing shared comparable-evidence policy. Below its mature threshold, the response says `insufficient_evidence` and does not inject a winning pattern.
- Every comparison package carries mechanism, reason, discovery use, evidence trace, trade-offs, local gate state, and generated provenance.
- Explicit Creator selection is saved and later joined to a linked published video. Unknown selection remains unknown; it is never inferred after the fact.
- Tamil validation requires Tamil script for Tamil title/description. Tanglish accepts legitimate Roman Tamil and mixed Tamil/English. Tokenization and similarity checks are Unicode-aware.

## Important files changed

- `win_engine/analysis/creator_brief.py`
- `win_engine/analysis/generation_quality.py`
- `win_engine/analysis/package_builder.py`
- `win_engine/llm/seo_writer.py`
- `win_engine/generation/strategy_engine.py`
- `win_engine/generation/seo_generator.py`
- `win_engine/feedback/migrations.py`
- `win_engine/feedback/history_store.py`
- `win_engine/core/schemas.py`
- `win_engine/api/routes.py`
- `win_engine/api/static/index.html`
- `win_engine/api/static/js/pages/creator.js`
- `win_engine/api/static/js/state.js`
- `win_engine/api/static/js/app.js`
- `tests/test_phase4_generation_quality.py`
- `tests/browser/fixtures.py`
- `tests/browser/test_critical_workflows.py`

## Database changes

Schema version is 3. The backup-first v2-to-v3 migration additively creates `analysis_package_selections` with one selection per analysis run, a foreign key with cascade deletion, server-known package ID, selected package JSON, quality-gate JSON, creator source, and selection/update timestamps. It neither rewrites nor deletes `analysis_runs`. Integrity and foreign-key checks pass.

## API changes

- `AnalyzeRequest` accepts optional duration, exact quote, on-screen text, voice-over, visual requirements, factual claims, claim restrictions, creator intent, and content constraints.
- `AnalyzeResponse` returns `history_run_id`, `generation_quality`, `personalization`, and `generation_trace`.
- `PUT /api/history/runs/{run_id}/selection` accepts only `{ "package_id": "..." }`. The server resolves metadata from the saved generation response and rejects invented IDs.
- History list/detail and linked-video reports expose explicit package-selection and association state.

## Frontend changes

The existing eight Creator stages remain. Advanced Brief adds the Phase 4 fields and renders backend provenance. Candidate cards are not padded. Clicking Select records the chosen server package in History, shows saving/saved/error state, blocks duplicate clicks, and never writes to YouTube. History labels known versus unknown choice and shows selected-versus-uploaded attribution.

## Quality-gate rules

The local gate checks exact-quote fidelity, unsupported events/relationships/outcomes/evidence, semantic and historical title similarity, generic template leakage, description presence and tag-list contamination, voice-over contradictions, focused tags, duplicate/excess hashtags, required `shorts`, `yt`, `youtube shorts`, and `viral shorts` tags for Shorts, Tamil/Tanglish validity, and Unicode normalization. Results contain structured codes, fields, severity, messages, accepted candidates, rejected candidates, warnings, rule version, and pass/fail state.

## Evidence and attribution rules

Personal evidence is used only when the existing Stage C policy marks the comparable cohort mature. The trace contains source, sample size, window, confidence, and whether learning was allowed. A generated primary package, explicitly selected alternative, and actual uploaded YouTube metadata remain separate. If selection was not recorded, attribution is `unknown` even when an uploaded title resembles a candidate.

## Tests

- Backend: 83 passing.
- Browser: 27 passing.
- Total: 110 passing.
- The new backend module contains 30 materially different deterministic briefs plus focused tests for provenance, completeness, diversity, duplicate prevention, fewer-than-three handling, quote/claim safety, Tamil/Tanglish, one repair, quota/empty fallback, evidence thresholds, selection, linkage, and migration integrity.
- Tests require no live Gemini, YouTube, OAuth, or public network.

## Known limitations

- Local semantic similarity is deterministic lexical/sequence analysis, not a paid embedding or keyword-volume service.
- A quality pass does not predict views, impressions, CTR, retention, reach, subscribers, or growth.
- The local fallback is intentionally conservative and may return very few usable alternatives.
- YouTube performance remains video-level evidence; individual tag causality cannot be proven.
- Checklist acknowledgements remain session-local; only explicit generated-package selection is persisted.
- Publishing and all YouTube metadata changes remain manual in YouTube Studio.

## Acceptance criteria and final status

All Phase 4 definition-of-done items in the implementation request are complete: truthful provenance, semantic filtering, honest candidate counts, deterministic quality output, one-repair maximum, quote/claim safeguards, Unicode Tamil/Tanglish handling, mature-evidence enforcement, reason/trade-off traceability, selected-package persistence and History attribution, 30 fixtures, old and new tests, schema integrity, Docker health, localhost-only networking, read-only YouTube permissions, and production dependency separation. Status: **complete**.
