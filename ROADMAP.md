# Project Status & Roadmap

Local AI-powered YouTube SEO engine. Single-user, 2-5 videos/day on a Lenovo
LOQ (i5-12HX / RTX 2050 / 12 GB RAM). Not a SaaS, not a multi-tenant tool.

This file replaces earlier marketing-style documents. It is the honest
state of the project as of the most recent cleanup pass.

## Current architecture (verified)

```
User script
    │
    ▼  POST /analyze  (FastAPI, sync handler)
ResearchService.gather()
    │  - YouTube Data API v3 search + video stats + channel stats
    │  - In-memory or Redis TTL cache (trending 6h / evergreen 7d)
    │  - Outlier scoring + keyword/entity extraction (spaCy)
    ▼
generate_seo_suggestions()  (win_engine/generation/seo_generator.py)
    │  - Topic-lock pre-process: risk-term normalization, category inference,
    │    main-topic extraction, idea-mode expansion
    │  - build_seo_package() — Ollama-first
    │       │
    │       ├─► write_seo_package(script, competitors, language, region,
    │       │     audience_type) → single Ollama JSON call
    │       │     (title, 5 variants, description, 10 tags, 3 hashtags)
    │       │
    │       └─► Fallback (deterministic, no random): minimal topic-locked
    │             title set + real description scaffold + research-derived
    │             tags. Only runs when Ollama is offline.
    │
    └─► Topic-lock post-process:
        - force_topic_in_title (only regenerates if title is structurally broken)
        - force_topic_in_description (prepends topic if missing)
        - force_topic_in_tags (drops junk, prepends topic, tops up category fallbacks)
        - force_hashtags (keeps LLM hashtags if present; tops up if missing)
```

Then enrichment runs on top of the locked package: content audit, opportunity
gap analysis, channel intelligence, content graph, chapters, session expansion,
binge bridge, thumbnail strategy, automation workflow, feedback package
(CTR prediction, A/B test pack, historical comparison).

## What is verified working

- **`POST /analyze` end-to-end** with Ollama offline → fallback path returns
  topic-locked output with no random scoring and no clickbait Mad Libs.
- **YouTube Data API v3** with key rotation on quota exhaustion.
- **TTL cache** with optional Redis fallback to in-memory.
- **`GET /`** serves a single-port HTML form (no Streamlit, no second port).
- **spaCy keyword + entity extraction** on script + competitor descriptions.
- **History store** (SQLite) records analysis runs for the learning engine.
- **Topic-lock layer** scrubs junk tags, normalizes risky terms, enforces
  topic presence in tags. No longer overrides LLM titles or hashtags.

## Current problems / technical debt

### Blockers for "creator-quality output"

1. **Ollama is not installed on this machine.** Until the user installs it
   (`winget install Ollama.Ollama` → `ollama pull mistral`), every `/analyze`
   call goes through the deterministic fallback path. The fallback is
   acceptable but it is not creator-quality output. **This is the single
   biggest gate.**
2. **Tamil / Tanglish output requires Ollama.** The fallback path is
   English-only — there is no template-based Tamil generation. When the user
   selects Tamil with Ollama offline, they get English fallback. This is the
   honest behavior; do not pretend otherwise.
3. **Competitor signal sent to the prompt is title + view count only.** Like
   count, comment count, channel subscriber count, video duration are all
   collected but not surfaced to Ollama. The model could pattern-match
   better with engagement-ratio context.

### Architecture issues (not blockers, but real)

4. **`/analyze` is a sync handler** doing blocking YouTube + Ollama I/O.
   Fine for 2-5 videos/day but it does block the event loop.
5. **`ResearchService` is instantiated per request.** Wasteful (rebuilds
   cache, YouTube client, history store). Should be a module-level singleton.
6. **`AnalyzeResponse` schema has 35 fields.** Most callers (including the
   built-in HTML form) only render 5 of them. The other 30 are computed every
   request anyway because the schema validates them.
7. **`intent_classifier` is a keyword-list lookup** with a TODO comment
   saying "Replace with robust classifier using real data." It works for
   English; it has nothing for Tamil/Tanglish.
8. **`language_engine` detects Tamil/Tanglish by counting marker words.**
   Brittle. Will misclassify often.

### Resolved in the latest cleanup

- ✅ Removed Streamlit branch (6 files, ~2,400 LOC).
- ✅ Removed clearly dead code (7 files, ~1,600 LOC).
- ✅ Removed `nlp_titlegen.py` template engine (446 LOC of clickbait Mad Libs
  with `random.uniform(7.5, 9.8)` fake scores).
- ✅ Removed `title_optimizer.py` (imported but never called).
- ✅ Removed `analysis/ai_enhancement.py` (secondary AI facade — only called
  by the deleted `nlp_titlegen.py`).
- ✅ Removed ~370 LOC of orphan template helpers from `strategy_engine.py`
  (`_build_title_variants`, `_build_description`, `_build_hashtags`,
  `_build_tags`, `_localize_title_variants`, `_extract_competitor_patterns`,
  `_extract_script_facts`, `_summarize_script`, `_humanize_*`).
