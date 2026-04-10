# YouTube Win-Engine

YouTube Win-Engine is a creator-focused backend + UI that turns a raw video script into a usable YouTube upload package.

It is built to help with:

- title generation
- alternative title ideas
- description generation
- tags and hashtags
- YouTube competitor research
- opportunity and packaging analysis
- language, region, and audience-aware strategy

## What This Project Does

You paste a script into the Streamlit UI or send it to the backend API.

The system then:

1. researches related YouTube videos
2. extracts keyword and topic signals
3. scores opportunities and competition baselines
4. generates:
   - best title
   - alternative titles
   - description
   - tags
   - hashtags

## Current Status

- Phase 1: complete
- Phase 2: complete
- Current active milestone: Phase 3 audit
- API: working
- Streamlit UI: working
- Redis: optional
- Docker: optional

See [ROADMAP.md](ROADMAP.md) for the detailed phase tracker.

## Stack

- Backend: FastAPI
- UI: Streamlit
- Storage: SQLite
- Cache:
  - in-memory by default
  - Redis optionally supported
- Research source: YouTube Data API

## Project Structure

```text
win_engine/
  api/          FastAPI app and routes
  analysis/     keyword, language, title, pacing, and gap logic
  core/         config, schemas, logging, middleware, rate limiting
  feedback/     SQLite history and learning summaries
  generation/   title, description, hashtag, automation generation
  ingestion/    research service, YouTube client, cache
  scoring/      outlier scoring

app.py            FastAPI entrypoint
streamlit_app.py  Streamlit UI
compose.yaml      Optional Docker + Redis setup
ROADMAP.md        Project phase tracker
```

## Features Available Right Now

- script input flow
- YouTube result gathering
- title / description / hashtag generation
- alternative title generation
- language, region, and audience context
- outlier and opportunity baselines
- title optimization baseline
- local feedback history with SQLite
- optional Redis-backed caching

## What Is Still Improving

- title realism across more niches
- description quality for better click support
- region-aware keyword prioritization
- local-vs-global weighting quality
- Tamil / Tanglish phrasing quality

## Requirements

- Python 3.13 recommended on this machine
- YouTube Data API key

## Environment Setup

Copy `.env.example` to `.env` and set at least:

```env
WIN_ENGINE_YOUTUBE_API_KEY=your_youtube_api_key
```

Optional Redis:

```env
WIN_ENGINE_REDIS_URL=redis://localhost:6379/0
```

If `WIN_ENGINE_REDIS_URL` is empty, the app automatically falls back to in-memory cache.

## Install

If your local virtual environment is active:

```powershell
pip install -r requirements.txt
```

If you want to use the exact Python path directly:

```powershell
& 'C:\Users\Sameer\AppData\Local\Programs\Python\Python313\python.exe' -m pip install -r requirements.txt
```

## Run The FastAPI App

```powershell
cd C:\Users\Sameer\Downloads\Seo-YT
.\.venv\Scripts\Activate.ps1
python app.py
```

Open:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Run The Streamlit UI

```powershell
cd C:\Users\Sameer\Downloads\Seo-YT
.\.venv\Scripts\Activate.ps1
python -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Open:

- `http://localhost:8501`

Do not open `http://0.0.0.0:8501` in the browser. That is only the bind address.

## Docker

Docker is optional.

To run the API with Redis:

```powershell
docker compose up --build
```

If you want the API container to use Redis, set this in `.env`:

```env
WIN_ENGINE_REDIS_URL=redis://redis:6379/0
```

## Git Notes

These are intentionally ignored:

- `.env`
- `.venv`
- `.tmp`
- `win_engine.db`
- `__pycache__`

## Notes

- The old Flask-era `ytseo/` package has been removed locally and should be committed as cleanup.
- The old `test_phase3_audit.py` file has also been removed locally and should be committed.
