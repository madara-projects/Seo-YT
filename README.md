# YouTube SEO Analyzer

A local-first FastAPI application that turns a video idea or script into a researched, upload-ready YouTube SEO package. It is designed for one creator running a few analyses per day, either directly on Windows or with Docker Compose.

The staged plan for turning it into a private, channel-aware growth tool is in [ROADMAP.md](ROADMAP.md).

## What it produces

- English, Tamil, and Tanglish title packages
- A primary title plus five scored alternatives
- Description, tags, and hashtags
- YouTube competitor research and outlier scoring
- Keyword, entity, opportunity, pacing, and content-audit signals
- Thumbnail direction, chapters, content-graph ideas, and publishing workflow
- CTR guidance, A/B title suggestions, and comparison with local analysis history
- JSON export from the built-in dashboard

Ollama generates the natural-language SEO copy. If Ollama is unavailable, the application remains usable through a deterministic English fallback and reports when native Tamil or Tanglish output could not be generated.

## Architecture

```text
Browser or API client
        |
        v
FastAPI routes and validation
        |
        +--> YouTube Data API research --> outlier and opportunity scoring
        |
        +--> Ollama generation --> topic-lock validation
        |
        +--> analysis and strategy engines
        |
        +--> SQLite history and feedback
        |
        v
Structured analysis response
```

The service uses one FastAPI process and an inline HTML/JavaScript dashboard. There is no frontend build toolchain or separate UI server.

## Requirements

- Python 3.11+
- A YouTube Data API v3 key
- [Ollama](https://ollama.com/) with a local model for high-quality multilingual output
- Docker Desktop only if using the container workflow

Redis is optional for direct local runs and is included by Docker Compose.

## Configuration

Copy the example file and add your API key:

```powershell
Copy-Item .env.example .env
```

Important variables:

| Variable | Purpose | Default |
|---|---|---|
| `WIN_ENGINE_YOUTUBE_API_KEY` | YouTube Data API v3 key | empty |
| `WIN_ENGINE_YOUTUBE_API_KEYS` | Comma-separated key rotation pool | empty |
| `WIN_ENGINE_YOUTUBE_MAX_RESULTS` | Competitors fetched per analysis | `5` |
| `OLLAMA_BASE_URL` | Ollama HTTP endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Generation model | `mistral` |
| `OLLAMA_TIMEOUT_SECONDS` | Generation timeout | `30` in the example |
| `WIN_ENGINE_DATABASE_PATH` | SQLite history path | `win_engine.db` |
| `WIN_ENGINE_REDIS_URL` | Optional Redis cache URL | empty |
| `WIN_ENGINE_PUBLIC_DIAGNOSTICS_ENABLED` | Allow diagnostics without an admin token | `true` |
| `WIN_ENGINE_ADMIN_API_TOKEN` | Token for protected operational endpoints | empty |

Do not commit `.env`; it is excluded by `.gitignore`. In non-development environments, configure an admin token before exposing operational endpoints.

## Run locally

Install and start Ollama first:

```powershell
ollama pull mistral
```

Create a clean virtual environment and install the application:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Run with Docker

Keep Ollama running on the host, then build and start the application with Redis:

```powershell
docker compose up --build -d
docker compose ps
```

The Compose configuration maps the host Ollama daemon through `host.docker.internal` and persists SQLite data in `win_engine.db`.

Stop the stack without deleting its data:

```powershell
docker compose down
```

## API

### Analyze a script

`POST /analyze`

```json
{
  "script": "How I organize a productive workday from home",
  "language": "english",
  "region": "global",
  "audience_type": "general"
}
```

Only `script` is required. The response contains the upload-ready packages and the supporting research and strategy fields.

### Operational endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Dashboard |
| `GET /health` | Process and database health |
| `GET /ready` | Database and YouTube-key readiness |
| `GET /meta` | Version and capabilities |
| `GET /diagnostics` | Live YouTube integration probe |
| `GET /docs` | OpenAPI interface |

When an endpoint is protected, send the token in the `X-Admin-Token` header.

## Project layout

```text
app.py                  Application entry point
compose.yaml            App and Redis services
Dockerfile              Production-style container image
requirements.txt        Python runtime dependencies
win_engine/
  api/                   FastAPI factory, dashboard, and routes
  analysis/              Topic, content, CTR, pacing, and strategy analysis
  core/                  Configuration, schemas, middleware, logging, rate limiting
  feedback/              SQLite history and feedback summaries
  generation/            SEO package and workflow generation
  ingestion/             YouTube client, caching, and research orchestration
  llm/                   Ollama client and SEO prompts
  scoring/               Competitor outlier scoring
```

## Current scope and limitations

- This is a local, single-user tool; it has no user accounts or multi-tenant isolation.
- YouTube research quality depends on a valid API key and available quota.
- Native Tamil and Tanglish generation requires Ollama.
- CTR values are heuristic guidance, not measured predictions.
- Chapter timestamps are generic suggestions and should be reviewed before publishing.
- The repository currently has no automated test suite; validate changes with import, API, and container smoke checks.
