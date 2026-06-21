# TECHNICAL_AUDIT.md

> Audit date: 2026-06-21. Findings are evidence-based with `file:line` citations.
> Severity: 🔴 high · 🟠 medium · 🟡 low. No code was changed.

---

## A. Syntax / import integrity

- ✅ All modules compile and the app boots: `create_app()` registered every route
  in the running container (`/`, `/health`, `/ready`, `/meta`, `/diagnostics`,
  `/analyze`). Verified live.
- 🔴 **Broken import (silently swallowed).** [gap_engine.py:36](win_engine/analysis/gap_engine.py#L36)
  `from win_engine.analysis.ai_enhancement import get_ai_engine`. There is **no**
  `win_engine/analysis/ai_enhancement.py` (ROADMAP confirms it was deleted,
  [ROADMAP.md:97](ROADMAP.md#L97)), and the real `win_engine/ai_enhancement.py`
  has **no** `get_ai_engine`. The `try/except Exception: pass`
  ([gap_engine.py:42-43](win_engine/analysis/gap_engine.py#L42)) hides the
  `ImportError`, so `ai_uniqueness_score` is **always 0.5**. Detailed in BUG_REPORT BUG-1.

## B. Circular dependencies

- None found. `core.logging.add_request_context` imports `core.config` *inside the
  function* ([logging.py:89](win_engine/core/logging.py#L89)) to avoid a cycle —
  acceptable. Import graph is a DAG (api → generation → analysis/feedback → core).

## C. Dead code / unused functions, classes, modules

All confirmed by repo-wide grep showing **definition only, no call site**:

| Symbol | Location | Status |
|---|---|---|
| `DeepLearningEngine` (entire class + module) | [deep_learning_engine.py:13](win_engine/feedback/deep_learning_engine.py#L13) | Imported at [learning_engine.py:7](win_engine/feedback/learning_engine.py#L7) but **never instantiated**. 337 LOC dead. |
| `_ctr_prediction` (v1) | [learning_engine.py:46](win_engine/feedback/learning_engine.py#L46) | Superseded by `_ctr_prediction_v2`; no callers. |
| `build_pattern_memory_package` | [learning_engine.py:228](win_engine/feedback/learning_engine.py#L228) | No callers outside its own file. |
| `enrich_feedback_with_patterns` | [learning_engine.py:248](win_engine/feedback/learning_engine.py#L248) | No callers. |
| `pattern_memory_summary` | [learning_engine.py:279](win_engine/feedback/learning_engine.py#L279) | No callers. |
| `HistoryStore.performance_correlation` | [history_store.py:431](win_engine/feedback/history_store.py#L431) | Only called by the unused `build_pattern_memory_package`. |
| `HistoryStore.success_formula_recognition` | [history_store.py:489](win_engine/feedback/history_store.py#L489) | Same — transitively dead. |
| `HistoryStore.trend_analysis` | [history_store.py:562](win_engine/feedback/history_store.py#L562) | Same. |
| `HistoryStore.memory_persistence` | [history_store.py:646](win_engine/feedback/history_store.py#L646) | Same. |
| `HistoryStore.creator_baseline` | [history_store.py:728](win_engine/feedback/history_store.py#L728) | Same. |
| `_idea_kill_switch` | [gap_engine.py:143](win_engine/analysis/gap_engine.py#L143) | Replaced by `get_dynamic_kill_switch`; no callers. ~40 LOC. |
| `performance_logger` | [logging.py:101](win_engine/core/logging.py#L101) | Context manager, never used. |
| `ai_insights`, `ai_quality_analysis` | [strategy_engine.py:166-167,189-190](win_engine/generation/strategy_engine.py#L166) | **Computed every request**, placed in the package dict, but `seo_generator` never reads them and they are not in `AnalyzeResponse`. Wasted work. |
| `find_content_similarity` | [ai_enhancement.py:42](win_engine/ai_enhancement.py#L42) | Only reachable via the unused `ai_insights` path. |

## D. Unused configuration values

`Settings` defines fields that are never read anywhere:
- `rate_limit_*` **are** used ([app.py:33-36](win_engine/api/app.py#L33)). ✅
- `request_timeout_seconds` used by YouTubeClient. ✅
- 🟡 `youtube_max_results` used. ✅
- 🟠 `OLLAMA_*` env vars are read by `ollama_client` via **`os.environ` directly**
  ([ollama_client.py:18-20](win_engine/llm/ollama_client.py#L18)), **not** through
  `Settings`. So Ollama config bypasses the central config object — inconsistent and
  means `.env`'s `OLLAMA_*` only work because pydantic-settings also loads `.env` into
  the process env path is NOT guaranteed. (In Docker we set them as real env vars, so
  it works there; for bare `python app.py` it relies on `.env` being exported, which it
  is not — `pydantic-settings` reads `.env` itself but `os.environ` does not see it.)
  See BUG_REPORT BUG-4.
- 🟡 `WIN_ENGINE_ENABLED_LANGUAGES` and `WIN_ENGINE_DEFAULT_REGION` exist in `.env`
  ([.env:24-26](.env#L24)) but there is **no** corresponding `Settings` field, so they
  are ignored (`extra="ignore"`, [config.py:31](win_engine/core/config.py#L31)).

## E. Unused database tables

Created in `_initialize` but **never** `INSERT`-ed or `SELECT`-ed (grep: no `INSERT INTO`
for any of them):
- 🟠 `video_uploads` [history_store.py:74](win_engine/feedback/history_store.py#L74)
- 🟠 `performance_metrics` [history_store.py:88](win_engine/feedback/history_store.py#L88)
- 🟠 `ab_tests` [history_store.py:104](win_engine/feedback/history_store.py#L104)
- 🟠 `scheduled_uploads` [history_store.py:122](win_engine/feedback/history_store.py#L122)

Only `video_snapshots` and `analysis_runs` are actually used.

## F. Concurrency

- 🟠 **`/analyze` is a synchronous handler** ([routes.py:833](win_engine/api/routes.py#L833))
  performing blocking network I/O (YouTube via `requests`, Ollama via sync `httpx`).
  FastAPI runs sync handlers in a threadpool, so it does **not** block the event loop
  outright, but throughput is bounded by the threadpool and each call is fully blocking.
  Acceptable for 2–5 req/day; not for any real concurrency. [ROADMAP.md:77](ROADMAP.md#L77).
- 🟡 **SQLite connection per call.** `HistoryStore._connect()` opens a fresh
  `sqlite3.connect(path)` for every operation ([history_store.py:20-25](win_engine/feedback/history_store.py#L20))
  with default `check_same_thread=True`. Because each threadpool task opens its own
  connection this is safe, but under concurrent writes SQLite's default file lock can
  raise `database is locked`. Low risk at stated volume.

## G. Blocking I/O

- 🟠 Sync `requests.get` in `YouTubeClient._request_json`
  ([youtube_client.py:173](win_engine/ingestion/youtube_client.py#L173)) and sync
  `httpx.post` in `ollama_client.generate` ([ollama_client.py:48](win_engine/llm/ollama_client.py#L48)).
  Async variants (`agenerate`) exist but are **unused**. The whole `/analyze` chain is
  sync, so the async client is dead weight today.

## H. Memory / resource concerns

- 🟡 **Unbounded rate-limiter map.** `InMemoryRateLimiter._events` keeps a deque per
  `"{ip}:{path}"` key and never evicts empty/idle keys
  ([rate_limit.py:13-14](win_engine/core/rate_limit.py#L13)). Grows with unique client
  IP×path combos. Negligible for single-user; would leak slowly in a public deployment.
- 🟡 **In-memory TTL cache never purges expired keys except on access**
  ([cache.py:21-31](win_engine/ingestion/cache.py#L21)). Fine here.
- 🟠 **`ResearchService` rebuilt per request** ([routes.py:836](win_engine/api/routes.py#L836),
  [routes.py:828](win_engine/api/routes.py#L828)) — recreates the cache, YouTube client,
  and `HistoryStore` (and re-runs `CREATE TABLE IF NOT EXISTS` every call). The
  in-memory cache is therefore **useless across requests** (each request gets a brand
  new empty cache unless Redis is configured). Confirmed: `TTLCache` is per-instance.
  This defeats the caching layer entirely in the default (no-Redis) config.

## I. Security

- 🔴 **Live YouTube API key committed to `.env` on disk**
  ([.env:4](.env#L4) — `AIzaSy...`). `.env` is git-ignored ([.gitignore:1](.gitignore#L1)),
  so it is not in version control, but the secret is sitting in the working tree and was
  visible in the audit. Treat as exposed → rotate. The `.env.example` correctly ships
  empty ([.env.example:4](.env.example#L4)). ✅ for the example.
- 🟠 **Diagnostics public by default.** `public_diagnostics_enabled=True`
  ([config.py:15](win_engine/core/config.py#L15)) means `GET /diagnostics` runs a live
  YouTube probe with no auth ([routes.py:823-830](win_engine/api/routes.py#L823)).
- 🟠 **`_require_admin` is a no-op in development.** It returns immediately when
  `app_environment == "development"` ([routes.py:848-849](win_engine/api/routes.py#L848)),
  and the default environment **is** `development` ([config.py:14](win_engine/core/config.py#L14)).
  So `/ready` (and `/diagnostics` when toggled private) are unauthenticated by default.
- 🟡 **Dashboard renders server JSON via `innerHTML`** with values interpolated directly
  (e.g. competitor `title`, `description`) — [routes.py:684-707](win_engine/api/routes.py#L684).
  Those strings come from the YouTube API. A malicious video title could inject markup
  (stored-reflected XSS in the local browser). Low impact for a single local user, real
  in any shared deployment.
- 🟡 No outbound timeout on Ollama reachability is unified (`_REACH_TIMEOUT=2.0` vs
  `OLLAMA_TIMEOUT`), fine.

## J. Error handling

- ✅ Centralized handlers for `HTTPException`, `RequestValidationError`, and bare
  `Exception` returning a consistent envelope ([app.py:59-102](win_engine/api/app.py#L59)).
- 🟠 **Over-broad silent excepts** that can mask bugs:
  - [gap_engine.py:42](win_engine/analysis/gap_engine.py#L42) `except Exception: pass`
    (this is what hides BUG-1).
  - [cache.py:74](win_engine/ingestion/cache.py#L74) `except Exception: pass` when
    building Redis — silently falls back to in-memory even on a config typo.
- 🟡 `generate_seo_suggestions` raises `ValueError` if the history store is missing
  ([seo_generator.py:43-44](win_engine/generation/seo_generator.py#L43)); that path is
  internal and always satisfied, so it's effectively an assertion.

## K. Logging

- 🟠 **File handler writes `win_engine.log` to the process CWD unconditionally**
  ([logging.py:52-57](win_engine/core/logging.py#L52)). In Docker this writes inside the
  container (ephemeral); locally it litters the repo root (this file was present and was
  removed in the prior task — it will reappear on next run). No rotation → unbounded
  growth over time.
- 🟡 Two logging stacks coexist: stdlib `logging.getLogger(__name__)` is used in most
  modules while `structlog` is configured globally. Works, but the structlog richness is
  largely unused.

## L. Scalability

- Designed and adequate for single-user/local. The per-request `ResearchService`,
  sync handler, broken cross-request cache, and SQLite-per-call patterns would all need
  rework before any multi-user use. None of these are defects *for the stated scope* —
  they are scope boundaries, documented honestly in [ROADMAP.md:77-88](ROADMAP.md#L77).

## M. Dependency hygiene

- 🔴 **spaCy + `en_core_web_sm` model are declared but unused.**
  [requirements.txt:9-10](requirements.txt#L9). Grep for `import spacy` / `en_core_web_sm`
  in code: **zero hits**. The keyword/entity extractors are pure regex
  ([keyword_extractor.py](win_engine/analysis/keyword_extractor.py),
  [entity_extractor.py](win_engine/analysis/entity_extractor.py)). spaCy + the model
  archive (~12 MB wheel + ~150 MB installed) bloat the image and lengthen the Docker
  build for no runtime benefit. README/ROADMAP claiming "spaCy keyword + entity
  extraction" is **inaccurate** ([README.md:67](README.md#L67), [ROADMAP.md:52](ROADMAP.md#L52)).
- 🟡 `redis` is required even though Redis is optional at runtime — fine (used by
  `cache.RedisTTLCache`).

## Summary scorecard (technical)

| Dimension | State |
|---|---|
| Compiles / boots | ✅ Clean |
| Dead code | 🔴 ~700+ LOC across feedback layer + gap_engine + logging |
| Broken-but-hidden logic | 🔴 BUG-1 (`ai_uniqueness_score`) |
| Unused dependency | 🔴 spaCy (~150 MB) |
| Unused DB schema | 🟠 4 of 6 tables |
| Caching effectiveness | 🟠 Defeated by per-request service in no-Redis mode |
| Secrets | 🔴 Live key on disk (rotate) |
| Default auth posture | 🟠 Open in `development` (the default) |
| Fit for stated scope | ✅ Yes |
</content>
