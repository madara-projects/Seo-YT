# SEO YT Personal Growth Engine

SEO YT is a private, local-first YouTube research, packaging, analytics, and learning application for one creator. It runs in Docker on the creator's laptop and uses FastAPI, SQLite, Redis, the YouTube Data and Analytics APIs, and Google Gemini.

The application turns a real video script or content description into an upload-ready package, preserves that package in History, links it to the creator's published YouTube video, retrieves the actual uploaded metadata and performance, and gradually builds channel-specific evidence for future recommendations.

SEO YT is an advisory tool. It does not guarantee views, reach, CTR, virality, subscribers, or a fixed growth percentage.

## Current status

Current application version: `0.9.0`

Implemented and available now:

- Script/content analysis with a structured creator brief.
- Google Gemini generation with a clearly labeled local fallback when Gemini is unavailable.
- One selected output language per run to reduce Gemini quota use.
- English, Tamil, and Tanglish-oriented generation workflows.
- Five title variants, description, tags, hashtags, upload-time evidence, and pacing guidance.
- Search, Browse, and Existing Audience packaging angles.
- YouTube API research, competitor-result analysis, keyword/entity extraction, possible outlier signals, and transparent Opportunity Score components.
- Permanent SQLite package History.
- Read-only YouTube OAuth connection and channel analytics.
- Fail-closed package-to-owned-video linking with stored ownership provenance.
- Comparison of generated metadata with the actual uploaded title, description, tags, and hashtags.
- Separate current display snapshots and retryable 24-hour, 7-day, and 28-day evidence windows.
- Linked-video performance diagnosis with evidence and confidence labels.
- Cohort analytics and Gemini learning guarded by one 5/10/20 evidence policy.
- Package-experiment persistence endpoints.
- Versioned SQLite migrations, verified backup-before-migration, enforced foreign keys, and transactional deletion.
- Local rate limiting, request IDs, security headers, encrypted OAuth refresh-token storage, Redis research caching, and SQLite WAL mode.
- Docker health check and localhost-only application binding.
- Production Compose verification completed on 16 August 2026: `redis` and `win-engine` are healthy/running, static and rollback routes return HTTP 200, and the application image contains no Playwright, Chromium, Node, or Ollama.
- Truthful loading, unavailable, and evidence-provenance states across the dashboard, plus one shared frontend API/error layer that preserves request IDs.
- Advanced Creator brief values persist through accordion collapse and are submitted in the single intentional Analyze request.
- Collector status clearly distinguishes disabled, dry-run, and unavailable/error states; collector remains disabled by default.
- Phase 3C local static frontend extraction: FastAPI serves same-origin HTML/CSS/native ES modules, with shared API/error/state/navigation modules and a `/dashboard_legacy` rollback route.
- Complete Phase 3D Creator decision workflow: Idea, Brief, Research, Angle, Packaging, Compare, Decision, and Checklist.
- Deterministic local package comparison and selection, evidence-aware decision summaries, manual pre-publish acknowledgments, safe copy, and full JSON export. Selection/checklist state remains local and never publishes or changes YouTube.
- Creator rendering and behavior are owned by `pages/creator.js`; the temporary Creator compatibility renderer and window bridge were removed from `app.js`.
- 68 automated backend tests and 27 deterministic Chromium browser tests (95 tests in the full local discovery run; browser tooling stays outside production Docker).

Planned but not yet complete:

- Ideas workspace and lifecycle tracking.
- Saved competitor/outlier watchlists and daily opportunity research.
- Honest topic-demand explorer.
- Complete visual Experiment Center and thumbnail/first-frame laboratory.
- Hook and retention assistant.
- Personal AI coach and weekly private report.
- Remaining page-level frontend modularization, installable PWA, and an approved Android architecture.
- Encrypted backup/restore and quota dashboard.

See [ROADMAP.md](ROADMAP.md) for the exact implementation sequence, data rules, and acceptance checks.

## Main workflow

