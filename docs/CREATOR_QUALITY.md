# Creator quality and evidence

This document replaces the overlapping dated Creator audit reports. Raw audit responses, screenshots and test logs remain under `runtime/`; project READMEs, the user guide, roadmap and changelog are retained.

## Quality contract

- Preserve creator source meaning and exact quotes. A silent quote description may add one concise, source-grounded contextual sentence, without inventing backstory, advice or outcomes.
- Keep the creator-requested `yt` and `shorts` tags for Shorts. Topic tags must be relevant, distinct and unambiguous. Autocomplete is an observed prediction, not search volume or a ranking guarantee.
- Separate retrieved results from results that pass relevance checks. When evidence is absent, say so rather than manufacture a competitor or performance claim.
- Local quality checks and title-writing heuristics are not measured CTR, views or search demand.
- Preserve UTF-8 History data. Do not publish or change YouTube videos as part of generation.

## Existing audited safeguards

Voice-over aliases normalize to the UI contract; one-letter words count in reading estimates; retention subgroups require five samples; retry diagnostics cover model switches and distinguish request-wide calls from writer calls. Cloud synchronization reports sanitized error codes and stages, retries transient connection establishment, and retains its durable queue. TLS checks remain enabled.

## Implemented changes

Branch: `fix/creator-quality-and-evidence`.

- The writer returns separate `description_context` and literal `description_context_source_phrase` fields for quote Shorts. Sanitization keeps one grounded sentence and records retention/omission reasons in generation diagnostics. A valid source phrase supports paraphrases; unsupported-claim filters still apply. Exact source text stays intact. Unsupported causal titles, such as claiming love heals a wound when the source only says a wound from love heals, fail validation.
- Broad tag phrases whose autocomplete expansions mostly introduce foreign subjects lose eligibility. Thus `scar quotes` is not accepted as confirmation of emotional scars when its predictions point at characters or films. Quote tag selection removes near-duplicate mood variants and prefers a clear quote-format phrase. User-requested `yt` and `shorts` stay.
- A bounded exact-quote search complements semantic searches without increasing the query cap. Quote keyword signals come from grounded candidates rather than arbitrary adjacent word fragments. Official audio, songs and other explicitly different formats do not qualify merely by pasting a quote into their descriptions. Relevance screening remains conservative; zero retained results is a valid outcome, not grounds to fabricate evidence.
- A shared UI formatter distinguishes retrieval counts, retained results and unavailable legacy counts across research, angle and decision panels. Even an all-filtered response displays its retrieval diagnostics.
- Package source/format checks and the separate 0–10 title-writing heuristic have distinct descriptions. Neither claims measured CTR or reach.
- Quote thumbnail text uses title-derived concepts rather than generic `... QUOTES` category labels. Optional scores and creative guidance are expandable. Creator avoids duplicate generation toasts over mobile controls, and upload timing is labeled a suggested starting window.

## Validation

Verified on 2026-10-22 after rebuilding the frontend and Docker app:

- Backend: 1,826 tests and 803 subtests passed. One existing Starlette/httpx deprecation warning remains.
- Frontend: 466 tests across 45 files passed; TypeScript and Vite production build passed.
- Chromium Creator tests: 8 passed, including mobile retrieval accounting and avoiding duplicate toast overlays.
- The captured live scar response was rendered in the rebuilt Creator page on desktop and at 390px mobile width: no browser errors or horizontal overflow. This UI replay did not make another generation request.
- Application health: database and cache healthy. Post-rebuild logs contained no application errors. Cloud sync reported healthy/idle, zero pending uploads and zero consecutive failures; the two new packages were pushed by the configured sync service.

| Live test | Run | Duration | Unique results retrieved | Retained after screening | Description context |
| --- | --- | --- | --- | --- | --- |
| Love, hurt and a lasting scar | 69 | 12.39 seconds | 132 | 0 | Retained |
| Small steps every day can lead to big changes | 70 | 13.21 seconds | 148 | 5 | Retained |

These final reruns reused cached YouTube responses, generated fresh Gemini packages, and exercised the new source-screen cache version. Both passed local package checks. Saved History title, description, tags and hashtags were compared with the UTF-8 live response.

### Scar package, run 69

Title: **The lingering scars left behind by love**

Description:

> When you are in love, and you get hurt, it’s like a cut. It will heal, but there will always be a scar.
>
> A reflection on how emotional wounds heal while leaving lasting scars behind.
>
> #shorts #quotes #love

Tags: `hurt quotes`, `love quotes`, `scar from love`, `yt`, `shorts`.

The package preserves the meaning and adds a short contextual sentence. Its topic tags are relevant, but this run has no retained comparable-video evidence; the interface labels them as script-derived and does not claim measured demand.

### Daily-progress package, run 70

Title: **Small steps every day can lead to big changes.**

The description retains the quote and adds: “A reflection on how consistent daily progress shapes our future over time.” Hashtags: `#shorts #quotes #SmallDailySteps`. Tags: `small steps big changes`, `small daily steps`, `yt`, `shorts`.

The five retained results are model-screened comparisons, not proof of search volume or future performance. The contextual sentence is relevant but still uses a template-like “A reflection on” opening; future writing evaluations can improve variety without loosening source fidelity.

## Limits

These tests verify the identified regressions, not every possible model output. Conservative screening can reject useful comparisons, and model-generated writing still benefits from human review. No channel analytics were connected for this review, so neither the package score nor these changes establish why the channel receives 1.2k–1.9k views. Reach needs evaluation against actual viewer response after publication. No video was uploaded or published to YouTube during these tests.
