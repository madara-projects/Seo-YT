"""SQLite persistence for Phase 7 public watchlist and demand observations."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from statistics import median
from typing import Any

from win_engine.feedback.history_store import HistoryStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def duration_seconds(value: Any) -> float | None:
    match = re.fullmatch(r"P(?:([0-9]+)D)?T?(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9.]+)S)?", str(value or ""))
    if not match:
        return None
    days, hours, minutes, seconds = (float(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def inferred_format(seconds: float | None) -> str:
    return "youtube_shorts" if seconds is not None and seconds <= 60 else "long_form" if seconds else "unknown"


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
        except Exception as exc:
            if "UNIQUE constraint" in str(exc):
                raise ValueError("This channel is already in the watchlist.") from exc
            raise
        return self.channel(item_id) or {}

    def channels(self, state: str | None = None) -> list[dict[str, Any]]:
        if state and state not in {"active", "archived"}: raise ValueError("Unknown watchlist state.")
        where, args = ("WHERE state=?", (state,)) if state else ("", ())
        with self.history._connect() as c:
            rows = c.execute(f"SELECT id FROM watchlist_channels {where} ORDER BY updated_at DESC", args).fetchall()
        return [item for row in rows if (item := self.channel(int(row[0])))]

    def channel(self, item_id: int) -> dict[str, Any] | None:
        with self.history._connect() as c:
            row = c.execute("SELECT id,channel_id,title,thumbnail_url,subscriber_count,video_count,notes,state,source,last_researched_at,created_at,updated_at FROM watchlist_channels WHERE id=?", (item_id,)).fetchone()
            snaps = c.execute("SELECT id,captured_at,subscriber_count,video_count,view_count,metadata_json,source FROM watchlist_channel_snapshots WHERE watchlist_channel_id=? ORDER BY captured_at DESC,id DESC", (item_id,)).fetchall()
        if not row: return None
        keys = ("id","channel_id","title","thumbnail_url","subscriber_count","video_count","notes","state","source","last_researched_at","created_at","updated_at")
        result = dict(zip(keys,row)); result["snapshots"] = [{"id":s[0],"captured_at":s[1],"subscriber_count":s[2],"video_count":s[3],"view_count":s[4],"metadata":_json(s[5]),"source":s[6]} for s in snaps]
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
            if existing and reject_duplicate: raise ValueError("This video is already in the watchlist.")
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
        if state: clauses.append("state=?"); args.append(state)
        if query: clauses.append("(title LIKE ? OR channel_title LIKE ?)"); args.extend([f"%{query}%",f"%{query}%"])
        where="WHERE "+" AND ".join(clauses) if clauses else ""
        with self.history._connect() as c: rows=c.execute(f"SELECT id FROM watchlist_videos {where} ORDER BY updated_at DESC",args).fetchall()
        return [item for row in rows if (item:=self.video(int(row[0])))]

    def video(self,item_id:int)->dict[str,Any]|None:
        with self.history._connect() as c:
            row=c.execute("SELECT id,video_id,watchlist_channel_id,channel_id,channel_title,title,published_at,duration_seconds,language,format,notes,state,source,last_researched_at,created_at,updated_at FROM watchlist_videos WHERE id=?",(item_id,)).fetchone()
            snaps=c.execute("SELECT id,captured_at,view_count,like_count,comment_count,duration_seconds,metadata_json,source FROM watchlist_video_snapshots WHERE watchlist_video_id=? ORDER BY captured_at DESC,id DESC",(item_id,)).fetchall()
            outlier=c.execute("SELECT id,analyzed_at,status,observed_views,baseline_median_views,relative_multiplier,sample_size,observation_window,explanation,signals_json,provenance FROM watchlist_outlier_analyses WHERE watchlist_video_id=? ORDER BY analyzed_at DESC,id DESC LIMIT 1",(item_id,)).fetchone()
        if not row:return None
        keys=("id","video_id","watchlist_channel_id","channel_id","channel_title","title","published_at","duration_seconds","language","format","notes","state","source","last_researched_at","created_at","updated_at")
        result=dict(zip(keys,row)); result["snapshots"]=[{"id":s[0],"captured_at":s[1],"view_count":s[2],"like_count":s[3],"comment_count":s[4],"duration_seconds":s[5],"metadata":_json(s[6]),"source":s[7]} for s in snaps]; result["latest_snapshot"]=result["snapshots"][0] if result["snapshots"] else None
        if outlier: result["outlier"]={"id":outlier[0],"analyzed_at":outlier[1],"status":outlier[2],"observed_views":outlier[3],"baseline_median_views":outlier[4],"relative_multiplier":outlier[5],"sample_size":outlier[6],"observation_window":outlier[7],"explanation":outlier[8],"signals":_json(outlier[9]),"provenance":outlier[10]}
        else: result["outlier"]=None
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
        snap=target.get('latest_snapshot') or {}; observed=snap.get('view_count'); channel_id=target.get('channel_id')
        peers=[]
        for item in self.videos(state='active'):
            ps=item.get('latest_snapshot') or {}
            if item['id']==item_id or item.get('channel_id')!=channel_id or ps.get('view_count') is None: continue
            if target.get('format') not in {'unknown',item.get('format')} and item.get('format')!='unknown': continue
            peers.append(float(ps['view_count']))
        sample=len(peers); now=utc_now(); baseline=float(median(peers)) if peers else None
        if observed is None or sample<5 or not baseline or baseline<=0:
            status='insufficient_evidence'; multiplier=None; explanation=f"Only {sample} comparable recent peer video(s) have public view observations; at least 5 with a positive median are required."
        else:
            multiplier=round(float(observed)/baseline,2); status='possible_outlier' if multiplier>=2.5 else 'observed_normal'; explanation=f"Observed views are {multiplier:.2f}x the median of {sample} comparable recent videos from this channel." + (" This is an observational outlier signal, not a viral prediction." if status=='possible_outlier' else " This observation is within the configured local outlier boundary.")
        signals={"topic":target.get('title'),"format":target.get('format'),"language":target.get('language'),"published_at":target.get('published_at'),"engagement_ratio":_engagement(snap),"limitation":"Public association does not establish that title, format, timing, or engagement caused the views."}
        with self.history._connect() as c:
            cur=c.execute("INSERT INTO watchlist_outlier_analyses(watchlist_video_id,analyzed_at,status,observed_views,baseline_median_views,relative_multiplier,sample_size,observation_window,explanation,signals_json,provenance) VALUES(?,?,?,?,?,?,?,?,?,?,'heuristic_public_observation')",(item_id,now,status,_int(observed),baseline,multiplier,sample,'latest_public_snapshot_per_recent_channel_video',explanation,json.dumps(signals)))
            analysis_id=int(cur.lastrowid)
        return {"id":analysis_id,"status":status,"observed_views":_int(observed),"baseline_median_views":baseline,"relative_multiplier":multiplier,"sample_size":sample,"observation_window":"latest_public_snapshot_per_recent_channel_video","explanation":explanation,"signals":signals,"provenance":"heuristic_public_observation"}

    def save_demand(self, values:dict[str,Any], classification:str, evidence:dict[str,Any], fingerprint:str|None=None)->dict[str,Any]:
        now=utc_now()
        with self.history._connect() as c:
            cur=c.execute("INSERT INTO demand_research_snapshots(idea_id,topic,language,format,region,audience_context,idea_fingerprint,classification,evidence_json,captured_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(values.get('idea_id'),values['topic'],values.get('language'),values.get('format'),values.get('region'),values.get('audience_context'),fingerprint,classification,json.dumps(evidence),now)); item_id=int(cur.lastrowid)
        return self.demand(item_id) or {}

    def demand(self,item_id:int)->dict[str,Any]|None:
        with self.history._connect() as c: row=c.execute("SELECT id,idea_id,topic,language,format,region,audience_context,idea_fingerprint,classification,evidence_json,captured_at FROM demand_research_snapshots WHERE id=?",(item_id,)).fetchone()
        if not row:return None
        keys=("id","idea_id","topic","language","format","region","audience_context","idea_fingerprint","classification","evidence","captured_at"); result=dict(zip(keys,row));result['evidence']=_json(row[9]);return result

    def demands(self,limit:int=50,offset:int=0,idea_id:int|None=None)->dict[str,Any]:
        where,args=("WHERE idea_id=?",(idea_id,)) if idea_id else ("",())
        with self.history._connect() as c:
            total=int(c.execute(f"SELECT COUNT(*) FROM demand_research_snapshots {where}",args).fetchone()[0]); rows=c.execute(f"SELECT id FROM demand_research_snapshots {where} ORDER BY captured_at DESC,id DESC LIMIT ? OFFSET ?",(*args,max(1,min(limit,100)),max(0,offset))).fetchall()
        return {"research":[self.demand(int(r[0])) for r in rows],"total":total,"limit":max(1,min(limit,100)),"offset":max(0,offset)}


def _int(value:Any)->int|None:
    try:return int(value) if value is not None else None
    except (TypeError,ValueError):return None
def _json(value:str|None)->dict[str,Any]:
    try:
        parsed=json.loads(value or '{}');return parsed if isinstance(parsed,dict) else {}
    except ValueError:return {}
def _engagement(snapshot:dict[str,Any])->float|None:
    views=_int(snapshot.get('view_count')); likes=_int(snapshot.get('like_count')); comments=_int(snapshot.get('comment_count'))
    return round(((likes or 0)+(comments or 0))/views,4) if views and (likes is not None or comments is not None) else None