```text
Video script or content description
              |
              v
Creator brief + approved YouTube research
              |
              v
Gemini SEO package or labeled local fallback
              |
              v
Local comparison, selection, decision, and checklist
              |
              v
Saved package in SQLite History
              |
              v
Manual YouTube upload by the creator
              |
              v
Link the owned YouTube video to the package
              |
              v
Actual metadata + real performance snapshots
              |
              v
Comparable cohort evidence for future decisions
```

The creator always decides what to publish or change. SEO YT does not automatically upload videos or edit live YouTube metadata.

## Dashboard pages

| Page | Current purpose |
|---|---|
| Dashboard | Channel summary, recent activity, diagnostics, and shortcuts. |
| Creator Studio | Move from idea and brief through research, angle, packaging, local comparison/selection, final decision, and a manual pre-publish checklist. |
| Analytics | View connected-channel metrics, owned videos, linked-video snapshots, and cohort-learning status. |
| History | Open complete saved packages, copy their contents, link an owned published video, and review actual metadata and performance. |
| Settings | Inspect YouTube OAuth, AI configuration, collector state, and local application diagnostics. |

## Generated package

A successful Creator Studio run can include:

- Primary recommended title and five materially different variants.
- Title quality heuristic. This is not a CTR prediction.
- Natural video-specific description.
- Focused YouTube tags and one to three hashtags.
- Required creator-selected Shorts tags when the content is a Short.
- Search, Browse, and Existing Audience title/thumbnail directions.
- Local comparison cards with deterministic package IDs, source labels, title-quality heuristics, thumbnail direction, and why-suggested context.
- A local selection summary that separates public observations, local heuristics, generated/AI suggestions, and unavailable post-publish evidence.
- A manual checklist plus copy/export actions; the exported JSON includes the complete analysis and a clearly labeled local workflow summary.
- Creator brief and content audit.
- Research queries, relevant public results, keyword/entity signals, and possible gaps.
- Opportunity Score based on visible research signals. This is not a probability of growth.
- Observed competitor publishing-time guidance with evidence count and limitations.
- Format-specific pacing guidance.

Gemini output is validated and stored with its generation source. If Gemini is unavailable, the application displays `FALLBACK` and does not claim that the fallback came from Gemini.

## YouTube linking and personal learning

After manually uploading a video:

1. Open `History`.
2. Select `Link Video` or change the existing link.
3. Paste the YouTube video URL or 11-character video ID.
4. SEO YT verifies that the connected channel owns the video.
5. The application stores the relationship between the generated package and published video.
6. Open the package and select `Refresh YouTube data` when a new observation is needed.

The linked report can show:

- Actual uploaded title, description, tags, hashtags, thumbnail, duration, and publication time.
- Whether the generated title was used exactly.
- Description overlap and generated tags/hashtags that were used.
- Views, likes, comments, like rate, average view duration, average percentage viewed, and subscribers gained when available.
- Current, 24-hour, 7-day, and 28-day snapshots when collected.
- A conservative diagnosis, comparison baseline, sample size, and confidence.

YouTube APIs report video-level outcomes; they do not prove that an individual tag, title, background, or upload time caused the views. Missing or delayed Analytics values are displayed as unavailable rather than guessed.

Only a verified owned link with comparable format/language metadata and a completed named snapshot window can become learning evidence. Current metrics are display-only. Confidence is `Collecting evidence` below five comparable videos, `Early signal` at 5, `Moderate evidence` at 10, and `Strong historical pattern` at 20. Existing links migrated from the older unversioned schema remain unverified until they are verified again; old snapshots are retained but are not silently promoted into mature evidence.

## Architecture

```text
Browser dashboard
      |
      v
FastAPI application (local static shell + API)
      |
      +-- Creator brief, research, scoring, and package generation
      |       |
      |       +-- YouTube Data API v3
      |       +-- Google Gemini API
      |
      +-- Read-only connected-channel analytics
      |       |
      |       +-- YouTube Data API v3
      |       +-- YouTube Analytics API
      |
      +-- SQLite WAL database
      |       +-- Packages and creator briefs
      |       +-- YouTube links and actual metadata
      |       +-- Performance snapshots and experiments
      |
      +-- Redis research cache
```

