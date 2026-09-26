"""SQLite persistence for Phase 7 public watchlist and demand observations."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from statistics import median
from typing import Any

from win_engine.analysis.source_cues import is_short_duration
from win_engine.core.iso_duration import duration_seconds
from win_engine.feedback.history_store import HistoryStore


class AlreadyWatched(ValueError):
    """The channel or video is already in the watchlist."""

OUTLIER_MULTIPLIER = 2.5
OUTLIER_MIN_PEERS = 5
# Lifetime views of a years-old upload say nothing about a two-day-old one, so
# peers must be published within this many days of the video and observed at
# between half and twice its age.
PEER_PUBLISH_WINDOW_DAYS = 180
PEER_AGE_RATIO = 2.0
OUTLIER_OBSERVATION_WINDOW = "peer_snapshot_nearest_same_age"

_CHANNEL_COLUMNS = "ch.id,ch.channel_id,ch.title,ch.thumbnail_url,ch.subscriber_count,ch.video_count,ch.notes,ch.state,ch.source,ch.last_researched_at,ch.created_at,ch.updated_at"
_CHANNEL_KEYS = ("id","channel_id","title","thumbnail_url","subscriber_count","video_count","notes","state","source","last_researched_at","created_at","updated_at")
_CHANNEL_SNAPSHOT_COLUMNS = "id,captured_at,subscriber_count,video_count,view_count,metadata_json,source"
_VIDEO_COLUMNS = "v.id,v.video_id,v.watchlist_channel_id,v.channel_id,v.channel_title,v.title,v.published_at,v.duration_seconds,v.language,v.format,v.notes,v.state,v.source,v.last_researched_at,v.created_at,v.updated_at"
_VIDEO_KEYS = ("id","video_id","watchlist_channel_id","channel_id","channel_title","title","published_at","duration_seconds","language","format","notes","state","source","last_researched_at","created_at","updated_at")
_VIDEO_SNAPSHOT_COLUMNS = "id,captured_at,view_count,like_count,comment_count,duration_seconds,metadata_json,source"
_OUTLIER_COLUMNS = "id,analyzed_at,status,observed_views,baseline_median_views,relative_multiplier,sample_size,observation_window,explanation,signals_json,provenance"
_DEMAND_COLUMNS = "id,idea_id,topic,language,format,region,audience_context,idea_fingerprint,classification,evidence_json,captured_at"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def inferred_format(seconds: float | None) -> str:
    # A live or upcoming broadcast reports no duration, which says nothing about its format.
    is_short = is_short_duration(seconds)
    return "unknown" if is_short is None else "youtube_shorts" if is_short else "long_form"


class IntelligenceStore:
    def __init__(self, history: HistoryStore):
        self.history = history

    def create_channel(self, metadata: dict[str, Any], notes: str = "") -> dict[str, Any]:
        channel_id = str(metadata.get("channel_id") or "").strip()
        if not channel_id or not metadata.get("title"):
            raise ValueError("The public channel could not be resolved.")
        now = utc_now()
        try:
            with self.history._connect() as c:
                cur = c.execute("""INSERT INTO watchlist_channels
                    (channel_id,title,thumbnail_url,subscriber_count,video_count,notes,state,source,last_researched_at,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,'active','public_observation',NULL,?,?)""",
                    (channel_id, metadata.get("title"), metadata.get("thumbnail_url"), _int(metadata.get("subscriber_count")), _int(metadata.get("video_count")), notes, now, now))
                item_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            if exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
                raise AlreadyWatched("This channel is already in the watchlist.") from exc
            raise
        return self.channel(item_id) or {}

    def channels(self, state: str | None = None) -> list[dict[str, Any]]:
        if state and state not in {"active", "archived"}: raise ValueError("Unknown watchlist state.")
        where, args = ("WHERE ch.state=?", (state,)) if state else ("", ())
        # One query for the whole list. An item carries only its latest
        # snapshot; the full history is on the channel's own endpoint.
        latest = ",".join(f"s.{column}" for column in _CHANNEL_SNAPSHOT_COLUMNS.split(","))
        with self.history._connect() as c:
            rows = c.execute(f"""SELECT {_CHANNEL_COLUMNS},{latest} FROM watchlist_channels ch
                LEFT JOIN watchlist_channel_snapshots s ON s.id=(SELECT x.id FROM watchlist_channel_snapshots x WHERE x.watchlist_channel_id=ch.id ORDER BY x.captured_at DESC,x.id DESC LIMIT 1)
                {where} ORDER BY ch.updated_at DESC""", args).fetchall()
        width = len(_CHANNEL_KEYS)
        return [{**dict(zip(_CHANNEL_KEYS, row[:width], strict=True)), "snapshots": [_channel_snapshot(row[width:])] if row[width] is not None else []} for row in rows]

    def channel(self, item_id: int) -> dict[str, Any] | None:
        with self.history._connect() as c:
            row = c.execute(f"SELECT {_CHANNEL_COLUMNS} FROM watchlist_channels ch WHERE ch.id=?", (item_id,)).fetchone()
            snaps = c.execute(f"SELECT {_CHANNEL_SNAPSHOT_COLUMNS} FROM watchlist_channel_snapshots WHERE watchlist_channel_id=? ORDER BY captured_at DESC,id DESC", (item_id,)).fetchall()
        if not row: return None
        result = dict(zip(_CHANNEL_KEYS, row, strict=True)); result["snapshots"] = [_channel_snapshot(s) for s in snaps]
        return result

    def update_channel(self, item_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
        allowed={"notes","state"}; unknown=set(changes)-allowed
        if unknown: raise ValueError("Only notes and active/archive state may be changed.")
        if changes.get("state") not in {None,"active","archived"}: raise ValueError("Unknown watchlist state.")
        if not changes: raise ValueError("Provide a watchlist update.")
        with self.history._connect() as c:
            cur=c.execute(f"UPDATE watchlist_channels SET {','.join(f'{k}=?' for k in changes)},updated_at=? WHERE id=?",(*changes.values(),utc_now(),item_id))
        return self.channel(item_id) if cur.rowcount else None

    def snapshot_channel(self, item_id: int, metadata: dict[str, Any], videos: list[dict[str, Any]]) -> dict[str, Any]:
        now=utc_now()
        with self.history._connect() as c:
            c.execute("INSERT INTO watchlist_channel_snapshots(watchlist_channel_id,captured_at,subscriber_count,video_count,view_count,metadata_json,source) VALUES(?,?,?,?,?,?,'public_observation')",(item_id,now,_int(metadata.get('subscriber_count')),_int(metadata.get('video_count')),_int(metadata.get('view_count')),json.dumps(metadata)))
            c.execute("UPDATE watchlist_channels SET title=?,thumbnail_url=?,subscriber_count=?,video_count=?,last_researched_at=?,updated_at=? WHERE id=?",(metadata.get('title'),metadata.get('thumbnail_url'),_int(metadata.get('subscriber_count')),_int(metadata.get('video_count')),now,now,item_id))
        for video in videos: self.upsert_video(video, watchlist_channel_id=item_id, snapshot=True)
        return self.channel(item_id) or {}

    def create_video(self, metadata: dict[str, Any], notes: str = "") -> dict[str, Any]:
        return self.upsert_video(metadata, notes=notes, snapshot=False, reject_duplicate=True)

    def upsert_video(self, metadata: dict[str, Any], *, watchlist_channel_id: int | None = None, notes: str = "", snapshot: bool = True, reject_duplicate: bool = False) -> dict[str, Any]:
        video_id=str(metadata.get("video_id") or "").strip(); title=str(metadata.get("title") or "").strip()
        if not video_id or not title: raise ValueError("The public video could not be resolved.")
        seconds=duration_seconds(metadata.get("duration")); now=utc_now(); language=str(metadata.get("default_language") or "unknown").lower(); fmt=inferred_format(seconds)
        with self.history._connect() as c:
            existing=c.execute("SELECT id FROM watchlist_videos WHERE video_id=?",(video_id,)).fetchone()
            if existing and reject_duplicate: raise AlreadyWatched("This video is already in the watchlist.")
            if existing:
                item_id=int(existing[0]); c.execute("""UPDATE watchlist_videos SET watchlist_channel_id=COALESCE(?,watchlist_channel_id),channel_id=?,channel_title=?,title=?,published_at=?,duration_seconds=?,language=?,format=?,last_researched_at=?,updated_at=? WHERE id=?""",(watchlist_channel_id,metadata.get('channel_id'),metadata.get('channel_title'),title,metadata.get('published_at'),seconds,language,fmt,now if snapshot else None,now,item_id))
            else:
                cur=c.execute("""INSERT INTO watchlist_videos(watchlist_channel_id,video_id,channel_id,channel_title,title,published_at,duration_seconds,language,format,notes,state,source,last_researched_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'active','public_observation',?,?,?)""",(watchlist_channel_id,video_id,metadata.get('channel_id'),metadata.get('channel_title'),title,metadata.get('published_at'),seconds,language,fmt,notes,now if snapshot else None,now,now)); item_id=int(cur.lastrowid)
            if snapshot:
                c.execute("INSERT INTO watchlist_video_snapshots(watchlist_video_id,captured_at,view_count,like_count,comment_count,duration_seconds,metadata_json,source) VALUES(?,?,?,?,?,?,?,'public_observation')",(item_id,now,_int(metadata.get('view_count')),_int(metadata.get('like_count')),_int(metadata.get('comment_count')),seconds,json.dumps(metadata)))
        return self.video(item_id) or {}

    def videos(self, state: str | None = None, query: str = "") -> list[dict[str, Any]]:
        if state and state not in {"active","archived"}: raise ValueError("Unknown watchlist state.")
        clauses=[]; args=[]
        if state: clauses.append("v.state=?"); args.append(state)
        if query: clauses.append("(v.title LIKE ? OR v.channel_title LIKE ?)"); args.extend([f"%{query}%",f"%{query}%"])
        where="WHERE "+" AND ".join(clauses) if clauses else ""
        # One query for the whole list. An item carries only its latest
        # snapshot; the full history is on the video's own endpoint.
        with self.history._connect() as c: items=_video_rows(c,where,tuple(args))
        for item in items: item["snapshots"]=[item["latest_snapshot"]] if item["latest_snapshot"] else []
        return items

    def video(self,item_id:int)->dict[str,Any]|None:
        with self.history._connect() as c:
            items=_video_rows(c,"WHERE v.id=?",(item_id,))
            snaps=c.execute(f"SELECT {_VIDEO_SNAPSHOT_COLUMNS} FROM watchlist_video_snapshots WHERE watchlist_video_id=? ORDER BY captured_at DESC,id DESC",(item_id,)).fetchall()
        if not items:return None
        result=items[0]; result["snapshots"]=[_video_snapshot(s) for s in snaps]; result["latest_snapshot"]=result["snapshots"][0] if result["snapshots"] else None
        return result

    def update_video(self,item_id:int,changes:dict[str,Any])->dict[str,Any]|None:
        allowed={"notes","state"};
        if set(changes)-allowed: raise ValueError("Only notes and active/archive state may be changed.")
        if changes.get('state') not in {None,'active','archived'}: raise ValueError("Unknown watchlist state.")
        if not changes: raise ValueError("Provide a watchlist update.")
        with self.history._connect() as c: cur=c.execute(f"UPDATE watchlist_videos SET {','.join(f'{k}=?' for k in changes)},updated_at=? WHERE id=?",(*changes.values(),utc_now(),item_id))
        return self.video(item_id) if cur.rowcount else None

    def analyze_outlier(self,item_id:int)->dict[str,Any]:
        target=self.video(item_id)
        if not target: raise KeyError(item_id)
        snap=target.get('latest_snapshot') or {}; observed=snap.get('view_count'); channel_id=str(target.get('channel_id') or '').strip()
        age_hours=None; peers=[]
        with self.history._connect() as c:
            if observed is not None:
                # SQLite reads both timestamps, offsets included, the same way for the video and its peers.
                age_hours=c.execute("SELECT (julianday(?)-julianday(?))*24",(snap.get('captured_at'),target.get('published_at'))).fetchone()[0]
            if channel_id and age_hours is not None:
                rows=c.execute("""SELECT v.id,v.format,s.view_count,(julianday(s.captured_at)-julianday(v.published_at))*24
                    FROM watchlist_videos v JOIN watchlist_video_snapshots s ON s.watchlist_video_id=v.id
                    WHERE v.channel_id=? AND v.id!=? AND v.state='active' AND s.view_count IS NOT NULL
                      AND abs(julianday(v.published_at)-julianday(?))<=?""",(channel_id,item_id,target.get('published_at'),PEER_PUBLISH_WINDOW_DAYS)).fetchall()
                peers=_peer_views_at_age(rows,target.get('format'),max(float(age_hours),1.0))
        sample=len(peers); now=utc_now(); baseline=round(float(median(peers)),2) if peers else None; status='insufficient_evidence'; multiplier=None
        if not channel_id: explanation="This video's channel is unknown, so there are no channel peers to compare it with."
        elif observed is None: explanation="This video has no public view count yet. Refresh it, then run the check again."
        elif age_hours is None: explanation="This video's publication time is unavailable, so its age at the latest snapshot is unknown and no peer can be compared at the same age."
        elif sample<OUTLIER_MIN_PEERS or not baseline or baseline<=0:
            explanation=f"Only {sample} other video(s) from this channel, published within {PEER_PUBLISH_WINDOW_DAYS} days of this one, have a public view count at a similar age; at least {OUTLIER_MIN_PEERS} with a positive median are required."
        else:
            multiplier=round(float(observed)/baseline,2); status='possible_outlier' if multiplier>=OUTLIER_MULTIPLIER else 'observed_normal'
            explanation=f"Views are {multiplier:.2f}x the median of {sample} videos from this channel published within {PEER_PUBLISH_WINDOW_DAYS} days of it, each compared at a similar age by views per day." + (" This is an observational outlier signal, not a viral prediction." if status=='possible_outlier' else f" That is below the {OUTLIER_MULTIPLIER:g}x outlier boundary.")
        signals={"topic":target.get('title'),"format":target.get('format'),"language":target.get('language'),"published_at":target.get('published_at'),"engagement_ratio":_engagement(snap),"limitation":"Public association does not establish that title, format, timing, or engagement caused the views."}
        with self.history._connect() as c:
            cur=c.execute("INSERT INTO watchlist_outlier_analyses(watchlist_video_id,analyzed_at,status,observed_views,baseline_median_views,relative_multiplier,sample_size,observation_window,explanation,signals_json,provenance) VALUES(?,?,?,?,?,?,?,?,?,?,'heuristic_public_observation')",(item_id,now,status,_int(observed),baseline,multiplier,sample,OUTLIER_OBSERVATION_WINDOW,explanation,json.dumps(signals)))
            analysis_id=int(cur.lastrowid)
        return {"id":analysis_id,"status":status,"observed_views":_int(observed),"baseline_median_views":baseline,"relative_multiplier":multiplier,"sample_size":sample,"observation_window":OUTLIER_OBSERVATION_WINDOW,"explanation":explanation,"signals":signals,"provenance":"heuristic_public_observation"}

    def save_demand(self, values:dict[str,Any], classification:str, evidence:dict[str,Any], fingerprint:str|None=None)->dict[str,Any]:
        now=utc_now()
        with self.history._connect() as c:
            cur=c.execute("INSERT INTO demand_research_snapshots(idea_id,topic,language,format,region,audience_context,idea_fingerprint,classification,evidence_json,captured_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(values.get('idea_id'),values['topic'],values.get('language'),values.get('format'),values.get('region'),values.get('audience_context'),fingerprint,classification,json.dumps(evidence),now)); item_id=int(cur.lastrowid)
        return self.demand(item_id) or {}

    def demand(self,item_id:int)->dict[str,Any]|None:
        with self.history._connect() as c: row=c.execute(f"SELECT {_DEMAND_COLUMNS} FROM demand_research_snapshots WHERE id=?",(item_id,)).fetchone()
        return _demand(row) if row else None

    def demands(self,limit:int=50,offset:int=0,idea_id:int|None=None)->dict[str,Any]:
        where,args=("WHERE idea_id=?",(idea_id,)) if idea_id else ("",())
        limit,offset=max(1,min(limit,100)),max(0,offset)
        with self.history._connect() as c:
            total=int(c.execute(f"SELECT COUNT(*) FROM demand_research_snapshots {where}",args).fetchone()[0]); rows=c.execute(f"SELECT {_DEMAND_COLUMNS} FROM demand_research_snapshots {where} ORDER BY captured_at DESC,id DESC LIMIT ? OFFSET ?",(*args,limit,offset)).fetchall()
        return {"research":[_demand(row) for row in rows],"total":total,"limit":limit,"offset":offset}


def _video_rows(c:sqlite3.Connection,where:str,args:tuple[Any,...])->list[dict[str,Any]]:
    """Videos with their latest snapshot and latest outlier analysis, in one query."""
    snapshot=",".join(f"s.{column}" for column in _VIDEO_SNAPSHOT_COLUMNS.split(","))
    outlier=",".join(f"o.{column}" for column in _OUTLIER_COLUMNS.split(","))
    rows=c.execute(f"""SELECT {_VIDEO_COLUMNS},{snapshot},{outlier} FROM watchlist_videos v
        LEFT JOIN watchlist_video_snapshots s ON s.id=(SELECT x.id FROM watchlist_video_snapshots x WHERE x.watchlist_video_id=v.id ORDER BY x.captured_at DESC,x.id DESC LIMIT 1)
        LEFT JOIN watchlist_outlier_analyses o ON o.id=(SELECT y.id FROM watchlist_outlier_analyses y WHERE y.watchlist_video_id=v.id ORDER BY y.analyzed_at DESC,y.id DESC LIMIT 1)
        {where} ORDER BY v.updated_at DESC""",args).fetchall()
    video_end=len(_VIDEO_KEYS); snapshot_end=video_end+len(_VIDEO_SNAPSHOT_COLUMNS.split(","))
    return [{**dict(zip(_VIDEO_KEYS,row[:video_end],strict=True)),"latest_snapshot":_video_snapshot(row[video_end:snapshot_end]) if row[video_end] is not None else None,"outlier":_outlier(row[snapshot_end:]) if row[snapshot_end] is not None else None} for row in rows]
def _peer_views_at_age(rows:list[tuple[Any,...]],target_format:Any,age_hours:float)->list[float]:
    """Each peer's views at the video's age, taken from its snapshot nearest that age.

    Scaling by the age ratio compares views per day, which holds only between
    similar ages because views come fastest early on; hence PEER_AGE_RATIO.
    """
    nearest:dict[int,tuple[float,float]]={}
    for peer_id,peer_format,views,peer_age in rows:
        if peer_age is None: continue
        if target_format not in {'unknown',peer_format} and peer_format!='unknown': continue
        ratio=max(float(peer_age),1.0)/age_hours
        if not 1/PEER_AGE_RATIO<=ratio<=PEER_AGE_RATIO: continue
        distance=abs(math.log(ratio))
        if peer_id not in nearest or distance<nearest[peer_id][0]: nearest[peer_id]=(distance,float(views)/ratio)
    return [views for _,views in nearest.values()]
def _channel_snapshot(s:tuple[Any,...])->dict[str,Any]:
    return {"id":s[0],"captured_at":s[1],"subscriber_count":s[2],"video_count":s[3],"view_count":s[4],"metadata":_json(s[5]),"source":s[6]}
def _video_snapshot(s:tuple[Any,...])->dict[str,Any]:
    return {"id":s[0],"captured_at":s[1],"view_count":s[2],"like_count":s[3],"comment_count":s[4],"duration_seconds":s[5],"metadata":_json(s[6]),"source":s[7]}
def _outlier(o:tuple[Any,...])->dict[str,Any]:
    return {"id":o[0],"analyzed_at":o[1],"status":o[2],"observed_views":o[3],"baseline_median_views":o[4],"relative_multiplier":o[5],"sample_size":o[6],"observation_window":o[7],"explanation":o[8],"signals":_json(o[9]),"provenance":o[10]}
def _demand(row:tuple[Any,...])->dict[str,Any]:
    keys=("id","idea_id","topic","language","format","region","audience_context","idea_fingerprint","classification","evidence","captured_at"); result=dict(zip(keys,row,strict=True)); result['evidence']=_json(row[9]); return result
def _int(value:Any)->int|None:
    try:return int(value) if value is not None else None
    except (TypeError,ValueError):return None
def _json(value:str|None)->dict[str,Any]:
    try:
        parsed=json.loads(value or '{}');return parsed if isinstance(parsed,dict) else {}
    except ValueError:return {}
def _engagement(snapshot:dict[str,Any])->float|None:
    views=_int(snapshot.get('view_count')); likes=_int(snapshot.get('like_count')); comments=_int(snapshot.get('comment_count'))
    # Hidden likes are unknown, not zero; without them the ratio would be comments alone.
    return round((likes+comments)/views,4) if views and likes is not None and comments is not None else None