- ✅ Fixed `force_topic_in_title` over-aggression — LLM titles are now
  preserved unless structurally broken.
- ✅ Fixed `force_hashtags` overwriting LLM hashtags — now prefers existing,
  only tops up.
- ✅ Wired `language`, `region`, `audience_type` into the Ollama prompt.
- ✅ Added competitor view counts to the prompt for pattern signal.
- ✅ Removed `random.uniform()` title scoring — replaced with a deterministic
  length + topic-presence score.
- ✅ Removed legacy `HF_TOKEN` from `.env`.

## Project maturity

| Area | Score | Note |
|---|---|---|
| Core SEO pipeline (with Ollama) | 7.5/10 | Ollama is wired correctly, prompts have language + competitor context, topic_lock no longer mutilates output. Quality cap is the model. |
| Core SEO pipeline (Ollama offline) | 5/10 | Deterministic fallback. Topic-locked but template. Acceptable as emergency, not as primary. |
| YouTube research | 7/10 | Real API, key rotation, cache, quota handling. View counts now reach the LLM. Engagement-ratio signal still on table. |
| Multilingual (Tamil / Tanglish) | 6/10 with Ollama / 2/10 without | Prompt now has explicit language instructions per language. Fallback is English-only. |
| Architecture cleanliness | 7/10 | Cleaner after deletion of ~7,400 LOC of dead/template code. Sync handler and 35-field schema are remaining smells. |
| Local-machine fit (i5-12HX / 12 GB) | 9/10 | spaCy ~150 MB, no torch, no transformers. Ollama with mistral 7B fits in 12 GB. |
| Production safety (single-user) | 7/10 | Rate limiter present, error handlers present, Ollama failure-tolerant. No auth/secrets management because not needed for local use. |
| Testing | 1/10 | Three case JSONs in repo root, one ad-hoc `test_payloads.py`. No pytest suite, no CI. |
| Documentation | 6/10 | This file + README. No API contract doc beyond Swagger at `/docs`. |

**Overall: ~6.5/10 for the stated use case.**

## Next priorities (ranked by impact)

1. **User installs Ollama and pulls `mistral`.** Unblocks every other quality
   improvement. ETA: 5 minutes.
2. **Verify Ollama-on output quality** with 3 real videos in English / Tamil
   / Tanglish. Tune the system prompt + temperature based on what comes out.
3. **Pass engagement metrics to the prompt.** Title alone is weak signal.
   Adding `(view_count, like_count, comment_count)` to each competitor entry
   lets the model say "this pattern works *because* it correlates with high
   engagement." ~10 LOC in `seo_writer._build_competitor_block`.
4. **Make `/analyze` async.** Use `httpx.AsyncClient` for YouTube and
   `ollama_client.agenerate` for the LLM. Frees the event loop. ~20 LOC.
5. **Singleton `ResearchService`** at app-create time, injected as a
   FastAPI dependency. ~10 LOC.
6. **Reduce response schema bloat.** Move 20+ analysis fields into an
   `extras: dict[str, Any]` and stop validating them strictly.
7. **Real tests.** A small pytest suite covering: `/analyze` happy path,
   `/analyze` with Ollama offline, topic_lock not over-firing, multilingual
   prompt routing. ~150 LOC.
8. **Tamil/Tanglish fallback.** When Ollama is offline and user requested
   Tamil/Tanglish, return an explicit `research_warnings` entry rather than
   silently returning English output.
9. **YouTube OAuth (future).** Currently uses public API key. If the user
   later wants `/my-videos`-style features (own-channel analytics), needs
   OAuth. Out of scope for current use case.
10. **Deploy-ability (future).** Dockerfile exists. Compose works. No
    Kubernetes, no Helm — that ship has sailed and was the right call.

## What still blocks "real creator-quality output"

1. **Ollama not installed.** Period. The architecture is now correct; the
   model needs to be there. Without it, the fallback path produces
   topic-locked-but-templated copy. That is not what a real creator wants
   to paste into YouTube.

2. **Prompt quality past mistral 7B**. Mistral 7B is the floor. For
   genuinely creator-quality Tamil output, a larger model
   (`llama3:8b`, `qwen2.5:7b`, or a Tamil-tuned model) will produce better
   natural rhythm. The user can swap by setting `OLLAMA_MODEL` in `.env`.

3. **Engagement signal**. The prompt currently sees competitor titles +
   view counts. Adding like-to-view and comment-to-view ratios would let
   the model reason about *what kind* of engagement these titles drove.

4. **Niche-specific prompt tuning**. One generic system prompt for all
   niches is leaving quality on the table. A per-category prompt header
   (gaming / education / vlog / finance / cooking) would lift output
   another notch — but only worth doing after seeing baseline mistral
   output for a few real videos.

Stop here. Do not add features 5 through 50 until 1 through 4 are tested
with real videos.