The default `/`, `/app`, and `/dashboard_view` routes serve the extracted local shell from `win_engine/api/static/index.html`. CSS and native ES modules are served from the same FastAPI process at `/static/*`; no CDN, Node toolchain, or second frontend server is required. `pages/creator.js` owns Creator state, requests, rendering, comparison, selection, checklist, copy, and export. The original embedded dashboard remains available at `/dashboard_legacy` for rollback.

## Requirements

- Docker Desktop with Docker Compose, recommended.
- A Google Gemini API key for AI-generated packages.
- A YouTube Data API v3 key for live public research.
- Google OAuth web-client credentials to connect the creator's channel and read private Analytics data.
- The connected Google account must own or manage the YouTube channel being analyzed.

The Google Cloud project that created the API key/OAuth client does not have to use the same Google account as the YouTube channel. During OAuth testing, the channel account must be added as an approved test user when the consent screen is in Testing mode.

## Configuration

Copy `.env.example` to `.env` and fill in the private values. Never commit `.env`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash:

```bash
cp .env.example .env
```

Important variables:

| Variable | Purpose | Required |
|---|---|---|
| `WIN_ENGINE_APP_ENVIRONMENT` | `production` enables admin-token protection for sensitive operational endpoints. | Recommended |
| `WIN_ENGINE_GEMINI_API_KEY` | Gemini package generation. | For Gemini output |
| `WIN_ENGINE_BIND_HOST` | Direct-Python bind address. Keep `127.0.0.1` for private laptop use; Compose overrides this only inside its container. | Default `127.0.0.1` |
| `WIN_ENGINE_GEMINI_MODEL` | Gemini model name. | Defaults from `.env.example` |
| `WIN_ENGINE_YOUTUBE_API_KEY` | Primary YouTube Data API research key. | For live research |
| `WIN_ENGINE_YOUTUBE_API_KEYS` | Optional comma-separated key pool; duplicates are removed. | Optional |
| `WIN_ENGINE_YOUTUBE_MAX_RESULTS` | Public research results used per query. | Optional; default `5` |
| `WIN_ENGINE_YOUTUBE_OAUTH_CLIENT_ID` | Google OAuth web-client ID. | For channel connection |
| `WIN_ENGINE_YOUTUBE_OAUTH_CLIENT_SECRET` | Google OAuth web-client secret. | For channel connection |
| `WIN_ENGINE_YOUTUBE_OAUTH_REDIRECT_URI` | Exact OAuth callback registered in Google Cloud. | Default `http://127.0.0.1:8000/oauth/youtube/callback` |
| `WIN_ENGINE_OAUTH_TOKEN_ENCRYPTION_KEY` | Fernet key used to encrypt the stored OAuth refresh token. | For channel connection |
| `WIN_ENGINE_DATABASE_PATH` | SQLite database path. | Default `win_engine.db` |
| `WIN_ENGINE_REDIS_URL` | Redis cache URL. Docker Compose sets this internally. | Optional outside Docker |
| `WIN_ENGINE_CACHE_TTL_TRENDING_SECONDS` | Trending research cache lifetime. | Default `21600` |
| `WIN_ENGINE_CACHE_TTL_EVERGREEN_SECONDS` | Evergreen research cache lifetime. | Default `604800` |
| `WIN_ENGINE_ADMIN_API_TOKEN` | Required header value for protected operational endpoints in production. | Recommended |
| `WIN_ENGINE_RATE_LIMIT_WINDOW_SECONDS` | In-memory request-rate window. | Default `60` |
| `WIN_ENGINE_RATE_LIMIT_MAX_REQUESTS` | General requests allowed per client/path/window. | Default `60` |

Generate the OAuth encryption key once:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the printed value as `WIN_ENGINE_OAUTH_TOKEN_ENCRYPTION_KEY`. Keep the same key while using the stored connection. Changing or losing it makes the existing encrypted refresh token unreadable, requiring the channel to be reconnected.

## Google API setup

In a Google Cloud project:

1. Enable YouTube Data API v3.
2. Enable YouTube Analytics API.
3. Configure the OAuth consent screen.
4. Create an OAuth client of type `Web application`.
5. Add this exact authorized redirect URI:

