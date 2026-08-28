# Phase 2B — Generation Quality and Package Dynamicity

Verification date: 2026-08-28  
Application: 0.13.0 · SQLite schema: 8

This report records a deterministic audit of the package-generation path. It is
not a claim of semantic AI quality or of YouTube reach.

## Inspected path

Creator input is parsed by `analysis/creator_brief.py`, then research/context is
assembled by `ingestion/research_service.py`. `api/routes.py` calls
`generation/seo_generator.py`, which applies risk/topic locking and calls
`generation/strategy_engine.py`. The strategy engine sends the selected
language to `llm/seo_writer.py` (Gemini when available), parses and validates
the response with `analysis/generation_quality.py`, and performs at most one
repair. A deterministic local fallback is used when the provider is unavailable.
The final package is normalized by `seo_generator.py`, converted to title /
thumbnail choices by `analysis/package_builder.py`, and stored by
`feedback/history_store.py` for Creator and History display.

## What was already correct

- Shorts titles require exactly one `#shorts`; contextual Shorts can receive a
  relevant emoji, while non-Shorts cannot use the label.
- The provider repair path is bounded to one attempt and preserves the local
  quality/safety gate.
- Search, Browse, and Existing audience intent labels are retained, and timing
  evidence follows the Phase 2A personal-history/public/general priority.
- Claims, exact quotes, language, title length, duplicate candidates, and
  obvious tag-list descriptions are checked deterministically.

## Confirmed weaknesses and hardening

The deterministic matrix used practical Python/CSV instruction, Chennai street
food travel, dosa cooking, Free Fire gaming, and rainy/night Shorts inputs with
the provider mocked unavailable. It showed that inferred ordinary topics were
truncated to three words, the fallback reused a universal “actual details”
sentence, and long topics could leave fewer than three usable title/package
alternatives after duplicate validation.

The following narrow changes address those observations:

- inferred non-quote topics retain up to eight meaningful source terms;
- fallback titles use five distinct, readable mechanisms and compact the title
  phrase without discarding the full topic used in descriptions/tags;
- fallback descriptions include the supplied source context and no longer use
  the universal placeholder paragraph;
- Search, Browse, and Existing audience package rationale is strategy-aware;
- platform filler (`youtube`, `yt`, `viral`, `trending`, and related variants)
  is removed, and context-aware normalization drops unrelated tags;
- the quality gate reports generic-filler dominance and topic-unrelated tags.

No topic-specific hardcoded mapping was added. The behavior is derived from the
creator brief and supplied research terms.

## Quality answers

- Titles, descriptions, tags, and keywords respond to supplied topic/context;
  deterministic tests verify cross-topic differences and contamination guards.
- Tags are normalized, deduplicated, subject-grounded, and filler-resistant.
- Search/Browse/Existing packages have distinct intent labels, discovery fields,
  and click rationale; this is strategic differentiation, not a reach forecast.
- Weak research does not create search volume, CTR, ranking, audience, or other
  unsupported facts.
- Shorts preserve one `#shorts` and use semantic emoji selection where context
  warrants it; different moods are not forced to share one emoji.
- Repair remains one bounded provider attempt; a failed repair is rejected and
  falls back safely rather than silently accepting an invalid package.
- The local fallback is honest and source-grounded, but it is deterministic and
  less expressive than Gemini. Its output is a safe starting package, not an
  assertion of expected performance.

## Limitations

Unit and integration tests cannot prove that a title will earn views, that a
description ranks, or that any tag caused a YouTube outcome. No live Gemini,
YouTube publishing, OAuth mutation, Aiven write, or production database test was
performed. Package strategy fields are metadata describing intended discovery
surfaces; they do not make YouTube serve a particular surface.

## Reproducible verification

All checks ran against a fresh `seo-yt-phase2b-verification:latest` image. The
backend command discovered **204 passed, 0 failed, 0 errors, 0 skipped**. The
deterministic browser suite reported **40 passed, 0 failed, 0 errors, 0
skipped**. Python `compileall` and JavaScript `node --check` passed;
`git diff --check` passed; and `docker compose config --quiet` passed.

A disposable container used an isolated temporary SQLite path (no project
database or `.env`). It was healthy; `/health` returned `status: ok`, version
`0.13.0`, and `database_ok: true`; `/meta` returned the expected capabilities.
The container was removed after verification. No live YouTube, Gemini, OAuth,
Aiven, or publishing request was made.

## Phase boundary

Phase 2B does not change cloud synchronization, data durability, OAuth scopes,
database schema, user data, or UI design. If the complete verification below is
clean, the next scoped phase is **PHASE 2C — DATA DURABILITY + CLOUD SYNC
CONTRACT HARDENING**.
