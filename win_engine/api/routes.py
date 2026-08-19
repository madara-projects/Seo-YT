from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from google.auth.exceptions import RefreshError

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.core.config import get_settings
from win_engine.core.schemas import AnalyzeRequest, AnalyzeResponse, LinkVideoRequest, UpdatePublishedVideoRequest, ComparableMetadataRequest, RecordExperimentRequest
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService
from win_engine.llm import gemini_client
from win_engine.api.dashboard_html import DASHBOARD_HTML
from win_engine.integrations.youtube_channel import YouTubeChannelService

router = APIRouter()

_APP_START = time.time()
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.get("/", response_class=HTMLResponse)
@router.get("/app", response_class=HTMLResponse)
@router.get("/dashboard_view", response_class=HTMLResponse)
def dashboard():
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html", headers=_NO_CACHE_HEADERS)


@router.get("/dashboard_legacy", response_class=HTMLResponse)
def legacy_dashboard():
    """Rollback route for the pre-Phase-3C embedded dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML, headers=_NO_CACHE_HEADERS)


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


@router.get("/api/snapshot-collector/status")
def snapshot_collector_status(request: Request):
    collector = getattr(request.app.state, "snapshot_collector", None)
    if collector is None:
        return {"state": "disabled", "enabled": False, "dry_run": False, "running": False}
    return collector.status()


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
        "video_language": payload.video_language,
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
    store = HistoryStore(get_settings().database_path)
    run = store.history_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Saved package not found.")
    run["linked_video_report"] = store.linked_package_report(run_id)
    return run


@router.post("/api/reset-database")
def reset_database(request: Request):
    settings = get_settings()
    _require_admin(request, settings)
    store = HistoryStore(settings.database_path)
    store.reset_database()
    return {"status": "cleared", "message": "All historical test records wiped cleanly."}


# --- Stage A: Published Video Linking Endpoints ---

@router.post("/api/history/runs/{run_id}/link-video")
def link_published_video(run_id: int, payload: LinkVideoRequest):
    settings = get_settings()
    store = HistoryStore(settings.database_path)
    run = store.history_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Saved SEO package not found.")

    clean_vid = _extract_youtube_video_id(payload.youtube_video_id)
    if not clean_vid:
        raise HTTPException(status_code=422, detail="Enter a valid 11-character YouTube video ID or video URL.")
    service = YouTubeChannelService(settings)
    try:
        owned_video = service.verify_owned_video(clean_vid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pub_at = payload.published_at or owned_video.get("published_at")
    if not owned_video.get("ownership_verified") or not owned_video.get("channel_id"):
        raise HTTPException(
            status_code=400,
            detail="YouTube ownership could not be verified, so the video was not linked.",
        )
    if not pub_at:
        raise HTTPException(status_code=400, detail="YouTube did not return a publication time for this video.")
    saved_package = run.get("package") if isinstance(run.get("package"), dict) else {}
    saved_brief = saved_package.get("creator_brief") if isinstance(saved_package.get("creator_brief"), dict) else {}
    selected_title = payload.selected_title or saved_package.get("title") or run.get("title")
    selected_description = payload.selected_description or saved_package.get("description")
    selected_tags = payload.selected_tags or saved_package.get("tags") or []
    selected_hashtags = payload.selected_hashtags or saved_package.get("hashtags") or []
    format_value = payload.format or saved_brief.get("video_format") or run.get("content_angle")
    language_value = payload.language or saved_brief.get("language")
    region_value = payload.region or saved_brief.get("region")
    link_id = store.link_published_video(
        analysis_run_id=run_id,
        youtube_video_id=clean_vid,
        published_at=pub_at,
        selected_title=str(selected_title) if selected_title else None,
        selected_thumbnail_package=payload.selected_thumbnail_package,
        selected_description=str(selected_description) if selected_description else None,
        selected_tags_json=json.dumps(selected_tags),
        selected_hashtags_json=json.dumps(selected_hashtags),
        format_val=str(format_value) if format_value else None,
        language=str(language_value) if language_value else None,
        region=str(region_value) if region_value else None,
        notes=payload.notes,
        ownership_state="verified",
        ownership_verified=True,
        verified_channel_id=str(owned_video.get("channel_id") or ""),
        ownership_verified_at=datetime.now(timezone.utc).isoformat(),
    )
    store.update_linked_video_metadata(link_id, owned_video)
    refresh_warning = None
    try:
        link = store.published_video_link(link_id)
        if link and owned_video.get("ownership_verified"):
            service.refresh_linked_video_performance(link)
    except Exception as exc:
        refresh_warning = (
            "The package was linked, but live analytics could not be refreshed yet: "
            + str(exc)
        )

    return {
        "status": "linked",
        "link_id": link_id,
        "analysis_run_id": run_id,
        "youtube_video_id": clean_vid,
        "published_at": pub_at,
        "refresh_warning": refresh_warning,
        "report": store.linked_package_report(run_id),
    }


@router.delete("/api/history/runs/{run_id}")
def delete_history_run(run_id: int):
    store = HistoryStore(get_settings().database_path)
    if not store.delete_analysis_run(run_id):
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return {"status": "deleted", "run_id": run_id}


@router.get("/api/published-videos")
def get_published_video_links():
    store = HistoryStore(get_settings().database_path)
    links = store.published_video_links_list()
    return {"links": links, "total": len(links)}


@router.get("/api/published-videos/{link_id}/snapshots")
def get_published_video_snapshots(link_id: int):
    store = HistoryStore(get_settings().database_path)
    link = store.published_video_link(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Published video link not found.")
    return {"link": link, "snapshots": store.performance_snapshots(link["youtube_video_id"])}


@router.post("/api/published-videos/{link_id}/refresh")
def refresh_published_video(link_id: int):
    settings = get_settings()
    store = HistoryStore(settings.database_path)
    link = store.published_video_link(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Published video link not found.")
    try:
        refreshed = YouTubeChannelService(settings).refresh_linked_video_performance(link)
        refreshed["report"] = store.linked_package_report(int(link["analysis_run_id"]))
        return refreshed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/api/published-videos/{link_id}")
def update_published_video_link(link_id: int, payload: UpdatePublishedVideoRequest):
    store = HistoryStore(get_settings().database_path)
    success = store.update_published_video_link(
        link_id=link_id,
        selected_title=payload.selected_title,
        selected_thumbnail_package=payload.selected_thumbnail_package,
        selected_description=payload.selected_description,
        notes=payload.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Published video link not found.")
    return {"status": "updated", "link_id": link_id}


@router.patch("/api/published-videos/{link_id}/comparable-metadata")
def update_comparable_metadata(link_id: int, payload: ComparableMetadataRequest):
    store = HistoryStore(get_settings().database_path)
    try:
        result = store.update_comparable_metadata(link_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Published video link not found.")
    return {"status": "updated", "link_id": link_id, "comparable_metadata": result}


# --- Stage C: Cohort Evidence Endpoints ---

@router.get("/api/learning/cohorts")
def get_cohort_analytics(
    format: str | None = None,
    language: str | None = None,
    duration_bucket: str | None = None,
    topic_category: str | None = None,
    window: str = "24h",
):
    store = HistoryStore(get_settings().database_path)
    try:
        return store.cohort_analytics(
            format_filter=format,
            language_filter=language,
            duration_bucket_filter=duration_bucket,
            topic_category_filter=topic_category,
            snapshot_window=window,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# --- Stage D: Package Experiments Endpoints ---

@router.post("/api/experiments")
def record_experiment(payload: RecordExperimentRequest):
    store = HistoryStore(get_settings().database_path)
    if not store.latest_performance_snapshot(payload.youtube_video_id):
        raise HTTPException(status_code=400, detail="Refresh this linked video before recording an experiment so its baseline is preserved.")
    exp_id = store.record_package_experiment(
        youtube_video_id=payload.youtube_video_id,
        old_title=payload.old_title,
        new_title=payload.new_title,
        old_thumbnail=payload.old_thumbnail,
        new_thumbnail=payload.new_thumbnail,
        reason=payload.reason,
        performance_before_json=json.dumps(payload.performance_before or store.latest_performance_snapshot(payload.youtube_video_id)),
    )
    return {"status": "recorded", "experiment_id": exp_id}


@router.get("/api/experiments/{youtube_video_id}")
def get_experiments(youtube_video_id: str):
    store = HistoryStore(get_settings().database_path)
    experiments = store.get_package_experiments(youtube_video_id)
    return {"experiments": experiments, "count": len(experiments)}


def _extract_youtube_video_id(value: str) -> str | None:
    candidate = value.strip()
    match = re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/embed/)([A-Za-z0-9_-]{11})", candidate)
    if match:
        return match.group(1)
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
