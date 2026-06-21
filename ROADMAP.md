# Project Status & Roadmap

Local AI-powered YouTube SEO engine. Single-user, 2-5 videos/day on a Lenovo
LOQ (i5-12HX / RTX 2050 / 12 GB RAM). Not a SaaS, not a multi-tenant tool (today).

> **Updated 2026-06-21** after a full-codebase audit. This file is the honest,
> audit-corrected state. Companion documents: `PROJECT_UNDERSTANDING.md`,
> `TECHNICAL_AUDIT.md`, `BUG_REPORT.md`, `ARCHITECTURE_REVIEW.md`,
> `CLEANUP_PLAN.md`, and the prioritized `ACTION_PLAN.md`.

---

## Current status (verified 2026-06-21)

- `POST /analyze` works end-to-end, both with Ollama (LLM path) and without it
  (deterministic topic-locked fallback). App boots cleanly in Docker; all routes
  register; `/health` returns `database_ok: true`.
- The repo runs in Docker via `docker compose up --build` (app + Redis; Ollama
  reached on the host via `host.docker.internal`).
- **Maturity:** good as a *local tool* (~6/10). **Not** production/commercial ready
  (~3.5/10) — see scorecard below.
- The audit found the apparent surface is larger than the running surface:
  ~700+ LOC of unwired code, an unused ~150 MB dependency, and several
  silent-failure bugs.

### Corrections to earlier claims (now verified false/overstated)
- ❌ **"spaCy keyword + entity extraction"** — spaCy is in `requirements.txt` but
  **never imported**. Extraction is pure regex. (BUG-2)
- ⚠️ **"Brain v2.0 / 90%+ accuracy" CTR** — it's a hand-tuned heuristic with an
  unused `title_score` param and a dead seasonality branch. (BUG-8)
- ⚠️ **`ai_uniqueness_score`** — permanently `0.5` due to a swallowed broken import. (BUG-1)
- ⚠️ **TTL cache** — does not work across requests in the default no-Redis config,
  because `ResearchService` is rebuilt per request. (BUG-3)

---

## What is complete

- Layered FastAPI app: factory, error envelope, request-id middleware, rate limiting.
- YouTube Data API v3: search + video stats + channel stats, key rotation, quota rollover.
- Ollama-first SEO generation with deterministic, topic-locked fallback.
- Topic-lock safety layer: risk-term normalization, junk-tag filtering, topic enforcement,
  idea-mode expansion.
- SQLite history (`video_snapshots`, `analysis_runs`) feeding the feedback package
  (CTR prediction, A/B pack, historical comparison, winning patterns).
- Single-port HTML dashboard at `/`; `/health`, `/ready`, `/meta`, `/diagnostics`.
- Docker build + compose (verified). DevOps (Jenkins) and earlier K8s/Helm removed.

## What is missing

- **Tests / CI** — none.
- **Production hardening** — auth is a no-op in the default `development` environment;
  `/diagnostics` is public by default; no log rotation (log written to CWD).
- **Secrets management** — a live API key currently sits in `.env` (rotate it).
- **Working cache across requests** — defeated by per-request service construction.
- **Multilingual reach from the UI** — dashboard only sends `{script}`; language/region/
  audience controls are absent (backend supports them).
- **Honest analytics** — 4 of 6 DB tables are unused; "deep learning"/"pattern memory"
  subsystems are written but never wired in; learning data mixes LLM and fallback runs.
- **Multi-tenancy** — global SQLite, no `user_id`, no per-user isolation/authz.

---

## Scorecard

| Dimension | Score | Note |
|---|:--:|---|
| Code Quality | 6.5/10 | Clean per file; ~700 LOC dead code + silent excepts. |
| Security | 4/10 | Open dev auth, public diagnostics, leaked key, XSS surface. |
| Reliability | 6/10 | Strong failure-tolerance; undermined by silent-wrong bugs + dead cache. |
| Maintainability | 6/10 | Readable locally; dead code masquerades as live; no tests. |
| Production Readiness | 3.5/10 | No tests/CI, no default auth, no log rotation, blocking handler. |

**Overall: ~6/10 local · ~3.5/10 production.**

---

## Next milestones

### Milestone 1 — Trustworthy local build (≈1–2 days)
Delete dead code (CLEANUP Groups 1–2), drop spaCy + fix docs (H2), fix/remove
`ai_uniqueness_score` (C5/BUG-1), restore the cache via a singleton `ResearchService`
(H1), move Ollama config into `Settings` (H4), segment learning data (H5).
**Exit:** running surface == apparent surface; cache actually hits; docs accurate.

### Milestone 2 — Safe single-user production (≈1 week, Goal A)
Rotate the key (C1), close the auth posture (C2/C3), add log rotation (H6), document
secrets injection (H7), add a minimal pytest smoke suite + CI (C6). Optionally async
the handler (M1).
**Exit:** deployable without leaking secrets, quota, or disk; `/analyze` covered by tests.

### Milestone 3 — Commercial foundation (≈2–4 weeks, Goal B)
Fix XSS (C4), full test suite + CI gate, introduce multi-tenancy (per-user data
isolation, authn/authz, per-user rate limits, Postgres instead of file SQLite),
observability (metrics/error tracking), and decide Phase 9/10 schema (implement or
remove, M4).
**Exit:** multiple users can be served safely with isolated data.

### Milestone 4 — Sellable product (≈6–10 weeks total, Goal C)
Remove/make-true every overclaim (spaCy, "Brain v2.0", uniqueness, chapters);
make the Ollama dependency a product decision (host/bundle a model, or sell fallback as
"basic mode"); invest in output quality (engagement signals in prompt = F1, per-niche
prompts = F2); add billing, support, data-retention policy, and YouTube API ToS/quota
economics review.
**Exit:** a defensible v1 SKU whose advertised capabilities all actually run.

---

## Verified architecture (unchanged, still accurate)

```
User script
    │
    ▼  POST /analyze  (FastAPI, sync handler)
ResearchService.gather()
    │  - YouTube Data API v3 search + video stats + channel stats
    │  - TTL cache (in-memory or Redis)  ← in-memory variant is per-request today (BUG-3)
    │  - Outlier scoring + keyword/entity extraction (regex, NOT spaCy)
    ▼
generate_seo_suggestions()
    │  - Topic-lock pre-process (risk normalization, category, main topic, idea expansion)
    │  - build_seo_package() — Ollama-first
    │       ├─► write_seo_package() → single Ollama JSON call (title/variants/desc/tags/hashtags)
    │       └─► deterministic fallback (topic-locked template) when Ollama offline
    └─► Topic-lock post-process (force_topic_in_* validators)
        ▼
    AnalyzeResponse (35 fields) → dashboard renders ~5
```

Enrichment on top: content audit, opportunity gap, channel intelligence, content graph,
chapters, session expansion, binge bridge, thumbnail strategy, automation workflow,
feedback package.

---

## Guiding principle

The architecture is sound. The core work is to **make the running surface match the
apparent surface** — delete what doesn't run, fix what silently lies, harden for
deployment — *then* invest in prompt/output quality, which is the real product value.
Do not add new features until Milestone 1 + the Critical items in `ACTION_PLAN.md` are done.
</content>
