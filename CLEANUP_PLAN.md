# CLEANUP_PLAN.md

> Audit date: 2026-06-21. **Nothing has been deleted.** This is a proposal with
> evidence and confidence levels. Confidence = likelihood deletion is safe.
> Each item lists references found (call sites) to justify the call.

Legend: **SAFE** = no references anywhere · **LIKELY SAFE** = referenced only by other
dead code · **VERIFY FIRST** = has live references or external/runtime implications.

---

## Group 1 — Whole files safe to delete

### 1.1 `win_engine/feedback/deep_learning_engine.py` — **LIKELY SAFE**
- **Reason:** `DeepLearningEngine` is imported once and never instantiated.
- **References:** import at [learning_engine.py:7](win_engine/feedback/learning_engine.py#L7)
  only; no construction, no method calls anywhere (grep).
- **Action:** delete file **and** remove the import line. 337 LOC.
- **Confidence:** High.

---

## Group 2 — Functions/methods safe to delete (within live files)

| Symbol | File:line | Reason | References found | Confidence |
|---|---|---|---|---|
| `_ctr_prediction` (v1) | [learning_engine.py:46-64](win_engine/feedback/learning_engine.py#L46) | Superseded by `_ctr_prediction_v2` | None | High |
| `build_pattern_memory_package` | [learning_engine.py:228-245](win_engine/feedback/learning_engine.py#L228) | Never called | None outside file | High |
| `enrich_feedback_with_patterns` | [learning_engine.py:248-276](win_engine/feedback/learning_engine.py#L248) | Never called | None | High |
| `pattern_memory_summary` | [learning_engine.py:279-300](win_engine/feedback/learning_engine.py#L279) | Never called | None | High |
| `HistoryStore.performance_correlation` | [history_store.py:431-487](win_engine/feedback/history_store.py#L431) | Only used by `build_pattern_memory_package` (dead) | transitively dead | High |
| `HistoryStore.success_formula_recognition` | [history_store.py:489-560](win_engine/feedback/history_store.py#L489) | same | transitively dead | High |
| `HistoryStore.trend_analysis` | [history_store.py:562-644](win_engine/feedback/history_store.py#L562) | same | transitively dead | High |
| `HistoryStore.memory_persistence` | [history_store.py:646-726](win_engine/feedback/history_store.py#L646) | same | transitively dead | High |
| `HistoryStore.creator_baseline` | [history_store.py:728-778](win_engine/feedback/history_store.py#L728) | same | transitively dead | High |
| `_idea_kill_switch` | [gap_engine.py:143-182](win_engine/analysis/gap_engine.py#L143) | Replaced by `get_dynamic_kill_switch` | None | High |
| `performance_logger` | [logging.py:101-133](win_engine/core/logging.py#L101) | Never used | None | High |

> Deleting Group 1 + Group 2 removes ~700+ LOC with zero behavioral change.

---

## Group 3 — Dead computation to remove (VERIFY FIRST — small behavioral surface)

### 3.1 `ai_insights` / `ai_quality_analysis` block — **VERIFY FIRST**
- **Where:** [strategy_engine.py:161-167,189-190](win_engine/generation/strategy_engine.py#L161).
- **Reason:** computed every request, added to the package dict, but **never read** by
  `seo_generator` and **not** part of `AnalyzeResponse`.
- **References:** `ai_insights`/`ai_quality_analysis` keys are only set, never gotten.
- **Caveat:** removing also makes `win_engine/ai_enhancement.py` (`get_ai_insights`,
  `analyze_content_quality_ai`, `find_content_similarity`) fully unused → that file
  could then be deleted too (133 LOC).
- **Confidence:** Medium-High. Verify no future plan needs it before deleting.

### 3.2 Broken `ai_uniqueness_score` block (BUG-1) — **VERIFY FIRST**
- **Where:** [gap_engine.py:33-43,57](win_engine/analysis/gap_engine.py#L33).
- **Decision needed:** either (a) fix the import to real semantic logic, or (b) remove
  the always-0.5 field. Don't leave it pretending to be a signal.
- **Confidence:** High that it's broken; the *choice* is a product call.

---

## Group 4 — Unused DB tables (VERIFY FIRST — data/migration implications)

`video_uploads`, `performance_metrics`, `ab_tests`, `scheduled_uploads`
([history_store.py:73-133](win_engine/feedback/history_store.py#L73)).
- **Reason:** created but never read/written (no `INSERT`/`SELECT` — grep).
- **Caveat:** the existing on-disk `win_engine.db` already contains these empty tables;
  removing the `CREATE TABLE` statements is safe for new DBs and harmless for existing
  ones (the tables just remain unused). **Do not** drop tables from a DB you intend to
  keep without a migration note.
- **Confidence:** High that they're unused; Medium on "delete now" vs "keep as planned
  schema" — depends on whether Phase 9/10 (uploads/scheduling) is still on the roadmap.

---

## Group 5 — Dependency & docs cleanup (VERIFY FIRST)

### 5.1 Remove spaCy from `requirements.txt` — **VERIFY FIRST**
- **Where:** [requirements.txt:9-10](requirements.txt#L9).
- **Reason:** never imported (BUG-2). Removing it shrinks the image ~150 MB and speeds
  the Docker build noticeably.
- **Caveat:** confirm no out-of-tree script relies on it; update README
  ([README.md:67](README.md#L67)) and ROADMAP ([ROADMAP.md:52](ROADMAP.md#L52)) to stop
  claiming spaCy extraction.
- **Confidence:** High (code), but flagged VERIFY because it touches build + docs.

---

## Group 6 — Already removed in the preceding task (recorded for completeness)

These were deleted just before this audit (DevOps/test cleanup):
`Jenkinsfile`, `Dockerfile.jenkins`, `setup-jenkins.ps1`, `jenkins_home/`,
`test_payloads.py`, `case1_gaming_risky.json`, `case2_education_long.json`,
`case3_idea_mode_short.json`, `win_engine.log`. No action needed.

---

## Items intentionally NOT recommended for deletion

| Item | Why keep |
|---|---|
| `win_engine.db` | Live runtime state (`video_snapshots`, `analysis_runs`); volume-mounted by compose. |
| `ctr_prediction_v2.py` / `dynamic_thresholds.py` | **Live** — called by `learning_engine` / `gap_engine` respectively (despite the overclaimed naming). Has dead *branches* (BUG-8) but the modules are wired in. |
| `automation_engine.py`, `expansion_engine.py` | Live — called by `build_seo_package`. |
| `ai_enhancement.py` | Only becomes deletable **after** Group 3.1. Keep until that decision. |
| `.env` | Required at runtime (but **rotate the leaked key**). |

---

## Suggested order of operations (when cleanup is approved)

1. Group 1 + Group 2 (pure dead code — zero risk).
2. Group 3 (remove dead computation; then optionally delete `ai_enhancement.py`).
3. Group 5 (drop spaCy + fix docs) — biggest image/build win.
4. Group 4 (decide: keep planned schema vs remove) — needs product input.
5. Re-run the app + a `/analyze` smoke test after each group.

**Estimated reduction:** ~830–1,000 LOC and ~150 MB image, with no change to observable
`/analyze` output (Groups 1, 2, 3.1, 5).
</content>
