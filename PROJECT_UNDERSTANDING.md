# PROJECT_UNDERSTANDING.md

> Audit date: 2026-06-21 · Scope: full read of every Python/Docker/YAML/Markdown/env file
> (`.venv`, `.git`, `.claude` excluded). No code was modified to produce this document.

---

## 1. What problem does this project solve?

It turns a **video script (or a one-line idea)** into a **ready-to-paste YouTube SEO
package**: a primary title, alternate title variants, a description, tags, hashtags,
plus a large bundle of supporting strategy analysis (intent, content audit, competitor
gap, pacing, thumbnail direction, chapters, CTR prediction, A/B test pack, historical
comparison).

It is explicitly a **local-first, single-user tool** — not a SaaS, not multi-tenant.
[README.md:1-8](README.md#L1), [ROADMAP.md:1-7](ROADMAP.md#L1).

## 2. Major features (verified against code)

| Feature | Entry point | Evidence |
|---|---|---|
| SEO package generation (Ollama-first, deterministic fallback) | `build_seo_package` | [strategy_engine.py:36-192](win_engine/generation/strategy_engine.py#L36) |
| Topic-lock / safety post-processing | `topic_lock.py` | [topic_lock.py](win_engine/analysis/topic_lock.py) |
| YouTube research (search + video + channel stats, key rotation) | `YouTubeClient` | [youtube_client.py:13-251](win_engine/ingestion/youtube_client.py#L13) |
| Outlier scoring of competitor videos | `score_outliers` | [outlier_engine.py:112-168](win_engine/scoring/outlier_engine.py#L112) |
| Keyword / entity extraction (regex heuristics) | `extract_keyword_signals`, `extract_entity_signals` | [keyword_extractor.py](win_engine/analysis/keyword_extractor.py), [entity_extractor.py](win_engine/analysis/entity_extractor.py) |
| Opportunity / competition gap analysis | `analyze_opportunity_gaps` | [gap_engine.py:9-61](win_engine/analysis/gap_engine.py#L9) |
| Content audit (hook, retention, alignment) | `audit_content_package` | [content_auditor.py:7-50](win_engine/analysis/content_auditor.py#L7) |
| CTR prediction "Brain v2.0" | `get_enhanced_ctr_prediction` | [ctr_prediction_v2.py:292](win_engine/analysis/ctr_prediction_v2.py#L292) |
| Feedback / learning loop over local history | `build_feedback_package` | [learning_engine.py:10-43](win_engine/feedback/learning_engine.py#L10) |
| SQLite history store | `HistoryStore` | [history_store.py:9](win_engine/feedback/history_store.py#L9) |
| Single-port HTML dashboard | `GET /` | [routes.py:768-770](win_engine/api/routes.py#L768) |
| Health / readiness / meta / diagnostics endpoints | routes | [routes.py:773-830](win_engine/api/routes.py#L773) |

## 3. Intended users

A **single creator** (the repo owner), producing 2–5 videos/day on a local laptop
(stated: Lenovo LOQ, i5-12HX / RTX 2050 / 12 GB). No login, no per-user state, no
auth in the local profile. [ROADMAP.md:3-4](ROADMAP.md#L3).

## 4. How the system works, end-to-end

```
Browser form (GET /)               app.py → create_app() → FastAPI
        │ POST /analyze {script}
        ▼
routes.analyze_script()            [routes.py:833-844]
        │ builds ResearchService(settings)  ← instantiated PER REQUEST
        ▼
ResearchService.gather()           [research_service.py:32-70]
   ├─ cache lookup (Redis or in-memory TTL)   [cache.py]
   ├─ YouTubeClient.search_videos()           [youtube_client.py:27]
   ├─ score_outliers()                        [outlier_engine.py:112]
   ├─ HistoryStore.record_snapshots()         [history_store.py:137]
   ├─ extract_keyword_signals / entity        [keyword_extractor.py / entity_extractor.py]
   ├─ upload_timing_insights()                [history_store.py:377]
   └─ analyze_thumbnails()                     [thumbnail_intelligence.py:6]
        ▼
generate_seo_suggestions()         [seo_generator.py:24-129]
   ├─ topic-lock PRE: normalize_risk_terms, infer_category,
   │   extract_main_topic, expand_idea_to_script   [topic_lock.py]
   ├─ classify_intent()                         [intent_classifier.py:9]
   ├─ build_seo_package()                       [strategy_engine.py:36]
   │     ├─ write_seo_package() → Ollama JSON call   [seo_writer.py:169]
   │     │     └─ falls back to _fallback_package() if Ollama offline
   │     ├─ audit_content_package, analyze_opportunity_gaps,
   │     │   analyze_script_pacing, build_channel_intelligence,
   │     │   build_content_graph_strategy, build_chapters,
   │     │   build_session_expansion, build_binge_bridge,
   │     │   build_thumbnail_strategy, build_automation_workflow
   │     ├─ HistoryStore.record_analysis_run()  [history_store.py:201]
   │     └─ build_feedback_package()            [learning_engine.py:10]
   └─ topic-lock POST: force_topic_in_* validators
        ▼
AnalyzeResponse (35 fields) .model_dump()      [schemas.py:23-58]
        ▼
Browser renders ~5 of the 35 fields            [routes.py:438-727]
```

## 5. Deployment model

- **Primary:** run locally with `python app.py` (uvicorn, host 0.0.0.0:8000).
  [app.py:11-18](app.py#L11).
- **Optional:** Docker. `Dockerfile` (python:3.11-slim) + `compose.yaml`
  (app + Redis). Confirmed building & running healthy during this audit.
- CI/CD (Jenkins) and the test scaffolding were removed in the immediately
  preceding task; Kubernetes/Helm were removed in commit `98121fe`.
- **No frontend build step** — the UI is a single inline HTML string served from
  `GET /` ([routes.py:20-765](win_engine/api/routes.py#L20)). There is no
  JS/TS toolchain, no `package.json`.

## 6. Core workflows

1. **Idea → SEO package** (the only real user workflow): paste text, click *Analyze*.
2. **Diagnostics**: `GET /diagnostics` runs a live YouTube probe.
3. **Health/readiness**: `GET /health`, `GET /ready`, `GET /meta` for ops.
4. **Export**: client-side "Export Result" downloads the last JSON response
   ([routes.py:373-382](win_engine/api/routes.py#L373)).

## 7. What is complete

- End-to-end `/analyze` pipeline (both Ollama-on and Ollama-offline paths).
- YouTube Data API integration with key rotation + quota rollover handling.
- TTL cache with Redis fallback to in-memory.
- Topic-lock layer (risk-term scrubbing, junk-tag filtering, topic enforcement).
- SQLite history (`video_snapshots`, `analysis_runs`) feeding the feedback package.
- Structured error envelope + rate limiting + request-id middleware.
- Docker build/run (verified).

## 8. What is incomplete / aspirational

- **Ollama dependency is external and unmanaged** — if not installed, every run
  silently uses the lower-quality template fallback. [ROADMAP.md:61-65](ROADMAP.md#L61).
- **"Performance tracking" + "execution engine" tables** (`video_uploads`,
  `performance_metrics`, `ab_tests`, `scheduled_uploads`) are created but **never
  written or read** — Phase 9/10 stubs. [history_store.py:72-133](win_engine/feedback/history_store.py#L72).
- **"Pattern memory" / "deep learning" subsystem** (`DeepLearningEngine`, 5
  `HistoryStore` analytics methods, 3 `learning_engine` helpers) is fully written
  but **never wired into any endpoint**. See TECHNICAL_AUDIT.md §Dead code.
- **`ai_uniqueness_score`** is hard-stuck at `0.5` due to a broken import — see
  BUG_REPORT.md BUG-1.
- **spaCy** is a declared dependency but **not used by any code** — see BUG_REPORT.md BUG-2.
- **Multilingual fallback** is English-only; Tamil/Tanglish require Ollama.
- **No automated tests** (the ad-hoc payload script was removed in the prior task).
- The dashboard only sends `{script}` — `language`, `region`, `audience_type` from
  `AnalyzeRequest` are never set by the UI ([routes.py:423](win_engine/api/routes.py#L423)).

## Folder structure

```
app.py                     FastAPI entry (uvicorn.run)
Dockerfile, compose.yaml   container build + app/redis stack
requirements.txt           deps (note: spaCy unused — see audit)
README.md, ROADMAP.md      docs (partially inaccurate — see audit)
win_engine/
  api/        app.py (factory, middleware, error handlers), routes.py (UI + endpoints)
  core/       config, schemas, logging, middleware, rate_limit
  ingestion/  research_service, youtube_client, cache
  analysis/   topic_lock, intent, keyword/entity extractors, content_auditor,
              gap_engine, language_engine, pacing_engine, strategy_layer,
              thumbnail_classifier, thumbnail_intelligence,
              ctr_prediction_v2, dynamic_thresholds
  generation/ seo_generator, strategy_engine, automation_engine, expansion_engine
  llm/        ollama_client, seo_writer
  feedback/   history_store, learning_engine, deep_learning_engine
  scoring/    outlier_engine
  ai_enhancement.py   rule-based quality/similarity (results computed but unused)
```

There is **no** authentication subsystem, **no** background worker/scheduler, and
**no** external integration other than the YouTube Data API and the local Ollama daemon.
</content>