```text
http://127.0.0.1:8000/oauth/youtube/callback
```

6. If the consent screen remains in Testing mode, add the YouTube channel's Google account under test users.
7. Put the API key, client ID, client secret, redirect URI, and generated encryption key in `.env`.

The application requests read-only YouTube and YouTube Analytics scopes. It cannot upload videos or change live metadata through these scopes.

## Run with Docker

Create the SQLite file once if it does not already exist. This ensures Docker bind-mounts a file rather than creating a directory.

PowerShell:

```powershell
if (-not (Test-Path win_engine.db)) { New-Item -ItemType File win_engine.db }
docker compose up -d --build
docker compose ps
```

Bash:

```bash
touch win_engine.db
docker compose up -d --build
docker compose ps
```

Open:

- Dashboard: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Docker publishes the application only on `127.0.0.1:8000`. Redis is available only to the Compose network and has no host port.

Before a versioned schema migration, the application creates and independently verifies a SQLite online backup. Docker stores migration backups in the host `backups/` directory; database and backup files are ignored by Git.

Stop the application while preserving the database:

```bash
docker compose down
```

Rebuild after source changes:

```bash
docker compose up -d --build
```

Do not use `docker compose down -v` unless you intentionally want to remove named volumes used by the Compose project.

## Run directly with Python

Docker is the supported normal workflow. For local development without Docker:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

When Redis is unavailable, the research cache falls back to its supported local behavior. SQLite remains the permanent record.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Dashboard application. |
| `GET` | `/health` | Process and database health. |
| `GET` | `/ready` | Protected readiness details in production. |
| `GET` | `/meta` | Application metadata and capability summary. |
| `GET` | `/diagnostics` | Sanitized YouTube research and Gemini configuration diagnostics. |
| `POST` | `/analyze` | Research content and generate/save an SEO package. |
| `GET` | `/youtube/channel/status` | Connected-channel and latest-sync status. |
| `GET` | `/youtube/channel/connect` | Start Google OAuth connection. |
| `POST` | `/youtube/channel/refresh` | Refresh connected-channel data. |
| `POST` | `/youtube/channel/disconnect` | Remove the locally stored OAuth connection. |
| `GET` | `/api/history` | Learning, scorecard, owned-performance, and database summary. |
| `GET` | `/api/history/runs` | Paginated saved-package list. |
| `GET` | `/api/history/runs/{run_id}` | Complete package and linked-video report. |
| `DELETE` | `/api/history/runs/{run_id}` | Delete one saved package. |
| `POST` | `/api/history/runs/{run_id}/link-video` | Verify and link an owned YouTube video. |
| `GET` | `/api/published-videos` | Linked published videos and latest performance. |
| `GET` | `/api/published-videos/{link_id}/snapshots` | Stored performance timeline. |
| `POST` | `/api/published-videos/{link_id}/refresh` | Refresh actual metadata and available performance. |
| `PATCH` | `/api/published-videos/{link_id}` | Update creator-recorded package choices/notes. |
| `GET` | `/api/learning/cohorts` | Cohort analytics with optional format/language filters. |
| `POST` | `/api/experiments` | Record a creator-approved package experiment baseline. |
| `GET` | `/api/experiments/{youtube_video_id}` | Retrieve experiments for one video. |
| `POST` | `/api/reset-database` | Protected destructive history reset. |

In `production`, protected endpoints require the configured value in the `X-Admin-Token` request header. The dashboard handles its supported local workflows; use the interactive API documentation carefully for destructive operations.

Example analysis request:

```json
{
  "script": "This is a 15-second Short with a sunset background and an exact on-screen quote.",
  "video_language": "english",
  "language": "english",
  "region": "global",
  "audience_type": "general",
  "target_audience": "People who relate to unspoken love",
  "viewer_promise": "A concise emotionally faithful quote package",
  "unique_angle": "A future imagined silently while sitting together",
  "proof": "The exact quote and sunset footage are visible in the finished video",
  "video_format": "Short",
  "title_style": "balanced",
  "thumbnail_idea": "Two silhouettes beneath a sunset"
}
```

