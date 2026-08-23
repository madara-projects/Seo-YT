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
from win_engine.analysis.idea_workspace import build_idea_evidence, evidence_to_research, idea_script
from win_engine.analysis.demand_explorer import analyze_demand, idea_fingerprint
from win_engine.core.config import get_settings
from win_engine.core.schemas import AnalyzeRequest, AnalyzeResponse, LinkVideoRequest, UpdatePublishedVideoRequest, ComparableMetadataRequest, RecordExperimentRequest, SelectPackageRequest, CreateIdeaRequest, UpdateIdeaRequest, GenerateIdeaRequest, CreateWatchChannelRequest, CreateWatchVideoRequest, UpdateWatchRequest, DemandResearchRequest, CreateStructuredExperimentRequest, UpdateStructuredExperimentRequest, AssignExperimentVideoRequest
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.intelligence_store import IntelligenceStore
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService
from win_engine.ingestion.youtube_client import YouTubeClient
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
        language=payload.language,
        region=payload.region,
        duration_seconds=payload.duration_seconds,
        exact_quote=payload.exact_quote,
        on_screen_text=payload.on_screen_text,
        voice_over=payload.voice_over,
        visual_requirements=payload.visual_requirements,
        factual_claims=payload.factual_claims,
        claim_restrictions=payload.claim_restrictions,
        creator_intent=payload.creator_intent,
        content_constraints=payload.content_constraints,
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


