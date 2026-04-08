# Deployment Guide

This project now includes a local Docker workflow and a deployment-ready app entrypoint.

## Local Docker Run

Build and start the app:

```powershell
docker compose up --build
```

Then open:

`http://127.0.0.1:8000`

## Stop the Container

```powershell
docker compose down
```

## Environment Variables

The app reads configuration from `.env` using the `WIN_ENGINE_` prefix.

Important values:

- `WIN_ENGINE_YOUTUBE_API_KEY`
- `WIN_ENGINE_YOUTUBE_API_KEYS`
- `WIN_ENGINE_YOUTUBE_MAX_RESULTS`
- `WIN_ENGINE_DATABASE_PATH`

## Hosted Deployment Notes

The app is deployment-friendly because:

- it binds to `0.0.0.0`
- it reads `PORT` from the environment
- it does not require a local-only reloader

For platforms like Render, Railway, or Fly.io:

1. Set the same `.env` values as platform environment variables.
2. Set the start command to:

```bash
python app.py
```

3. Expose port `8000` or let the platform inject `PORT`.

## Persistence Note

The current v1 setup uses SQLite for local history tracking. For simple single-instance deployment this is acceptable, but for more serious hosted usage Phase 7+ should move history storage to PostgreSQL.