## Data and security boundaries

- `.env`, SQLite databases, WAL files, and local virtual environments are ignored by Git.
- OAuth refresh tokens are encrypted before local storage when a valid encryption key is configured.
- API responses use request IDs and sanitized error messages.
- Security headers disable framing and browser camera, microphone, and geolocation access.
- The current product is designed for one trusted user on one laptop.
- Do not expose the Docker port to the LAN or internet without authentication, TLS, and a separately approved Android/security architecture.
- Do not place secret values in screenshots, issues, commits, exported package data, or logs.

## Current limitations

- Gemini free-tier/model quotas can change and may temporarily force the labeled local fallback.
- YouTube Analytics may lag behind public view/like counts.
- Automatic snapshot collection is opt-in and disabled by default. When enabled it is quota-capped, due-window-only, and runs only while Docker is running. Dry-run mode performs no API calls or database writes.
- Comparable learning metadata is local and source-labelled (From package, Creator confirmed, YouTube verified, or Unknown); unknown/topic values are never guessed.
- Migrated pre-Phase-1 links must be ownership-verified again before they can affect learning, and their legacy snapshots remain display/history data only.
- The official APIs do not provide vidIQ's proprietary monthly keyword-search estimates.
- Public competitor metadata can show correlations and possible outliers but cannot reveal private competitor retention or prove causation.
- The experiment persistence API exists, but the complete Experiment Center UI is not finished.
- Creator package selection and checklist acknowledgments are intentionally browser-session state. The generated analysis is saved to History, but the local choice is not claimed as a persisted publishing decision.
- The application is not yet an Android app and remains bound to the local laptop.

## Testing

Run the backend suite locally:

```powershell
python -m unittest discover -s tests
```

Or inside the running Docker service:

```bash
docker compose exec -T win-engine python -m unittest discover -s tests
```

The backend suite contains 65 tests covering versioned migrations, backup verification, foreign keys, ownership, retryable snapshots, transactional deletion, history persistence, comparable metadata, collector dry-run/disablement, linked-video reports, cohort thresholds, learning behavior, scoring, Gemini failure handling, and related engine behavior. The optional browser suite contains 27 deterministic Playwright/Chromium tests covering navigation, loading/errors, advanced-brief retention, Research/provenance, stale responses, package comparison/selection, decision/checklist behavior, safe copy/export, encoding integrity, OAuth/collector states, History detail, linked refresh, request counts, console/page errors, and external-request isolation. The full local discovery run passes 92 tests. Browser tooling is installed only through `requirements-browser.txt` and is excluded from production Docker.

## Repository structure

```text
Seo-YT/
├── app.py                       # Application entry point
├── compose.yaml                 # Localhost-only FastAPI and internal Redis services
├── Dockerfile                   # Python 3.11 application image and health check
├── requirements.txt             # Pinned Python dependencies
├── README.md                    # Current product and operating documentation
├── ROADMAP.md                   # Remaining implementation program and rules
├── tests/
│   ├── browser/                 # Deterministic Chromium fixtures and workflow tests
│   └── test_engine.py           # Core engine regression tests
└── win_engine/
    ├── analysis/                # Brief, quality, research-insight, score, and pacing logic
    ├── api/                     # FastAPI routes and same-origin static dashboard application
    ├── core/                    # Configuration, schemas, middleware, logging, and rate limits
    ├── feedback/                # SQLite History, links, snapshots, cohorts, and learning
    ├── generation/              # SEO package assembly and strategy layers
    ├── ingestion/               # YouTube public research and caching
    ├── integrations/            # Read-only YouTube OAuth and Analytics integration
    └── llm/                     # Gemini client, prompts, validation, and fallback handling
```

## Product direction

SEO YT is intended to become a private personal alternative to the most useful vidIQ and TubeBuddy workflows—not a public clone. Its advantage is the traceable loop from the creator's exact content to the generated package, actual uploaded metadata, comparable performance, and future channel-specific recommendations.

The product remains successful only when it reports insufficient evidence honestly and helps the creator make better decisions without promising an outcome YouTube itself does not guarantee.