@router.put("/api/history/runs/{run_id}/selection")
def select_history_package(run_id: int, payload: SelectPackageRequest):
    """Persist only a package that exists in the saved generated response."""

    store = HistoryStore(get_settings().database_path)
    try:
        selection = store.select_generated_package(run_id, payload.package_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if selection is None:
        raise HTTPException(status_code=404, detail="Saved package not found.")
    return {"status": "selected", "selection": selection}


# --- Stage G1: Idea backlog and topic opportunity workspace ---

@router.post("/api/ideas", status_code=201)
def create_idea(payload: CreateIdeaRequest):
    store = HistoryStore(get_settings().database_path)
    try:
        idea = store.create_content_idea(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "created", "idea": idea}


@router.get("/api/ideas")
def list_ideas(status: str | None = None, limit: int = 50, offset: int = 0):
    store = HistoryStore(get_settings().database_path)
    try:
        return store.content_ideas(status=status, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/ideas/{idea_id}")
def get_idea(idea_id: int):
    idea = HistoryStore(get_settings().database_path).content_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return {"idea": idea}


@router.patch("/api/ideas/{idea_id}")
def update_idea(idea_id: int, payload: UpdateIdeaRequest):
    store = HistoryStore(get_settings().database_path)
    try:
        idea = store.update_content_idea(idea_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return {"status": "updated", "idea": idea}


@router.post("/api/ideas/{idea_id}/research")
def research_idea(idea_id: int):
    settings = get_settings()
    store = HistoryStore(settings.database_path)
    idea = store.content_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")
    if idea.get("status") == "archived":
        raise HTTPException(status_code=409, detail="Restore this archived idea before researching it.")
    snapshot = _collect_idea_research(idea, store, settings)
    return {"status": "researched", "snapshot": snapshot, "idea": store.content_idea(idea_id)}


@router.post("/api/ideas/{idea_id}/generate")
def generate_idea_package(idea_id: int, payload: GenerateIdeaRequest):
    settings = get_settings()
    store = HistoryStore(settings.database_path)
    idea = store.content_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")
    if idea.get("status") in {"archived", "published"}:
        raise HTTPException(status_code=409, detail="Restore or duplicate this completed idea before generating another package.")
    script = idea_script(idea, payload.script)
    creator_brief = _idea_creator_brief(idea, script)
    latest = idea.get("latest_research") if isinstance(idea.get("latest_research"), dict) else None
    if latest and isinstance(latest.get("evidence"), dict):
        research_data = evidence_to_research(latest["evidence"])
    else:
        _collect_idea_research(idea, store, settings)
        refreshed = store.content_idea(idea_id) or {}
        latest = refreshed.get("latest_research") if isinstance(refreshed.get("latest_research"), dict) else None
        research_data = evidence_to_research((latest or {}).get("evidence") or {})
    research_data["history_store"] = store
    context = {
        "language": idea.get("language") or "english",
        "video_language": idea.get("language") or "english",
        "region": idea.get("region") or "global",
        "audience_type": "general",
        "creator_brief": creator_brief,
    }
    analysis = generate_seo_suggestions(script, research_data, context=context)
    run_id = analysis.get("history_run_id")
    if not isinstance(run_id, int):
        raise HTTPException(status_code=500, detail="The generated package was not saved to History.")
    linked = store.attach_content_idea_analysis(idea_id, run_id)
    return {"status": "package_generated", "idea": linked, "analysis": analysis}


def _idea_creator_brief(idea: dict[str, object], script: str) -> dict[str, object]:
    return build_creator_brief(
        script=script,
        target_audience=str(idea.get("audience_angle") or ""),
        viewer_promise="",
        unique_angle=str(idea.get("browse_angle") or idea.get("search_angle") or ""),
        proof="",
        video_format=str(idea.get("format") or ""),
        title_style="balanced",
        thumbnail_idea=str(idea.get("visual_or_background") or ""),
        language=str(idea.get("language") or "english"),
        region=str(idea.get("region") or "global"),
        duration_seconds=idea.get("target_duration_seconds"),
        exact_quote="",
        on_screen_text=str(idea.get("on_screen_text") or ""),
        voice_over="",
        visual_requirements=str(idea.get("visual_or_background") or ""),
        factual_claims="",
        claim_restrictions="",
        creator_intent=str(idea.get("emotion_or_intent") or ""),
        content_constraints="",
    )


def _collect_idea_research(idea: dict[str, object], store: HistoryStore, settings) -> dict[str, object]:
    script = idea_script(idea)
    creator_brief = _idea_creator_brief(idea, script)
    research = ResearchService(settings).gather(
        script,
        region=str(idea.get("region") or "global"),
        primary_language=str(idea.get("language") or "english"),
        creator_brief=creator_brief,
    )
    try:
        personal = store.cohort_analytics(
            format_filter=str(idea.get("format") or "unknown"),
            language_filter=str(idea.get("language") or "unknown"),
            snapshot_window="24h",
        )
    except ValueError:
        personal = {"learning_allowed": False, "sample_size": 0, "confidence_label": "Collecting evidence", "snapshot_window": "24h", "recommendation": "Not enough personal evidence."}
    evidence = build_idea_evidence(research, personal)
    snapshot = store.save_content_idea_research(int(idea["id"]), evidence)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return snapshot


# --- Phase 7 G2: public competitor/outlier watchlist ---

def _public_client(settings):
    return YouTubeClient(settings.youtube_api_key_pool, settings.request_timeout_seconds)

@router.post("/api/watchlist/channels", status_code=201)
def create_watch_channel(payload: CreateWatchChannelRequest):
    settings=get_settings(); metadata=_public_client(settings).get_channel(payload.channel_id, raise_on_error=False)
    if not metadata: raise HTTPException(status_code=400, detail="The public channel could not be resolved with the configured YouTube Data API.")
    try: item=IntelligenceStore(HistoryStore(settings.database_path)).create_channel(metadata,payload.notes)
    except ValueError as exc: raise HTTPException(status_code=409 if "already" in str(exc) else 422,detail=str(exc)) from exc
    return {"status":"created","channel":item}

@router.get("/api/watchlist/channels")
def list_watch_channels(state:str|None=None):
    try: items=IntelligenceStore(HistoryStore(get_settings().database_path)).channels(state)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"channels":items,"total":len(items)}

@router.get("/api/watchlist/channels/{item_id}")
def get_watch_channel(item_id:int):
    item=IntelligenceStore(HistoryStore(get_settings().database_path)).channel(item_id)
    if not item: raise HTTPException(status_code=404,detail="Watched channel not found.")
    return {"channel":item}

@router.patch("/api/watchlist/channels/{item_id}")
def update_watch_channel(item_id:int,payload:UpdateWatchRequest):
    try:item=IntelligenceStore(HistoryStore(get_settings().database_path)).update_channel(item_id,payload.model_dump(exclude_unset=True))
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
    if not item:raise HTTPException(status_code=404,detail="Watched channel not found.")
    return {"status":"updated","channel":item}

@router.post("/api/watchlist/channels/{item_id}/research")
def research_watch_channel(item_id:int):
    settings=get_settings(); store=IntelligenceStore(HistoryStore(settings.database_path)); item=store.channel(item_id)
    if not item:raise HTTPException(status_code=404,detail="Watched channel not found.")
    client=_public_client(settings); metadata=client.get_channel(item['channel_id']); videos=client.list_channel_videos(item['channel_id'],20)
    if not metadata:raise HTTPException(status_code=400,detail="Public channel research is unavailable; no snapshot was created.")
    return {"status":"researched","channel":store.snapshot_channel(item_id,metadata,videos),"observed_videos":len(videos)}

@router.post("/api/watchlist/videos", status_code=201)
def create_watch_video(payload:CreateWatchVideoRequest):
    video_id=_extract_youtube_video_id(payload.video_id)
    if not video_id:raise HTTPException(status_code=422,detail="Enter a valid public YouTube video ID or URL.")
    settings=get_settings(); metadata=_public_client(settings).get_video(video_id)
    if not metadata:raise HTTPException(status_code=400,detail="The public video could not be resolved with the configured YouTube Data API.")
    try:item=IntelligenceStore(HistoryStore(settings.database_path)).create_video(metadata,payload.notes)
    except ValueError as exc:raise HTTPException(status_code=409 if "already" in str(exc) else 422,detail=str(exc)) from exc
    return {"status":"created","video":item}

@router.get("/api/watchlist/videos")
def list_watch_videos(state:str|None=None,q:str=""):
    try:items=IntelligenceStore(HistoryStore(get_settings().database_path)).videos(state,q[:200])
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"videos":items,"total":len(items)}

@router.get("/api/watchlist/videos/{item_id}")
def get_watch_video(item_id:int):
    item=IntelligenceStore(HistoryStore(get_settings().database_path)).video(item_id)
    if not item:raise HTTPException(status_code=404,detail="Watched video not found.")
    return {"video":item}

@router.patch("/api/watchlist/videos/{item_id}")
def update_watch_video(item_id:int,payload:UpdateWatchRequest):
    try:item=IntelligenceStore(HistoryStore(get_settings().database_path)).update_video(item_id,payload.model_dump(exclude_unset=True))
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
    if not item:raise HTTPException(status_code=404,detail="Watched video not found.")
    return {"status":"updated","video":item}

@router.post("/api/watchlist/videos/{item_id}/research")
def research_watch_video(item_id:int):
    settings=get_settings(); store=IntelligenceStore(HistoryStore(settings.database_path)); item=store.video(item_id)
    if not item:raise HTTPException(status_code=404,detail="Watched video not found.")
    metadata=_public_client(settings).get_video(item['video_id'])
    if not metadata:raise HTTPException(status_code=400,detail="Public video research is unavailable; no snapshot was created.")
    return {"status":"researched","video":store.upsert_video(metadata,watchlist_channel_id=item.get('watchlist_channel_id'),snapshot=True)}

@router.post("/api/watchlist/videos/{item_id}/analyze-outlier")
def analyze_watch_video_outlier(item_id:int):
    store=IntelligenceStore(HistoryStore(get_settings().database_path))
    try:analysis=store.analyze_outlier(item_id)
    except KeyError as exc:raise HTTPException(status_code=404,detail="Watched video not found.") from exc
    return {"status":"analyzed","analysis":analysis,"video":store.video(item_id)}


# --- Phase 7 G5: honest topic-demand explorer ---

def _run_demand(values:dict[str,object],idea:dict[str,object]|None=None):
    settings=get_settings(); history=HistoryStore(settings.database_path); intelligence=IntelligenceStore(history)
    topic=str(values.get('topic') or '').strip(); brief=build_creator_brief(script=topic,video_format=str(values.get('format') or ''),language=str(values.get('language') or 'english'),region=str(values.get('region') or 'global'),target_audience=str(values.get('audience_context') or ''),creator_intent='',viewer_promise='',unique_angle='',proof='',title_style='balanced',thumbnail_idea='',duration_seconds=None,exact_quote='',on_screen_text='',voice_over='',visual_requirements='',factual_claims='',claim_restrictions='',content_constraints='')
    research=ResearchService(settings).gather(topic,region=str(values.get('region') or 'global'),primary_language=str(values.get('language') or 'english'),creator_brief=brief)
    try:personal=history.cohort_analytics(format_filter=str(values.get('format') or 'unknown'),language_filter=str(values.get('language') or 'unknown'),snapshot_window='24h')
    except ValueError:personal={"learning_allowed":False,"sample_size":0,"confidence_label":"Collecting evidence"}
    classification,evidence=analyze_demand(topic,research,intelligence.videos(state='active'),personal)
    fingerprint=idea_fingerprint(idea) if idea else None
    return intelligence.save_demand(values,classification,evidence,fingerprint)

@router.post("/api/demand/research",status_code=201)
def create_demand_research(payload:DemandResearchRequest):
    return {"status":"researched","research":_run_demand(payload.model_dump())}

@router.get("/api/demand/research")
def list_demand_research(limit:int=50,offset:int=0,idea_id:int|None=None):
    return IntelligenceStore(HistoryStore(get_settings().database_path)).demands(limit,offset,idea_id)

@router.get("/api/demand/research/{research_id}")
def get_demand_research(research_id:int):
    item=IntelligenceStore(HistoryStore(get_settings().database_path)).demand(research_id)
    if not item:raise HTTPException(status_code=404,detail="Demand research snapshot not found.")
    return {"research":item}

@router.post("/api/ideas/{idea_id}/demand-research",status_code=201)
def create_idea_demand_research(idea_id:int):
    idea=HistoryStore(get_settings().database_path).content_idea(idea_id)
    if not idea:raise HTTPException(status_code=404,detail="Idea not found.")
    values={"idea_id":idea_id,"topic":idea['topic'],"language":idea.get('language'),"format":idea.get('format'),"region":idea.get('region'),"audience_context":idea.get('audience_angle')}
    return {"status":"researched","research":_run_demand(values,idea)}

@router.post("/api/demand/research/{research_id}/generate")
def generate_from_demand(research_id:int):
    settings=get_settings(); history=HistoryStore(settings.database_path); intelligence=IntelligenceStore(history); item=intelligence.demand(research_id)
    if not item:raise HTTPException(status_code=404,detail="Demand research snapshot not found.")
    if item.get('idea_id'):
        idea=history.content_idea(int(item['idea_id']))
        if not idea:raise HTTPException(status_code=409,detail="The related idea is unavailable.")
        return generate_idea_package(int(item['idea_id']),GenerateIdeaRequest())
    evidence=item.get('evidence') or {}; research={"youtube_results":evidence.get('public_results') or [],"top_opportunities":[],"keyword_signals":[],"entity_signals":[],"upload_timing":{},"thumbnail_intelligence":{},"research_queries":[],"research_decision":{},"research_warnings":[],"cache_policy":"demand-research-snapshot","history_store":history}
    brief=build_creator_brief(script=item['topic'],video_format=item.get('format') or '',language=item.get('language') or 'english',region=item.get('region') or 'global',target_audience=item.get('audience_context') or '',viewer_promise='',unique_angle='',proof='',title_style='balanced',thumbnail_idea='',duration_seconds=None,exact_quote='',on_screen_text='',voice_over='',visual_requirements='',factual_claims='',claim_restrictions='',creator_intent='',content_constraints='')
    analysis=generate_seo_suggestions(item['topic'],research,context={"language":item.get('language') or 'english',"video_language":item.get('language') or 'english',"region":item.get('region') or 'global',"audience_type":'general',"creator_brief":brief})
    return {"status":"package_generated","analysis":analysis,"demand_research_id":research_id}


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
    saved_selection = run.get("selected_package") if isinstance(run.get("selected_package"), dict) else {}
    selected_package = saved_selection.get("package") if isinstance(saved_selection.get("package"), dict) else {}
    saved_brief = saved_package.get("creator_brief") if isinstance(saved_package.get("creator_brief"), dict) else {}
    selected_title = payload.selected_title or selected_package.get("title") or saved_package.get("title") or run.get("title")
    selected_description = payload.selected_description or selected_package.get("description") or saved_package.get("description")
    selected_tags = payload.selected_tags or selected_package.get("tags") or saved_package.get("tags") or []
    selected_hashtags = payload.selected_hashtags or selected_package.get("hashtags") or saved_package.get("hashtags") or []
    format_value = payload.format or saved_brief.get("video_format") or run.get("content_angle")
    language_value = payload.language or saved_brief.get("language")
    region_value = payload.region or saved_brief.get("region")
    link_id = store.link_published_video(
        analysis_run_id=run_id,
        youtube_video_id=clean_vid,
        published_at=pub_at,
        selected_title=str(selected_title) if selected_title else None,
        selected_thumbnail_package=payload.selected_thumbnail_package or selected_package.get("package_id"),
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


# --- Phase 8 / G3: Published Video Audit ---

@router.get("/api/audits")
def list_published_audits(evidence_state: str | None = None, audit_state: str | None = None):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    candidates = store.audit_candidates(evidence_state=evidence_state, audit_state=audit_state)
    return {"candidates": candidates, "total": len(candidates)}


@router.get("/api/audits/{link_id}")
def get_published_audit(link_id: int, audit_id: int | None = None):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    if not store.history.published_video_link(link_id):
        raise HTTPException(status_code=404, detail="Published video link not found.")
    audit = store.audit(link_id, audit_id)
    return {"audit": audit, "versions": store.audit_versions(link_id), "status": "available" if audit else "not_run"}


@router.post("/api/audits/{link_id}/refresh", status_code=201)
def refresh_published_audit(link_id: int):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    audit = store.refresh_audit(link_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Published video link or saved analysis was not found.")
    return {"status": "audited", "audit": audit, "versions": store.audit_versions(link_id)}


@router.get("/api/audits/{link_id}/findings")
def get_published_audit_findings(link_id: int):
    audit = AuditExperimentStore(HistoryStore(get_settings().database_path)).audit(link_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Run the published-video audit first.")
    return {"audit_id": audit["id"], "summary": audit["summary"], "findings": audit["findings"]}


@router.get("/api/audits/{link_id}/evidence")
def get_published_audit_evidence(link_id: int):
    audit = AuditExperimentStore(HistoryStore(get_settings().database_path)).audit(link_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Run the published-video audit first.")
    return {"audit_id": audit["id"], "evidence": audit["evidence"], "observed_performance": audit["observed_performance"], "limitations": audit["limitations"]}


# --- Phase 8 / G4: Structured Experiment Center ---

@router.post("/api/experiment-center/experiments", status_code=201)
def create_structured_experiment(payload: CreateStructuredExperimentRequest):
    item = AuditExperimentStore(HistoryStore(get_settings().database_path)).create_experiment(payload.model_dump())
    return {"status": "created", "experiment": item}


@router.get("/api/experiment-center/experiments")
def list_structured_experiments(status: str | None = None, mode: str | None = None):
    if status and status not in {"draft", "planned", "active", "paused", "completed", "cancelled", "inconclusive"}:
        raise HTTPException(status_code=422, detail="Invalid experiment status filter.")
    if mode and mode not in {"controlled", "observational"}:
        raise HTTPException(status_code=422, detail="Invalid experiment mode filter.")
    items = AuditExperimentStore(HistoryStore(get_settings().database_path)).experiments(status=status, mode=mode)
    return {"experiments": items, "total": len(items)}


@router.get("/api/experiment-center/experiments/{experiment_id}")
def get_structured_experiment(experiment_id: int):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    item = store.experiment(experiment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return {"experiment": item, "result_versions": store.result_versions(experiment_id)}


@router.patch("/api/experiment-center/experiments/{experiment_id}")
def update_structured_experiment(experiment_id: int, payload: UpdateStructuredExperimentRequest):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    try:
        item = store.update_experiment(experiment_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return {"status": "updated", "experiment": item}


@router.post("/api/experiment-center/experiments/{experiment_id}/assignments", status_code=201)
def assign_structured_experiment_video(experiment_id: int, payload: AssignExperimentVideoRequest):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    try:
        item = store.assign_video(experiment_id, payload.published_video_link_id, payload.role, payload.notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "assigned", "experiment": item}


@router.delete("/api/experiment-center/experiments/{experiment_id}/assignments/{assignment_id}")
def remove_structured_experiment_assignment(experiment_id: int, assignment_id: int):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    if not store.remove_assignment(experiment_id, assignment_id):
        raise HTTPException(status_code=404, detail="Experiment assignment not found.")
    return {"status": "removed", "assignment_id": assignment_id}


@router.post("/api/experiment-center/experiments/{experiment_id}/compare", status_code=201)
def compare_structured_experiment(experiment_id: int):
    store = AuditExperimentStore(HistoryStore(get_settings().database_path))
    result = store.refresh_experiment_result(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return {"status": "compared", "result": result, "experiment": store.experiment(experiment_id)}


def _extract_youtube_video_id(value: str) -> str | None:
    candidate = value.strip()
    match = re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/embed/)([A-Za-z0-9_-]{11})", candidate)
    if match:
        return match.group(1)
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
