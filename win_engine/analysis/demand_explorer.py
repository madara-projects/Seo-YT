"""Deterministic, provenance-rich topic-demand evidence classification."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone, timedelta
from statistics import median
from typing import Any


def idea_fingerprint(idea:dict[str,Any])->str:
    fields=("topic","notes","format","language","region","visual_or_background","on_screen_text","emotion_or_intent","search_angle","browse_angle","audience_angle")
    raw="\n".join(str(idea.get(k) or '').strip().casefold() for k in fields)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def analyze_demand(topic:str,research:dict[str,Any],watch_videos:list[dict[str,Any]],personal:dict[str,Any])->tuple[str,dict[str,Any]]:
    results=[r for r in research.get('youtube_results',[]) if isinstance(r,dict)]
    now=datetime.now(timezone.utc); recent=0; views=[]; engagements=[]; channels=set()
    for result in results:
        channels.add(str(result.get('channel_id') or result.get('channel_title') or 'unknown'))
        published=_date(result.get('published_at'))
        if published and now-published<=timedelta(days=90): recent+=1
        view=_number(result.get('view_count'))
        if view is not None: views.append(view)
        likes=_number(result.get('like_count')); comments=_number(result.get('comment_count'))
        if view and (likes is not None or comments is not None): engagements.append(((likes or 0)+(comments or 0))/view)
    topic_tokens={t for t in re.findall(r"[a-z0-9]+",topic.casefold()) if len(t)>2}
    matching=[]
    for video in watch_videos:
        title_tokens=set(re.findall(r"[a-z0-9]+",str(video.get('title') or '').casefold()))
        if topic_tokens and topic_tokens & title_tokens:
            outlier=video.get('outlier') or {}
            matching.append({"watchlist_video_id":video.get('id'),"video_id":video.get('video_id'),"title":video.get('title'),"outlier_status":outlier.get('status') or 'not_analyzed',"relative_multiplier":outlier.get('relative_multiplier'),"captured_at":(video.get('latest_snapshot') or {}).get('captured_at'),"provenance":"public_observation"})
    outliers=sum(1 for item in matching if item['outlier_status']=='possible_outlier')
    count=len(results); channel_count=len(channels-{"unknown"})
    reasons=[]
    if count>=3: reasons.append(f"{count} relevant public results were observed in the sampled API result set.")
    if recent: reasons.append(f"{recent} observed result(s) were published in the last 90 days.")
    if channel_count>=2: reasons.append(f"Coverage was observed across {channel_count} independent channels.")
    if views: reasons.append(f"Median captured public views across {len(views)} result(s): {median(views):.0f}.")
    if outliers: reasons.append(f"{outliers} matching saved watchlist video(s) have an observational possible-outlier result.")
    if count>=8 and channel_count>=4 and recent>=3 and (outliers>=1 or len(engagements)>=5): classification='strong_observed_interest'
    elif count>=5 and channel_count>=3 and recent>=2 and views: classification='active_topic'
    elif count>=3 and (recent>=1 or channel_count>=2): classification='emerging_signal'
    else: classification='insufficient_evidence'; reasons.append("The observed sample is too sparse for an interest classification.")
    personal_allowed=bool(personal.get('learning_allowed'))
    evidence={
        "classification":classification,"reasons":reasons,"captured_at":now.isoformat(),
        "signals":[
            {"name":"sampled_relevant_results","observed":count,"source":"public_observation","limitation":"Sampled API results, not monthly search volume."},
            {"name":"recent_publications_90d","observed":recent,"source":"public_observation","limitation":"Publication activity does not prove audience demand."},
            {"name":"independent_channels","observed":channel_count,"source":"public_observation","limitation":"Channel coverage is observational."},
            {"name":"median_captured_views","observed":round(float(median(views)),2) if views else None,"source":"public_observation" if views else "unavailable","limitation":"Views at capture time are not search volume or causal evidence."},
            {"name":"watchlist_possible_outliers","observed":outliers,"source":"heuristic","limitation":"Outlier association does not establish causation."},
        ],
        "public_results":results,"watchlist_evidence":matching,
        "personal_evidence":{"status":"post_publish_evidence" if personal_allowed else "insufficient_evidence","learning_allowed":personal_allowed,"sample_size":int(personal.get('sample_size') or 0),"confidence_label":personal.get('confidence_label') or 'Collecting evidence',"source":"post_publish_evidence" if personal_allowed else "unavailable"},
        "limitations":["No official monthly search-volume data is available.","No CPC, market size, guaranteed demand, CTR, views, or growth is inferred.","Public views, titles, formats, timing, and engagement are associations; causation cannot be established."],
        "provenance":{"research":"approved_youtube_data_api_research","watchlist":"public_observation_and_local_heuristic","personal":"shared_mature_evidence_policy"},
    }
    return classification,evidence

def _date(value:Any):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'));return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError,TypeError):return None
def _number(value:Any):
    try:return float(value) if value is not None else None
    except (ValueError,TypeError):return None
