# YouTube SEO Analyzer

A local-first tool that turns a video script (or even a one-line idea) into a
ready-to-paste YouTube SEO package: title, 5 title variants, description,
tags, hashtags, and supporting strategy data.

Built for personal use — single user, a few videos per day.

## What it gives you

For any video idea you type in:

- **Title** (SEO + CTR optimized) + 4 alternates in different styles
- **Description** (120–180 words, keyword-front-loaded, with CTA)
- **Tags** (10, cleaned of junk filler)
- **Hashtags** (3, topic-derived)
- Supporting analysis: intent, content audit, competitor gap, pacing,
  thumbnail strategy, chapter outline, A/B test pack

## How it works

```
Your idea  ─►  YouTube research (competitor titles, keywords)
           ─►  Ollama generates SEO copy from your idea + competitor context
           ─►  Topic-lock layer (validates output, drops junk, enforces topic)
           ─►  Final package
```

Ollama is the brain. If Ollama is offline, the app falls back to template-only
output (still usable, but much less natural).

## Quick start

### 1. Install Ollama
Download from [ollama.ai](https://ollama.ai), then in a terminal:
```powershell
ollama pull mistral
```
The daemon auto-starts on `http://localhost:11434`.

### 2. Install Python deps
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure
```powershell
copy .env.example .env
```
Open `.env` and set `WIN_ENGINE_YOUTUBE_API_KEY` (free key from
[Google Cloud Console](https://console.cloud.google.com/) — enable
**YouTube Data API v3**).

### 4. Run
```powershell
python app.py
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) — built-in HTML form.
Or hit `POST /analyze` directly. Swagger docs at `/docs`.

## Stack

- **FastAPI** — API + built-in HTML form (no Streamlit, no second port)
- **spaCy** — keyword + entity extraction
- **Ollama (mistral)** — title/description generation
- **SQLite** — local history for learning + comparison
- **Redis** (optional) — caches YouTube research between requests
- **Docker** — optional, for a containerized run

## Run with Docker

The easiest way is Docker Compose (brings up the app + Redis, and points Ollama
at the host daemon automatically):

```powershell
docker compose up --build
```

Or build and run the single container by hand:

```powershell
docker build -t seo-app .
docker run -p 8000:8000 --env-file .env --add-host host.docker.internal:host-gateway -e OLLAMA_BASE_URL=http://host.docker.internal:11434 seo-app
```

Either way, open [http://127.0.0.1:8000](http://127.0.0.1:8000). Keep Ollama
running on the host (`ollama serve` / `ollama pull mistral`).

## Project shape

```
app.py                          FastAPI entry
win_engine/
  api/        routes (/, /analyze, /health, /ready, /meta, /diagnostics)
  ingestion/  YouTube client + research orchestration
  analysis/   topic-lock, NLP, intent, gap, pacing, thumbnail, content audit
  generation/ SEO package builder + automation/expansion/chapters
  feedback/   history store, learning engine, CTR prediction
  llm/        Ollama client + SEO writer
  scoring/    outlier engine for YouTube video scoring
  core/       config, schemas, logging, middleware, rate-limit
```

## Limits

- New / very niche trends → lower confidence from research signals
- Thumbnail output is concept guidance, not generated images
- Best results when Ollama is running locally
