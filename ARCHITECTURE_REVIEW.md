# ARCHITECTURE_REVIEW.md

> Audit date: 2026-06-21. Evaluated against the project's **stated scope**:
> single-user, local-first, 2–5 videos/day. Scores are 1–10.

---

## 1. Current architecture

A single FastAPI process with a clean layered package:

```
api  →  generation  →  analysis + feedback + ingestion + scoring  →  core
```

- **Entry:** `app.py` → `create_app()` (factory pattern, good).
- **Request path:** one synchronous `POST /analyze` orchestrates research →
  generation → topic-lock → 35-field response.
- **External deps:** YouTube Data API (HTTP), Ollama (local HTTP), SQLite, optional Redis.
- **UI:** inline HTML/JS string served from `/` (no build pipeline).

The layering is genuinely good: modules are small, single-purpose, and import
downward only (no cycles). The seams (`ResearchService`, `build_seo_package`,
`write_seo_package`, `topic_lock`) are well chosen.

## 2. Design quality

**Strengths**
- Clear separation of concerns; each analysis concern is its own module.
- Ollama-first with deterministic fallback is a sound resilience pattern
  ([strategy_engine.py:64-72](win_engine/generation/strategy_engine.py#L64)).
- Topic-lock as a thin pre/post wrapper keeps the LLM honest without rewriting it
  ([seo_generator.py:31-91](win_engine/generation/seo_generator.py#L31)).
- Consistent error envelope + request-id + rate limiting at the edge.
- Config centralized via pydantic-settings (mostly — see the Ollama exception).

**Weaknesses**
- **Feature-stub accretion.** Whole subsystems were written ahead of being wired in
  (DeepLearningEngine, pattern-memory methods, 4 DB tables, CTR "v2", dynamic
  thresholds). This is the biggest architectural smell: ~700+ LOC of plausible-looking
  but unreachable machinery, plus marketing-grade naming ("Brain v2.0", "90%+ accuracy")
  that overstates what runs. See TECHNICAL_AUDIT §C/§E.
- **The 35-field response.** `AnalyzeResponse` ([schemas.py:23-58](win_engine/core/schemas.py#L23))
  forces every analysis to run every request; the UI renders ~5 fields. Heavy coupling
  between the schema and a dozen engines.
- **Per-request `ResearchService`** breaks the cache and re-runs DDL each call
  (TECHNICAL_AUDIT §H/BUG-3).
- **Two config paths** (Settings vs `os.environ` for Ollama) — inconsistent (BUG-4).
- **Persisted learning signal is unsegmented** (template vs LLM runs mixed, BUG-5).

## 3. Maintainability

- Small modules, readable code, good docstrings, type hints throughout → easy to read.
- **But** a newcomer cannot tell live code from dead code without a usage trace: e.g.
  `learning_engine` imports `DeepLearningEngine` at the top
  ([learning_engine.py:7](win_engine/feedback/learning_engine.py#L7)) implying it's used,
  when it isn't. The dead code actively misleads.
- Docs (README/ROADMAP) are partly inaccurate (spaCy claim), which erodes trust in the docs.
- No tests → refactors are unguarded.

## 4. Extensibility

- Adding a new analysis module is easy (drop in `analysis/`, call from `build_seo_package`,
  add a field to `AnalyzeResponse`). The pattern is obvious.
- The 35-field monolithic response makes it costly to add fields cleanly; an `extras:
  dict` would help (already noted in [ROADMAP.md:143-144](ROADMAP.md#L143)).
- LLM swap is trivial (`OLLAMA_MODEL`), and the prompt builder is well isolated
  ([seo_writer.py:92-123](win_engine/llm/seo_writer.py#L92)).

## 5. Security

- For local single-user: acceptable. For anything shared: not.
- Default `development` environment disables admin gating
  ([routes.py:848](win_engine/api/routes.py#L848)); diagnostics public by default;
  dashboard `innerHTML` injection surface; live API key on disk (rotate).
  See TECHNICAL_AUDIT §I, BUG-9.

## 6. Reliability

- Failure-tolerant by design: Ollama offline → fallback; YouTube quota → key rotation
  → empty results + warning; Redis missing → in-memory. Good.
- Undercut by silent-failure habits: swallowed `ImportError` (BUG-1), swallowed Redis
  build errors ([cache.py:74](win_engine/ingestion/cache.py#L74)). The system "keeps
  working" while producing subtly wrong output.

## 7. Scalability

- Single-process, sync handler, SQLite-per-call, per-request service construction. All
  fine at 2–5 req/day; none of it survives concurrency. The ROADMAP already names the
  fixes (async handler, singleton service) — they are deferred deliberately, not missed.

---

## Scores

| Dimension | Score | Rationale |
|---|---:|---|
| **Architecture** | **7/10** | Clean layering and good seams; dragged down by dead-subsystem accretion and the per-request service breaking the cache. |
| **Code Quality** | **6.5/10** | Readable, typed, documented — but ~700+ LOC dead code, silent excepts, and overclaimed "v2/Brain" naming. |
| **Security** | **4/10** | Open-by-default dev posture, public diagnostics, live key on disk, innerHTML injection. Fine *only* because it's local. |
| **Maintainability** | **6/10** | Easy to read per-file; hard to trust globally (dead code masquerades as live, docs partly wrong, no tests). |
| **Production Readiness** | **3.5/10** | Not intended for production. Sync handler, broken cache, no auth by default, no tests, no log rotation. Solid as a *local tool*, not a deployed service. |

**Overall (for the stated local-tool scope): ~6/10.** The bones are good; the project's
real debt is **unwired ambition** — large, named, plausible subsystems that don't run —
plus a handful of silent-failure bugs that make wrong output look like success.

### Top 5 architectural recommendations (no code changed yet)
1. Delete the unwired subsystems (DeepLearningEngine, pattern-memory methods + their
   5 HistoryStore methods, 4 unused tables, `_idea_kill_switch`, `_ctr_prediction` v1,
   `performance_logger`) — see CLEANUP_PLAN.md.
2. Fix or remove BUG-1 (`ai_uniqueness_score`) and remove the swallowing `except`.
3. Make `ResearchService` a singleton at app-create time (restores caching) and/or
   move Ollama config into `Settings`.
4. Drop spaCy from requirements (and correct README/ROADMAP) until it's actually used.
5. Add a minimal pytest suite around `/analyze` (happy path + Ollama-offline + topic-lock).
</content>
