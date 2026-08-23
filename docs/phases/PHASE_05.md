# Phase 5 - Hook, Pacing & Retention Assistant

## 1. Objective

Improve the structure of a video before publishing by identifying opening, first-frame, pacing, quote-presentation, expectation-alignment, reveal, payoff, and loop risks. The assistant provides deterministic guidance and evidence provenance; it does not predict or guarantee retention, views, CTR, reach, subscribers, or growth.

## 2. Scope

Phase 5 implements roadmap Stage I inside the existing eight-stage Creator workflow. It analyzes the submitted script and structured brief, the generated content angle, final validated packages, the explicit package selection, and eligible linked-video history. It returns practical changes and honest structural alternatives without publishing or changing YouTube metadata.

## 3. Architecture changes

- `win_engine/analysis/retention_assistant.py` owns the provider-independent rule engine and rule version `phase5-v1`.
- `seo_generator.py` runs the assistant only after the final Phase 4-validated packages are known, so package alignment refers to the exact response shown to the creator.
- `history_store.py` derives retention learning from the existing linked-video/snapshot system and reuses the shared eligibility policy.
- The complete assistant response is already retained in `analysis_runs.payload_json`; a compact trace is attached to an explicit package selection.
- No parallel History, analytics, or evidence subsystem was introduced.

## 4. API changes

`AnalyzeResponse` additively exposes `retention_assistant`. Its structured value includes rule/provenance metadata, overall risk, opening analysis, first-frame analysis, pacing analysis, quote presentation, risk map, recommendations, alternatives, final-package alignment, retention-learning state, trace, and disclaimer.

No new endpoint was required. Existing analyze, History, selection, and linked-report routes retain their request-ID, normalized-error, rate-limit, and security behavior. Existing clients may ignore the additive response field.

## 5. Database changes

No migration was required and SQLite remains schema version 3. The existing analysis JSON is the canonical saved Phase 5 result. The existing `analysis_package_selections.package_json` stores a small `retention_trace` when a package is selected. Linked-video reports compute the current comparable evidence state from existing verified links and snapshots. This avoids duplicating production data or creating a competing record system.

## 6. Frontend changes

The Creator retains all eight stages. A real Hook, Pacing and Retention Assistant panel appears in the Angle and Decision stages and shows:

- opening score and basis;
- first-frame reading burden and visual-information status;
- short-form or long-form pacing analysis;
- exact-quote preservation and attribution status;
- selected-package alignment;
- structured retention risks;
- prioritized changes and practical alternatives;
- post-publish learning status and sample threshold;
- a provenance guide separating creator-supplied, inferred, heuristic, AI-assisted, post-publish evidence, and unavailable sources.

Changing the explicit package selection immediately updates the displayed alignment after the server confirms persistence. History shows the saved Phase 5 trace and linked reports show the current evidence state. No action publishes or changes a YouTube video.

## 7. Retention-analysis rules

- Opening checks cover subject clarity, specificity/curiosity, generic setup, delayed quote/value, exposition, and unsupported guarantees.
- First-frame checks calculate text burden and a conservative reading estimate. Visual alignment is evaluated only from creator-supplied visual descriptions; otherwise it is unavailable.
- Pacing separates Shorts from long-form, considers supplied duration, estimated speech, repetition, transitions, overload, and late payoff, and never fabricates precise timing.
- Exact quotes remain verbatim. The assistant may recommend splitting or earlier presentation but never silently rewrites or attributes a quote.
- Voice-over contradictions are identified from supplied inputs, while an explicit no-voice-over statement is respected.
- Timing bands are returned only when duration is known. Without duration, the risk map uses relative opening, setup, development, payoff, and ending stages.
- Alternatives are structural generated heuristics, not measured outcomes. They preserve factual constraints and contain no guaranteed-performance language.
- Package alignment is deterministic text alignment against the actual final package IDs, not observed audience behavior.

## 8. Evidence policy

Retention learning reuses the existing comparable-evidence rules. A sample must have verified ownership, comparable format and language, an eligible completed observation window, and real average-view-percentage data. Below five eligible videos, the result is `insufficient_evidence` and no successful pattern is displayed.

At five or more eligible observations, the system can display grouped hook, pacing, and quote-presentation associations using observed median average-view percentage. They are explicitly labelled `observed_correlation_not_causation`. Current/legacy display snapshots, incomplete windows, unverified ownership, missing metrics, and mismatched cohorts do not qualify. Exact retention curves and drop timestamps are unavailable through the current integration and remain unavailable.

## 9. Test coverage

- Backend: 114 passing, including 31 dedicated Phase 5 tests.
- Browser: 29 passing, including traceable Creator rendering and persisted-selection alignment.
- Total: 143 passing.

Coverage includes strong, generic, delayed, unsupported, and missing openings; long/short/unavailable first-frame input; quote burden, exact preservation, conflict, and voice-over cases; short-form and long-form pacing; missing duration and relative stages; no fabricated timing; repeated ideas and late payoff; safe recommendations and alternatives; final package IDs; selection/History traceability; missing performance metrics; four-sample insufficiency; and five-sample observed-correlation behavior. Tests do not call live Gemini, YouTube, OAuth, or the public internet.

## 10. Known limitations

- Scores and risk levels are deterministic heuristics, not experimentally calibrated retention predictions.
- Reading and speech durations are estimates and cannot know the creator's actual edit speed, typography, delivery, or audience.
- The assistant cannot inspect video pixels or audio; it uses only creator-supplied descriptions.
- Official data currently available to this application does not expose a detailed retention curve or exact drop timestamps.
- Observational average-view-percentage associations cannot establish why a video performed differently.
- Evidence remains sparse until at least five comparable mature linked videos exist.

## 11. Security/privacy boundaries

YouTube access remains read-only (`youtube.readonly` and `yt-analytics.readonly`). Publishing and metadata changes remain manual in YouTube Studio. The application remains bound to `127.0.0.1:8000`; Redis has no host-published port. Phase 5 adds no scraping, paid provider, Ollama, background upload, new secret, or external data transfer. Production Docker remains free of Node, npm, Playwright, Chromium, and Ollama.

## 12. Final verification

- Full backend suite: 114 passed.
- Full deterministic Chromium suite: 29 passed.
- Full discovery: 143 passed.
- JavaScript syntax checks: passed.
- SQLite integrity: `ok`; foreign-key violations: zero; schema version: 3.
- Docker services: rebuilt and healthy.
- Application port: localhost-only; Redis: internal-only.
- Production dependency inspection: no Node, npm, Playwright, Chromium, or Ollama.
- YouTube OAuth scopes: read-only.
- `/dashboard_legacy`: retained.

## 13. Acceptance criteria

The Phase 5 functional sections H1-H11 are implemented without replacing the Creator workflow. A 17-word quote receives realistic reading guidance rather than generic curiosity-turn advice; missing visual or timing data is labelled unavailable or expressed with relative stages; exact quotes and truth constraints are preserved; mature evidence thresholds are enforced; selected-package attribution and saved History traces are present; and existing Phase 1-4 behavior remains covered.

## 14. Final status

**Complete for the documented Phase 5 scope.** The capability is a truthful, deterministic pre-publish assistant plus evidence-gated observational learning. It is not a retention predictor, automatic editor, publisher, or substitute for YouTube Studio retention curves.
