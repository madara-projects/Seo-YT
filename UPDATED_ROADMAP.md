# UPDATED_ROADMAP.md

> Audit date: 2026-06-21. Supersedes the maturity/priority sections of `ROADMAP.md`
> with findings verified against the code in this audit. The original `ROADMAP.md`
> remains a good architecture narrative; this file corrects its inaccuracies and
> re-prioritizes by business value × technical impact.

---

## Current state (verified 2026-06-21)

- `POST /analyze` works end-to-end (Ollama-on and Ollama-offline). Verified booting in
  Docker; all routes register.
- The codebase carries **~700+ LOC of unwired subsystems** and a handful of
  **silent-failure bugs** (see BUG_REPORT.md). The honest functional surface is smaller
  than the file count suggests.
- **Corrections to the old ROADMAP:**
  - ❌ "spaCy keyword + entity extraction" — **false**. Extraction is pure regex; spaCy
    is installed but never imported (BUG-2).
  - ⚠️ "Brain v2.0 / 90%+ accuracy" CTR — it's a hand-tuned heuristic with an unused
    `title_score` param and a dead seasonality branch (BUG-8).
  - ⚠️ `ai_uniqueness_score` is a real-looking field stuck at 0.5 (BUG-1).
  - ⚠️ The TTL cache does not work across requests in the default (no-Redis) config (BUG-3).

## Completed work (real)

- Layered FastAPI app, factory pattern, error envelope, rate limiting, request-id.
- YouTube Data API v3 with key rotation + quota rollover.
- Ollama-first generation with deterministic topic-locked fallback.
- Topic-lock safety layer (risk terms, junk tags, topic enforcement).
- SQLite history (`video_snapshots`, `analysis_runs`) → feedback package.
- Docker build + compose (app + Redis), Ollama reachable from container (fixed in the
  prior task).
- DevOps/test scaffolding removed (Jenkins, K8s/Helm earlier, ad-hoc test files).

## Missing work (real gaps)

- No automated tests / CI.
- No log rotation; log written to CWD (BUG-10).
- No auth by default (development mode disables admin gating).
- Multilingual fallback is English-only.
- Dashboard only sends `{script}` — language/region/audience controls absent from UI.

---

## Critical blockers

| # | Blocker | Evidence | Why it blocks |
|---|---|---|---|
| B1 | **Ollama not guaranteed present** | [ROADMAP.md:61-65](ROADMAP.md#L61) | Without it every run silently uses the lower-quality fallback. Single biggest quality gate. |
| B2 | **Leaked YouTube API key on disk** | [.env:4](.env#L4) | Secret was exposed during audit → rotate before any sharing/deploy. |
| B3 | **Silent-wrong bugs** (BUG-1, BUG-3, BUG-5) | BUG_REPORT.md | Output/learning signals are subtly wrong while looking healthy. |

---

## High-ROI improvements (do first)

| # | Item | Impact | Effort | Refs |
|---|---|---|---|---|
| H1 | **Rotate the leaked API key**; keep only in `.env` (already git-ignored) | Security | 5 min | [.env:4](.env#L4) |
| H2 | **Delete dead subsystems** (CLEANUP_PLAN Groups 1–2) | −700 LOC, trustable codebase | 1–2 h | CLEANUP_PLAN.md |
| H3 | **Drop spaCy + fix docs** (BUG-2) | −~150 MB image, faster build, honest docs | 30 min | [requirements.txt:9](requirements.txt#L9) |
| H4 | **Singleton `ResearchService`** at app-create | Restores caching (BUG-3), cuts YouTube quota burn | ~1 h | [routes.py:836](win_engine/api/routes.py#L836) |
| H5 | **Fix or remove `ai_uniqueness_score`** + delete the swallowing `except` (BUG-1) | Correctness/trust | 30 min | [gap_engine.py:34-43](win_engine/analysis/gap_engine.py#L34) |
| H6 | **Move Ollama config into `Settings`** (BUG-4) | `.env` works for local runs too | 30 min | [ollama_client.py:18](win_engine/llm/ollama_client.py#L18) |
| H7 | **Minimal pytest suite** (`/analyze` happy + Ollama-offline + topic-lock not over-firing) | Guards all future refactors | ~3 h | — |

## Medium-priority improvements

| # | Item | Impact | Refs |
|---|---|---|---|
| M1 | Persist `generation_source` and exclude template runs from learning aggregates (BUG-5) | Cleaner learning signal | [strategy_engine.py:191](win_engine/generation/strategy_engine.py#L191) |
| M2 | Make `/analyze` async (`httpx.AsyncClient`, `ollama_client.agenerate`) | Frees event loop, uses the already-written async client | [ollama_client.py:60](win_engine/llm/ollama_client.py#L60) |
| M3 | Slim `AnalyzeResponse` — move ~20 rarely-used fields into `extras: dict` | Less coupling, cheaper requests | [schemas.py:23](win_engine/core/schemas.py#L23) |
| M4 | Escape dashboard interpolation (BUG-9) | Removes injection surface | [routes.py:684-707](win_engine/api/routes.py#L684) |
| M5 | Log rotation + write to a configurable path (BUG-10) | Bounded disk, clean repo | [logging.py:52](win_engine/core/logging.py#L52) |
| M6 | Decide on Phase 9/10 tables: implement or remove (CLEANUP Group 4) | Schema honesty | [history_store.py:73](win_engine/feedback/history_store.py#L73) |
| M7 | Surface language/region/audience controls in the dashboard | Unlocks multilingual path already in the backend | [routes.py:423](win_engine/api/routes.py#L423) |

## Future enhancements (after the above)

| # | Item | Note |
|---|---|---|
| F1 | Pass engagement ratios (like/view, comment/view) to the Ollama prompt | ~10 LOC; better pattern signal. [ROADMAP.md:135-138](ROADMAP.md#L135) |
| F2 | Per-niche system-prompt headers (gaming/education/finance/…) | Quality lift; only after baseline mistral output is reviewed |
| F3 | Real intent classifier (replace keyword lookup TODO) | [intent_classifier.py:12](win_engine/analysis/intent_classifier.py#L12) |
| F4 | Dynamic chapter timestamps from script length (BUG-7) | Makes chapters usable |
| F5 | YouTube OAuth for own-channel analytics | Out of scope for current single-user tool |
| F6 | If Phase 9/10 revived: wire `video_uploads`/`ab_tests`/`scheduled_uploads` + the pattern-memory analytics that are already written | Reuses currently-dead code instead of deleting it |

---

## Prioritized sequence (business value × technical impact)

1. **H1** (rotate key) — security, 5 min.
2. **H2 + H3** (delete dead code + drop spaCy) — biggest trust/size win, low risk.
3. **H5 + H6 + H4** (fix silent-wrong bugs + restore cache) — correctness.
4. **H7** (tests) — lock in the cleaned state.
5. **M1–M5** (learning hygiene, async, schema slimming, XSS, logging).
6. **F1–F2** (prompt quality) — the actual creator-output lever, once the base is clean.

**Guiding principle (carried from the original ROADMAP and reaffirmed):** the architecture
is sound; the work is to **make the running surface match the apparent surface** — delete
what doesn't run, fix what silently lies, then invest in prompt/output quality.
</content>
