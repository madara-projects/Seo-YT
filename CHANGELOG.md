# Changelog

## [Unreleased] — 2026-06-21 — Creator-quality output: multi-language + better prompting

Goal: make the generated YouTube package significantly better for a single local
creator (English / Tamil / Tanglish), per `QUALITY_REPORT.md`. Three highest-value
improvements implemented. No code deleted. No SaaS/multi-user/infra changes.

### Added
- **Multi-language SEO packages.** Every `POST /analyze` now returns a new
  `multilang` object with **English, Tamil, and Tanglish** packages
  (title, 5 variants, description, tags, hashtags) from a single request — the core
  success metric. The dashboard renders them in a new "Upload-Ready Packages" section.
  - `win_engine/llm/seo_writer.py`: new `write_multilang_packages()` (one Ollama
    reachability check, then one generation per language) + `_generate_one()` helper.
  - `win_engine/generation/strategy_engine.py`: generates the three languages, uses
    the English package as the base for downstream analysis, tracks
    `fallback_languages`.
  - `win_engine/generation/seo_generator.py`: topic-locks each language package
    (English-only description fallback) and surfaces `multilang`.
  - `win_engine/core/schemas.py`: added `multilang: Dict[str, Any]` to `AnalyzeResponse`.
  - `win_engine/api/routes.py`: dashboard section + render logic for the three packages.
- **Honest offline fallback warning.** When Ollama is offline/returns nothing,
  Tamil/Tanglish fall back to an English template **and say so** in
  `research_warnings` (previously silent). `win_engine/generation/seo_generator.py`.

### Changed — prompt quality (`win_engine/llm/seo_writer.py`)
- **Engagement-rich competitor context:** the prompt now includes like-rate and
  comments-per-1k alongside views (previously title + views only), so the model can
  reason about *why* a title performs.
- **Per-niche voice guidance:** the inferred `category` (gaming/education/finance/
  tech/fitness/cooking/vlog/general) now injects niche-specific guidance into the prompt.
- **Few-shot examples** for English / Tamil / Tanglish (a 7B model follows examples
  far better than prose instructions).
- **Language-key alias fix:** `hinglish_or_hindi` → `hindi`, `spanish_like` → `english`,
  so non-English requests stop silently degrading to the default English instruction.
- **Tuned generation:** default `temperature` 0.7 → **0.5** (tighter, on-topic copy);
  `max_tokens` 900 → **1100** (fewer truncated-JSON silent fallbacks).
- `win_engine/generation/strategy_engine.py`: competitor entries now carry
  likes/comments/subscribers/duration; `category` passed into generation.

### Changed — less "template smell" (`win_engine/analysis/topic_lock.py`)
- `force_topic_in_description`: **stopped prepending** the robotic
  `"{Topic} - complete guide. "`; real descriptions are now left untouched (only an
  empty description gets a minimal topic line).
- `force_topic_in_tags`: generic category fallbacks are now added **only when the
  model produced too few real tags** (< 6), instead of always flooding output with
  filler like `daily vlog, lifestyle, real life`.
- `_title_is_broken`: **Tamil-script titles are no longer flagged "broken"** and
  regenerated into English (a pure non-Latin title previously had no `[A-Za-z]` words
  and was wrongly rejected). Critical for real Tamil output.

### Fixed — real uniqueness signal (`win_engine/analysis/gap_engine.py`)
- `ai_uniqueness_score` was **permanently `0.5`** due to a broken import
  (`win_engine.analysis.ai_enhancement.get_ai_engine` — module doesn't exist) swallowed
  by a bare `except`. Now computes a **real** score:
  `1 − max(word-overlap similarity of your title vs the top 5 competitor titles)`,
  reusing the existing `win_engine.ai_enhancement.find_content_similarity` (no new deps).
  `analyze_opportunity_gaps()` gained a `target_title` parameter; the broken import and
  the swallowing `except` are gone.

### Validation
- `py_compile` clean on all edited files.
- Docker image rebuilt; container reports **healthy**; `create_app()` boots.
- `POST /analyze` → HTTP 200 for the target input
  ("My video is about my daily office life vlog and personal experiences") and a
  short-idea input. Response contains `multilang` with all three languages;
  `ai_uniqueness_score` = 0.875 (real); honest Tamil/Tanglish fallback warning present.
- `GET /` renders the new multilang section; `GET /health` → 200.

### Notes / known issues (NOT introduced by this change)
- **Ollama is offline in the current environment**, so Tamil/Tanglish currently fall
  back to the English template (and now say so). The architecture is ready; genuine
  native-language output appears once Ollama is installed:
  `ollama pull mistral` (or `qwen2.5:7b` for stronger Tamil). This is the single
  biggest remaining quality lever — see `QUALITY_REPORT.md` P1.1.
- A **pre-existing** logging misconfiguration (`structlog.stdlib.filter_by_level` in
  `win_engine/core/logging.py` `foreign_pre_chain`) emits "Logging error … isEnabledFor"
  noise on stderr. It does not affect `/analyze` output and was present before this
  change (see TECHNICAL_AUDIT.md §K). Left untouched to honor "top-3 only, no
  speculative changes".
- Performance note: with Ollama on, `/analyze` now makes up to 3 model calls (one per
  language). Acceptable for 2–5 videos/day; revisit if latency matters.
</content>
