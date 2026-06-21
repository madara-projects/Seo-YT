# SEO OUTPUT QUALITY REPORT

> Date: 2026-06-21 · Goal: creator-quality local output (English/Tamil/Tanglish),
> single creator, 2–5 videos/day, local Ollama. Enterprise/SaaS concerns excluded.
> Phases 1–3 below changed no code. Phase 4 (top-3 implementation) is in the CHANGELOG.

---

## PHASE 1 — Quality audit (evidence from source)

### Two findings that dominate everything else

**F0 — Ollama is offline → only the template fallback ever runs.**
Verified live: `ollama_client.is_available()` → `False`. When offline,
`write_seo_package` returns `None` ([seo_writer.py:194-195](win_engine/llm/seo_writer.py#L194))
and `build_seo_package` uses `_fallback_package` ([strategy_engine.py:72](win_engine/generation/strategy_engine.py#L72)),
which is a deterministic English template ([strategy_engine.py:249-292](win_engine/generation/strategy_engine.py#L249)).
**No code change can produce creator-quality output until Ollama + a model are installed.**

**F1 — The UI can't request Tamil/Tanglish.**
The dashboard posts only `{ script }` ([routes.py:423](win_engine/api/routes.py#L423)).
`AnalyzeRequest.language` defaults to `"english"` ([schemas.py:10](win_engine/core/schemas.py#L10)),
so `build_language_strategy` always sees `selected_language="english"`
([language_engine.py:16,21-22](win_engine/analysis/language_engine.py#L16)) and the prompt
is always built for English ([seo_writer.py:52-56](win_engine/llm/seo_writer.py#L52)).
**Result: one request = one language, and the UI locks it to English.**

### 1. What currently limits output quality?
- **Single weak signal to the model.** The competitor block sends only `title (views)`
  ([seo_writer.py:71-89](win_engine/llm/seo_writer.py#L71)); like/comment/subscriber/
  duration are fetched ([youtube_client.py:88-93](win_engine/ingestion/youtube_client.py#L88))
  then discarded. The model can't reason about *why* a title won.
- **One generic system prompt** for every niche ([seo_writer.py:21-26](win_engine/llm/seo_writer.py#L21)),
  even though `category` is already inferred ([topic_lock.py:167](win_engine/analysis/topic_lock.py#L167))
  and never used in the prompt.
- **High temperature (0.7) + 900-token cap** ([seo_writer.py:176-177](win_engine/llm/seo_writer.py#L176)).
  0.7 drifts off-topic for SEO copy; 900 tokens can truncate the JSON on a 7B model →
  parse fail → silent fallback.
- **Dead cache** ([routes.py:836](win_engine/api/routes.py#L836) rebuilds `ResearchService`
  per request) → competitor set changes between re-runs of the same idea → inconsistent
  suggestions.

### 2. Why do some outputs still feel generic?
- **Topic-lock injects robotic boilerplate.** `force_topic_in_description` prepends
  `"{Topic} - complete guide. "` whenever the topic isn't literally present
  ([topic_lock.py:299-302](win_engine/analysis/topic_lock.py#L299)).
- **Tags get flooded with generic fillers.** `force_topic_in_tags` tops up with
  `CATEGORY_FALLBACK_KEYWORDS` ([topic_lock.py:319-326](win_engine/analysis/topic_lock.py#L319)),
  e.g. vlog → `daily vlog, morning routine, weekend vlog, lifestyle, day in life, real life`
  ([topic_lock.py:80-83](win_engine/analysis/topic_lock.py#L80)).
- **The fallback itself is template Mad-Libs:** `How to {X} (Step-by-Step)`,
  `{X}: Real Methods That Work` ([strategy_engine.py:257-263](win_engine/generation/strategy_engine.py#L257)).
  Since Ollama is off, this is *all you see today*.

### 3. What prevents creator-quality results?
F0 (no Ollama) + the single-signal, niche-blind, high-temperature prompt + the
genericizing post-process. Even with Ollama on, the prompt isn't good enough to
consistently beat a human.

### 4. What prevents strong Tamil/Tanglish?
- F1 (UI can't select them).
- **Language-key mismatch:** `language_engine` can emit `"hinglish_or_hindi"` /
  `"spanish_like"` ([language_engine.py:25-30](win_engine/analysis/language_engine.py#L25)),
  but `_LANGUAGE_INSTRUCTIONS` only has `english/tamil/tanglish/hindi`
  ([seo_writer.py:28-49](win_engine/llm/seo_writer.py#L28)) → those fall back to English
  silently ([seo_writer.py:52-56](win_engine/llm/seo_writer.py#L52)).
- **No few-shot examples.** The Tamil/Tanglish instructions are prose only
  ([seo_writer.py:33-44](win_engine/llm/seo_writer.py#L33)); a 7B model follows *examples*
  far better than adjectives.
- **English-only fallback with no warning** — selecting Tamil with Ollama off silently
  yields English ([strategy_engine.py:249](win_engine/generation/strategy_engine.py#L249)).

### 5. What prevents better competitor-aware recommendations?
- Engagement metrics discarded before the prompt (see §1).
- **`ai_uniqueness_score` is permanently fake** — broken swallowed import
  ([gap_engine.py:34-43](win_engine/analysis/gap_engine.py#L34)); always `0.5`.
- Dead cache means the competitor sample shifts run-to-run.

### 6. What prevents better niche-specific generation?
`category` is computed ([topic_lock.py:167-177](win_engine/analysis/topic_lock.py#L167))
and passed around ([seo_generator.py:37,49](win_engine/generation/seo_generator.py#L37))
but **never reaches the Ollama prompt**. The model treats a finance script and a gaming
script identically.

---

## PHASE 2 — Top 10 improvements (ranked strictly by creator value)

| # | Change | Impact | Effort | Files | Why it matters |
|---|---|:--:|---|---|---|
| 1 | **Install Ollama + pull a model** (user action, not code) | 10 | S | — | Nothing is creator-quality without it. The #1 lever, full stop. |
| 2 | **Multi-language output**: every `/analyze` returns English **and** Tamil **and** Tanglish packages; UI renders all three | 10 | M | seo_writer, strategy_engine, seo_generator, schemas, routes | Directly the success metric; today impossible (F1). |
| 3 | **Engagement-rich competitor block** (like/view, comment/view, duration) | 9 | S | seo_writer, strategy_engine | Lets the model reason about *why* titles win, not just mimic words. |
| 4 | **Few-shot Tamil/Tanglish examples** in the prompt | 9 | S | seo_writer | Biggest lever for natural non-English output on a 7B model. |
| 5 | **Per-niche system prompt** from the already-inferred `category` | 8 | S | seo_writer, strategy_engine | Gaming vs finance vs vlog need different voice/rhythm. |
| 6 | **De-genericize topic-lock** (stop the "complete guide" prefix + tag flooding) | 8 | S | topic_lock | Removes the most obvious "template smell". |
| 7 | **Tune generation** (temp ~0.5, larger token budget, truncation-safe parse) | 7 | S | seo_writer | Tighter on-topic titles; fewer silent fallbacks. |
| 8 | **Fix language-key mismatch + trust selected language** | 7 | S | seo_writer, language_engine | Stops Tamil/Hindi requests silently becoming English. |
| 9 | **Real uniqueness score** via existing Jaccard, fed into differentiation (fixes the C5 bug) | 6 | S | gap_engine, ai_enhancement | Turns a fake constant into a real "are you uploading a clone?" check. |
| 10 | **Singleton `ResearchService`** (stable competitor set, working cache) | 6 | S–M | routes, research_service | Consistent suggestions across re-runs; less quota burn. |

---

## PHASE 3 — Execution plan (creator-quality only)

**Priority 1 — biggest quality jumps (do first)**
- P1.1 Install Ollama + `ollama pull mistral` (or `qwen2.5:7b` for better Tamil). *(user)*
- P1.2 Multi-language output (#2).
- P1.3 Prompt upgrade bundle: engagement context (#3) + few-shot (#4) + per-niche (#5)
  + tuned params (#7) + language-key fix (#8).

**Priority 2 — important**
- P2.1 De-genericize topic-lock (#6).
- P2.2 Real uniqueness + differentiation feed (#9).
- P2.3 Honest fallback warnings for non-English when Ollama is offline.

**Priority 3 — nice-to-have**
- P3.1 Singleton `ResearchService` / working cache (#10).
- P3.2 Dynamic chapter timestamps from script length.
- P3.3 UI controls for region/audience (Tamil Nadu / diaspora nuance).

**Explicitly out of scope:** SaaS, multi-user, auth, K8s, CI/CD expansion, billing, scaling.

---

## What got implemented now (Phase 4)

The **top 3** by creator value that are *also safe to ship and testable with Ollama
offline*:

- **Implementation A — Prompt upgrade** (#3+#4+#5+#7+#8).
- **Implementation B — Multi-language output** (#2) with honest offline fallback (P2.3).
- **Implementation C — De-generic topic-lock + real uniqueness** (#6+#9).

See `CHANGELOG.md`. Note: with Ollama offline these are validated on the *fallback path*
(structure, plumbing, no regressions). The real Tamil/Tanglish creator-quality output
appears the moment you complete **P1.1 (install Ollama)** — the architecture is now ready
for it.
</content>
