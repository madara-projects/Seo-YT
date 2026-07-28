# 🚀 YouTube SEO Analyzer & Growth Engine

<p align="center">
  <b>A local-first, AI-powered YouTube SEO & Channel Strategy Engine built with FastAPI, Google Gemini 3.5 Flash, and SQLite.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/AI_Engine-Gemini_3.5_Flash-8E44AD?style=for-the-badge&logo=google" alt="Gemini AI" />
  <img src="https://img.shields.io/badge/Database-SQLite_WAL-003B57?style=for-the-badge&logo=sqlite" alt="SQLite" />
  <img src="https://img.shields.io/badge/Container-Docker-2496ED?style=for-the-badge&logo=docker" alt="Docker" />
</p>

---

## 🌟 Overview

**YouTube SEO Analyzer** turns raw video scripts or topic ideas into upload-ready, highly optimized YouTube SEO packages. Designed for solo creators and digital strategists, it combines **live YouTube Data API v3 market research**, **outlier competitor scoring**, and **Google Gemini AI** to produce maximum organic reach and high CTR titles.

---

## ✨ Key Features & Capabilities

- 🎯 **High-CTR Title Suite**: Generates a primary recommended title plus 5 distinct, scored title variants (How-to, Curiosity Gap, Result-Driven, Beginner, and Question styles).
- 📝 **Rich Description Engine**: Produces 150–300 word structured YouTube descriptions featuring opening hooks, bulleted key takeaways, chapter scaffolds, subscriber call-to-actions, and hashtags.
- 🌐 **Multi-Language & Regional Support**: Full generation support for **English**, **Tamil**, and **Tanglish** (Tamil-English blend), tailored for global or India-specific audiences.
- 📊 **Channel Self-Learning System**: Automatically records video performance snapshots (e.g. 1,000+ view milestones) in SQLite and injects top channel winners into AI prompts to continuously refine title recommendations.
- 🔍 **Live Competitor & Gap Analysis**: Analyzes competitor view counts, published dates, and keyword density to calculate topic **Opportunity Scores (0–100)** and **Content Retention Audit Signals**.
- 🎨 **Bento Grid Studio Dashboard**: Built-in zero-dependency SPA UI with tabbed views (**Dashboard**, **SEO Creator Studio**, **Channel Analytics**, **Settings & APIs**) and fail-proof 1-click copy buttons for titles, descriptions, and tags.
- 🐳 **Pure Docker Isolation**: 100% containerized deployment with Redis caching and persistent volume mapping.

---

## 📐 System Architecture

```text
                     ┌────────────────────────────────────────┐
                     │   Creator / Web Browser Dashboard      │
                     └───────────────────┬────────────────────┘
                                         │
                                         v
                     ┌────────────────────────────────────────┐
                     │    FastAPI Application Core Services   │
                     └───────┬────────────────────────┬───────┘
                             │                        │
                             v                        v
  ┌────────────────────────────────────┐    ┌───────────────────────────────────┐
  │   YouTube Data API v3 Research     │    │  Google Gemini 3.5 Flash Engine   │
  │ • Outlier Competitor Scoring       │    │ • Topic-Lock Title Suite          │
  │ • Opportunity Score (0-100)        │    │ • Structured 200w Descriptions    │
  │ • Keyword & Entity Extraction      │    │ • Multi-Lang (Eng/Tamil/Tanglish) │
  └──────────────────┬─────────────────┘    └─────────────────┬─────────────────┘
                     │                                        │
                     └───────────────────┬────────────────────┘
                                         │
                                         v
                     ┌────────────────────────────────────────┐
                     │    SQLite Local Database (WAL Mode)    │
                     │ • Permanent JSON Analysis History Log  │
                     │ • Channel Snapshot Self-Learning Store │
                     └────────────────────────────────────────┘
```

---

## 🛠️ Configuration & Environment Variables

Copy `.env.example` to create your local `.env` configuration:

```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `WIN_ENGINE_GEMINI_API_KEY` | **Google Gemini API Key** for AI copy generation | *Required for AI copy* |
| `WIN_ENGINE_YOUTUBE_API_KEY` | **YouTube Data API v3 Key** for live competitor research | *Required for research* |
| `WIN_ENGINE_DATABASE_PATH` | Path to local SQLite database | `win_engine.db` |
| `WIN_ENGINE_YOUTUBE_MAX_RESULTS` | Number of competitor videos analyzed per run | `5` |
| `WIN_ENGINE_REDIS_URL` | Optional Redis cache connection URL | `redis://localhost:6379/0` |
| `WIN_ENGINE_ADMIN_API_TOKEN` | Token for protected operational endpoints | *Optional* |

---

## 🐳 Quick Start with Docker (Recommended)

Run the full stack (FastAPI Backend + Redis Cache + SQLite Storage) inside isolated Docker containers:

```bash
# 1. Build and launch the container stack
docker compose up --build -d

# 2. Check container health status
docker compose ps
```

Open your browser and navigate to:
- **Studio Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

To stop the containers while preserving database history:
```bash
docker compose down
```

---

## 💻 Local Windows / Python Installation

If running directly without Docker:

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Launch the server
python app.py
```

---

## 🔌 API Endpoints Reference

### 1. Analyze Script / Idea (`POST /analyze`)
**Request Body:**
```json
{
  "script": "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
  "language": "english",
  "region": "in",
  "audience_type": "general"
}
```

### 2. Live Operational Endpoints
| HTTP Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard & SEO Studio UI |
| `GET` | `/api/history` | Retrieves stored analysis runs and channel self-learning stats |
| `GET` | `/diagnostics` | Diagnostic check for Gemini, YouTube API, and DB connection |
| `GET` | `/health` | System health and container status |

---

## 📁 Repository Structure

```text
Seo-YT/
├── app.py                      # FastAPI application entry point
├── compose.yaml                # Docker Compose orchestration
├── Dockerfile                  # Production container image manifest
├── requirements.txt            # Python dependencies
├── win_engine/
│   ├── api/                    # FastAPI routes, CORS, and Dashboard HTML UI
│   ├── analysis/               # Topic-lock, content audit, CTR, & gap engines
│   ├── core/                   # Config, schemas, middleware, & logging
│   ├── feedback/               # SQLite history store & channel self-learning
│   ├── generation/             # Strategy engine & SEO package builders
│   ├── ingestion/              # YouTube research client & caching
│   └── llm/                    # Gemini 3.5 Flash client & prompt strategies
```

---

<p align="center">
  Made for creators aiming for <b>higher CTR, deeper viewer retention, and maximum channel growth</b>. 🚀
</p>
