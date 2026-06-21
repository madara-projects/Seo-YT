# BUG_REPORT.md

> Audit date: 2026-06-21. Each bug lists evidence, impact, and confidence.
> No fixes were applied (audit-only phase).

---

## Marker scan (TODO / FIXME / HACK / XXX / placeholder)

Repo-wide grep results:

- **TODO** — [intent_classifier.py:12](win_engine/analysis/intent_classifier.py#L12):
  `"TODO: Replace with robust classifier using real data."` The intent classifier is a
  keyword-list lookup ([intent_classifier.py:9-58](win_engine/analysis/intent_classifier.py#L9))
  and defaults to `"SUGGESTED"` for anything unmatched ([line 58](win_engine/analysis/intent_classifier.py#L58)).
- **FIXME / HACK / XXX** — none found.
- **Placeholder / "Note: Real implementation would..."** —
  [ctr_prediction_v2.py:236](win_engine/analysis/ctr_prediction_v2.py#L236)
  `"# Note: Real implementation would check current month"`: the `seasons` dict
  ([lines 230-235](win_engine/analysis/ctr_prediction_v2.py#L230)) is built and then
  never used; seasonality always returns `1.0` unless a trending keyword matches.

---

## Confirmed bugs

### 🔴 BUG-1 — `ai_uniqueness_score` is permanently 0.5 (broken import, swallowed)
- **Where:** [gap_engine.py:34-43](win_engine/analysis/gap_engine.py#L34)
- **Evidence:** imports `win_engine.analysis.ai_enhancement.get_ai_engine`. That module
  does not exist (the real one is `win_engine.ai_enhancement` and has **no**
  `get_ai_engine` — see [ai_enhancement.py](win_engine/ai_enhancement.py) public surface
  and [ROADMAP.md:97](ROADMAP.md#L97) confirming `analysis/ai_enhancement.py` was
  deleted). The `except Exception: pass` at [line 42-43](win_engine/analysis/gap_engine.py#L42)
  swallows the `ImportError` on every call.
- **Impact:** `uniqueness_score` initialized to `0.5` ([line 34](win_engine/analysis/gap_engine.py#L34))
  is never updated, so `opportunity_gap_analysis.ai_uniqueness_score` is a constant
  fake. Any consumer treating it as real signal is misled.
- **Confidence:** High (verified by grep + module read).

### 🔴 BUG-2 — spaCy advertised but never used; misleading docs + image bloat
- **Where:** [requirements.txt:9-10](requirements.txt#L9); claims at
  [README.md:67](README.md#L67) and [ROADMAP.md:52](ROADMAP.md#L52).
- **Evidence:** zero `import spacy` / `en_core_web_sm` references in code. Extraction is
  regex-only.
- **Impact:** ~150 MB of unused dependency in the Docker image; longer build; docs
  claim an analysis capability the code does not have.
- **Confidence:** High.

### 🟠 BUG-3 — In-memory cache is dead across requests (no caching in default config)
- **Where:** [routes.py:836](win_engine/api/routes.py#L836) creates
  `ResearchService(settings)` per request; [research_service.py:24-28](win_engine/ingestion/research_service.py#L24)
  builds a fresh `TTLCache` each time when `redis_url` is empty.
- **Evidence:** `TTLCache` stores state on the instance ([cache.py:14-19](win_engine/ingestion/cache.py#L14));
  a new instance per request starts empty, so `gather()`'s cache lookup
  ([research_service.py:38-41](win_engine/ingestion/research_service.py#L38)) always
  misses and re-hits the YouTube API.
- **Impact:** Every `/analyze` consumes YouTube quota even for identical repeated queries
  (defeats the trending/evergreen TTL design). Only mitigated if Redis is configured.
- **Confidence:** High.

### 🟠 BUG-4 — Ollama config read from `os.environ`, bypassing Settings/`.env`
- **Where:** [ollama_client.py:18-20](win_engine/llm/ollama_client.py#L18) reads
  `OLLAMA_BASE_URL/MODEL/TIMEOUT` directly from `os.environ` at **import time**.
- **Evidence:** these are not fields on `Settings` ([config.py:9-31](win_engine/core/config.py#L9)),
  and nothing exports `.env` into `os.environ` for a bare `python app.py` run
  (pydantic-settings reads `.env` for `Settings`, but `os.environ` does not see it).
- **Impact:** For local `python app.py`, the `.env` `OLLAMA_*` values are **ignored**;
  only real shell env vars take effect. Works in Docker only because compose injects them
  as real env vars ([compose.yaml](compose.yaml), set during the prior task). Also,
  reading at import time means changing env after import has no effect.
- **Confidence:** High.

### 🟠 BUG-5 — `record_analysis_run` is called even on the Ollama fallback / errors aren't isolated
- **Where:** [strategy_engine.py:136-147](win_engine/generation/strategy_engine.py#L136).
- **Evidence:** every `/analyze` writes an `analysis_runs` row, including fallback-template
  runs, with the template's deterministic title score. The learning/feedback aggregates
  ([history_store.py:233](win_engine/feedback/history_store.py#L233),
  [history_store.py:304](win_engine/feedback/history_store.py#L304)) then blend real
  Ollama runs and template runs together with no `generation_source` column to separate
  them (the source is computed at [strategy_engine.py:191](win_engine/generation/strategy_engine.py#L191)
  but never persisted).
- **Impact:** "Winning patterns", "best angle", and historical comparisons are polluted by
  template runs, skewing the learning signal.
- **Confidence:** Medium-High (behavioral, not a crash).

### 🟠 BUG-6 — Potential `ZeroDivisionError`-class / empty-data edge in `_topic_from_signals` & friends is handled, but `max(... key=...)` on empty dict is not
- **Where:** `_competitor_shadow` uses `max(title_pattern_counts, key=...)`
  ([gap_engine.py:267](win_engine/analysis/gap_engine.py#L267)) — safe (dict always has 3
  keys). `build_channel_intelligence` uses `most_common(1)[0][0]`
  ([strategy_layer.py:27-29](win_engine/analysis/strategy_layer.py#L27)) — guarded by the
  early `if not youtube_results` return ([strategy_layer.py:10](win_engine/analysis/strategy_layer.py#L10)). ✅
- **Evidence:** reviewed; these specific spots are safe. Listed to document that the
  empty-input paths were checked.
- **Confidence:** High (no bug here — recorded as a cleared suspicion).

### 🟡 BUG-7 — `chapters` timestamps are hard-coded regardless of script length
- **Where:** [expansion_engine.py:6-13](win_engine/generation/expansion_engine.py#L6).
- **Evidence:** `timestamps = ["00:00","00:30","02:00","04:00"]` are fixed; chapter titles
  come from the first 4 keyword signals. For a 30-second short or a 2-hour video the
  timestamps are equally wrong.
- **Impact:** Chapter output is cosmetic/unreliable; pasting it into YouTube would create
  bogus chapter markers.
- **Confidence:** High.

### 🟡 BUG-8 — `seasonality_factor` dead branch; `title_score` parameter ignored in v2 predictor
- **Where:** [ctr_prediction_v2.py:215-239](win_engine/analysis/ctr_prediction_v2.py#L215)
  (`seasons` dict unused) and [ctr_prediction_v2.py:27-35](win_engine/analysis/ctr_prediction_v2.py#L27)
  (`title_score` accepted by `predict_ctr` but never used in the computation).
- **Impact:** "Brain v2.0 / 90%+ accuracy" framing ([ctr_prediction_v2.py:74-76](win_engine/analysis/ctr_prediction_v2.py#L74),
  [learning_engine.py:74-76](win_engine/feedback/learning_engine.py#L74)) is marketing;
  the model is a hand-tuned heuristic with an unused parameter and a dead seasonal branch.
  No crash, but the accuracy claim is unfounded.
- **Confidence:** High.

### 🟡 BUG-9 — Stored XSS surface in dashboard via YouTube-supplied strings
- **Where:** [routes.py:684-707](win_engine/api/routes.py#L684) interpolates
  `item.title` / `channel_title` / `description` into `innerHTML`.
- **Impact:** A crafted competitor video title/description could inject HTML/script into
  the local user's browser. Single-user/local lowers severity, but it is a real injection.
- **Confidence:** Medium (depends on YouTube returning markup; titles are sanitized by
  YT but descriptions are freeform).

### 🟡 BUG-10 — `win_engine.log` written to CWD with no rotation
- **Where:** [logging.py:52-57](win_engine/core/logging.py#L52).
- **Impact:** Unbounded file growth; clutters repo root on local runs (regenerates after
  deletion). Confidence: High.

---

## Runtime / production risk summary

| ID | Title | Severity | Crash? | Silent? |
|---|---|---|---|---|
| BUG-1 | `ai_uniqueness_score` stuck 0.5 | 🔴 | No | Yes |
| BUG-2 | spaCy unused / docs wrong | 🔴 | No | Yes |
| BUG-3 | Cross-request cache dead | 🟠 | No | Yes (quota burn) |
| BUG-4 | Ollama config bypasses `.env` locally | 🟠 | No | Yes |
| BUG-5 | Learning data polluted by fallback runs | 🟠 | No | Yes |
| BUG-7 | Hard-coded chapter timestamps | 🟡 | No | No |
| BUG-8 | CTR v2 dead params / overclaimed accuracy | 🟡 | No | Yes |
| BUG-9 | Dashboard innerHTML injection | 🟡 | No | No |
| BUG-10 | Unrotated log file | 🟡 | No | No |

No crash-class bugs were found on the `/analyze` happy path; the dominant theme is
**silent wrong-ness** (swallowed import, dead cache, polluted learning signal, unfounded
accuracy claims).
</content>
