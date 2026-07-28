from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google.auth.exceptions import RefreshError

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.core.config import get_settings
from win_engine.core.schemas import AnalyzeRequest, AnalyzeResponse
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService
from win_engine.llm import gemini_client
from win_engine.api.dashboard_html import DASHBOARD_HTML
from win_engine.integrations.youtube_channel import YouTubeChannelService

router = APIRouter()

_APP_START = time.time()


@router.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@router.get("/health")
def health_check():
    settings = get_settings()
    history = HistoryStore(settings.database_path).system_status()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "uptime_seconds": int(time.time() - _APP_START),
        "database_ok": history["database_ok"],
    }


@router.get("/ready")
def readiness_check(request: Request):
    settings = get_settings()
    _require_admin(request, settings)
    history = HistoryStore(settings.database_path).system_status()
    youtube_keys_present = bool(settings.youtube_api_key_pool)
    ready = history["database_ok"] and youtube_keys_present

    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": history,
            "youtube_api_keys_present": youtube_keys_present,
        },
    }


@router.get("/meta")
def metadata():
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "docker_optional": True,
        "capabilities": [
            "youtube research",
            "seo generation",
            "outlier scoring",
            "feedback loop",
            "advanced strategy layer",
        ],
    }


@router.get("/diagnostics")
def diagnostics():
    settings = get_settings()
    research = ResearchService(settings)

    return {**research.diagnostics(), "gemini": gemini_client.diagnostics()}


@router.get("/youtube/channel/status")
def youtube_channel_status():
    return YouTubeChannelService(get_settings()).status()


@router.get("/youtube/channel/connect")
def connect_youtube_channel():
    service = YouTubeChannelService(get_settings())
    try:
        return RedirectResponse(service.authorization_url())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/oauth/youtube/callback")
def youtube_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(url=f"/?youtube=error&reason={error}")
    try:
        YouTubeChannelService(get_settings()).complete_authorization(code=code, state=state)
    except ValueError as exc:
        return RedirectResponse(url="/?youtube=error")
    except Exception:
        return RedirectResponse(url="/?youtube=error")
    return RedirectResponse(url="/?youtube=connected")


@router.post("/youtube/channel/refresh")
def refresh_youtube_channel():
    try:
        return YouTubeChannelService(get_settings()).refresh()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RefreshError as exc:
        raise HTTPException(
            status_code=401,
            detail="Your YouTube connection has expired or was revoked. Select Connect Channel to reconnect it.",
        ) from exc


@router.post("/youtube/channel/disconnect")
def disconnect_youtube_channel():
    YouTubeChannelService(get_settings()).disconnect()
    return {"disconnected": True}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_script(payload: AnalyzeRequest):
    settings = get_settings()
    creator_brief = build_creator_brief(
        script=payload.script,
        target_audience=payload.target_audience,
        viewer_promise=payload.viewer_promise,
        unique_angle=payload.unique_angle,
        proof=payload.proof,
        video_format=payload.video_format,
        title_style=payload.title_style,
        thumbnail_idea=payload.thumbnail_idea,
    )
    research = ResearchService(settings)
    research_data = research.gather(
        payload.script,
        region=payload.region,
        primary_language=payload.language,
        creator_brief=creator_brief,
    )

    context = {
        "language": payload.language,
        "region": payload.region,
        "audience_type": payload.audience_type,
        "creator_brief": creator_brief,
    }
    return generate_seo_suggestions(payload.script, research_data, context=context)


def _require_admin(request: Request, settings) -> None:
    if settings.app_environment == "development":
        return

    expected = settings.admin_api_token
    if not expected:
        raise HTTPException(status_code=403, detail="This endpoint is disabled until an admin token is configured.")

    provided = request.headers.get("X-Admin-Token", "").strip()
    if provided != expected:
        raise HTTPException(status_code=403, detail="Admin token required for this endpoint.")


@router.get("/api/history")
def get_history_summary():
    settings = get_settings()
    store = HistoryStore(settings.database_path)
    return {
        "learning": store.learning_summary(),
        "scorecard": store.internal_scorecard(),
        "owned_performance": store.owned_performance_summary(),
        "status": store.system_status(),
    }


@router.get("/api/history/runs")
def get_history_runs(limit: int = 50, offset: int = 0):
    store = HistoryStore(get_settings().database_path)
    return {"runs": store.history_runs(limit=limit, offset=offset), "limit": min(max(limit, 1), 100), "offset": max(offset, 0)}


@router.get("/api/history/runs/{run_id}")
def get_history_run(run_id: int):
    run = HistoryStore(get_settings().database_path).history_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Saved package not found.")
    return run


@router.post("/api/reset-database")
def reset_database(request: Request):
    settings = get_settings()
    _require_admin(request, settings)
    store = HistoryStore(settings.database_path)
    store.reset_database()
    return {"status": "cleared", "message": "All historical test records wiped cleanly."}
